"""Pipeline sequencial: FFmpeg → Whisper → (libera GPU) → pyannote → turnos.

Privacidade: nenhuma chamada de rede (HF_HUB_OFFLINE=1) e nenhum trecho da
transcrição é escrito em log.
"""
from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import gc
import glob
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

warnings.filterwarnings("ignore", message=".*torchcodec.*")
warnings.filterwarnings("ignore", message=".*degrees of freedom.*")
warnings.filterwarnings("ignore", message=".*TensorFloat-32.*")
warnings.filterwarnings("ignore", module="pyannote")

from .config import Config
from .markdown import agrupar_turnos, atribuir_falantes, montar_markdown, rotular_falantes

log = logging.getLogger("transcritor")

DIARIZACAO = "pyannote/speaker-diarization-community-1"
# Estímulo para o Whisper não "limpar" hesitações em entrevistas (transcrição literal).
PROMPT_LITERAL = "Éh... então, é, né, hum... eu acho que, tipo, é... assim, ééé, sabe?"

# (percentual, etapa) — chamado durante o processamento; pode lançar exceção para cancelar.
Progresso = Callable[[float, str], None]


class Cancelado(Exception):
    """Lançada pelo callback de progresso para interromper o processamento."""


@dataclass
class Resultado:
    turnos: list[dict]  # [{"inicio": s, "falante": "Falante 1", "texto": "..."}]
    falantes: list[str]
    duracao: float
    modelo: str


def registrar_dlls_nvidia() -> None:
    """Torna visíveis as DLLs cuBLAS/cuDNN instaladas via pip (Windows)."""
    base = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    if base.is_dir():
        for sub in base.iterdir():
            b = sub / "bin"
            if b.is_dir():
                os.add_dll_directory(str(b))
                os.environ["PATH"] = f"{b}{os.pathsep}{os.environ['PATH']}"


def achar_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    padrao = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\bin\ffmpeg.exe")
    achados = glob.glob(padrao, recursive=True)
    if achados:
        return achados[0]
    raise RuntimeError("FFmpeg não encontrado no PATH (veja o README, seção FFmpeg).")


def dica_falantes(nome: str) -> int | None:
    m = re.search(r"_(\d{1,2})p$", Path(nome).stem, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _converter_wav(origem: Path, destino: Path) -> float:
    cmd = [achar_ffmpeg(), "-y", "-loglevel", "error", "-i", str(origem), "-ac", "1", "-ar", "16000",
           "-c:a", "pcm_s16le", str(destino)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg falhou ao converter o áudio: {r.stderr.strip()[:300]}")
    with wave.open(str(destino), "rb") as w:
        return w.getnframes() / w.getframerate()


def _liberar_gpu() -> None:
    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _transcrever(wav: Path, duracao: float, cfg: Config, perfil: str, modelo: str, compute: str,
                 progresso: Progresso):
    from faster_whisper import WhisperModel

    log.info("Transcrevendo (%s, %s)", modelo, compute)
    progresso(3, "Carregando modelo de transcrição")
    model = WhisperModel(modelo, device="cuda", compute_type=compute)
    try:
        kw = dict(language=cfg.idioma, vad_filter=True, word_timestamps=True,
                  condition_on_previous_text=False)
        if perfil == "entrevista":
            kw["initial_prompt"] = PROMPT_LITERAL
        segmentos, _ = model.transcribe(str(wav), **kw)
        palavras = []
        for s in segmentos:
            palavras.extend((w.start, w.end, w.word) for w in (s.words or []))
            progresso(3 + 57 * min(s.end / max(duracao, 1), 1), "Transcrevendo")
        return palavras
    finally:
        del model
        _liberar_gpu()


def _diarizar(wav: Path, num_falantes: int | None, progresso: Progresso):
    import numpy as np
    import torch
    from pyannote.audio import Pipeline

    log.info("Diarizando%s", f" ({num_falantes} falantes)" if num_falantes else "")
    progresso(60, "Carregando modelo de falantes")
    pipe = Pipeline.from_pretrained(DIARIZACAO)
    pipe.to(torch.device("cuda"))

    faixas = {"segmentation": (60, 80), "embeddings": (80, 96)}

    def hook(nome, artefato, file=None, total=None, completed=None):
        if nome in faixas and total:
            a, b = faixas[nome]
            progresso(a + (b - a) * (completed or 0) / total, "Identificando falantes")

    try:
        with wave.open(str(wav), "rb") as w:
            sr = w.getframerate()
            pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        entrada = {"waveform": torch.from_numpy(pcm.astype(np.float32) / 32768.0).unsqueeze(0),
                   "sample_rate": sr}
        kw = {"hook": hook}
        if num_falantes:
            kw["num_speakers"] = num_falantes
        out = pipe(entrada, **kw)
        return [(t.start, t.end, spk) for t, _, spk in out.speaker_diarization.itertracks(yield_label=True)]
    finally:
        del pipe
        _liberar_gpu()


def _e_oom(exc: BaseException) -> bool:
    return "out of memory" in str(exc).lower() or type(exc).__name__ == "OutOfMemoryError"


def processar(origem: Path, perfil: str, cfg: Config, num_falantes: int | None = None,
              progresso: Progresso | None = None) -> Resultado:
    """Converte, transcreve e diariza. Não escreve nada em saida/."""
    progresso = progresso or (lambda p, e: None)
    registrar_dlls_nvidia()
    origem = Path(origem)
    num_falantes = num_falantes or dica_falantes(origem.name)
    t0 = time.time()
    log.info("Processando %s (perfil %s)", origem.name, perfil)

    with tempfile.TemporaryDirectory(prefix="transcritor_") as tmp:
        wav = Path(tmp) / "audio.wav"
        progresso(1, "Convertendo áudio")
        duracao = _converter_wav(origem, wav)

        modelo_usado = cfg.modelo
        try:
            palavras = _transcrever(wav, duracao, cfg, perfil, cfg.modelo, cfg.compute_type, progresso)
        except Exception as exc:
            if isinstance(exc, Cancelado) or not _e_oom(exc):
                raise
            log.warning("Memória da GPU insuficiente; repetindo com %s / %s",
                        cfg.fallback_modelo, cfg.fallback_compute_type)
            _liberar_gpu()
            palavras = _transcrever(wav, duracao, cfg, perfil, cfg.fallback_modelo,
                                    cfg.fallback_compute_type, progresso)
            modelo_usado = cfg.fallback_modelo

        try:
            turnos_brutos = _diarizar(wav, num_falantes, progresso)
        except Exception as exc:
            if isinstance(exc, Cancelado) or not _e_oom(exc):
                raise
            raise RuntimeError("Memória da GPU insuficiente na diarização, mesmo após a transcrição.") from exc

    progresso(97, "Montando transcrição")
    rotuladas, falantes = rotular_falantes(atribuir_falantes(palavras, turnos_brutos))
    turnos = [{"inicio": ini, "falante": f, "texto": "\n\n".join(par)}
              for ini, f, par in agrupar_turnos(rotuladas)]
    log.info("Processamento concluído em %.0fs (áudio de %.0fs)", time.time() - t0, duracao)
    return Resultado(turnos, falantes, duracao, modelo_usado)


def transcrever_arquivo(origem: Path, perfil: str, cfg: Config, num_falantes: int | None = None) -> Path:
    """Modo CLI: processa e grava saida/<perfil>/AAAA-MM-DD_HHMM_<nome>.md. Devolve o caminho."""
    origem = Path(origem)
    r = processar(origem, perfil, cfg, num_falantes)
    texto = montar_markdown(perfil=perfil, arquivo_origem=origem.name, duracao_s=r.duracao,
                            modelo=r.modelo, turnos=r.turnos, falantes=r.falantes)

    destino_dir = cfg.saida / perfil
    destino_dir.mkdir(parents=True, exist_ok=True)
    nome = f"{datetime.now():%Y-%m-%d_%H%M}_{origem.stem}"
    destino, n = destino_dir / f"{nome}.md", 2
    while destino.exists():
        destino, n = destino_dir / f"{nome}-{n}.md", n + 1
    destino.write_text(texto, encoding="utf-8")
    log.info("Gravado: %s", destino.name)
    return destino
