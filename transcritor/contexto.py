"""Transcrição contextualizada (ata, notas…) com LLM local via Ollama.

O texto só trafega para http://127.0.0.1:11434 (Ollama local). Para áudios longos, a
transcrição é dividida em blocos: cada bloco gera notas fiéis e as notas são
combinadas na etapa final (resumo em duas fases, "map-reduce").
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

import httpx

from .config import RAIZ_PROJETO
from .markdown import hms
from .perfis import PERFIS

OLLAMA = os.environ.get("TRANSCRITOR_OLLAMA", "http://127.0.0.1:11435")
LIBRARY_CUDA = os.environ.get("TRANSCRITOR_OLLAMA_LIB", "cuda_v12")
PASTA_PROMPTS = RAIZ_PROJETO / "prompts"
PALAVRAS_POR_BLOCO = 2000
NUM_CTX = 8192

SISTEMA = ("Você é um assistente de pesquisa e de gabinete. Responda sempre em português do Brasil, "
           "de forma fiel ao texto fornecido, sem inventar fatos, nomes, datas ou prazos. "
           "Quando algo não estiver claro ou não tiver sido dito, escreva 'não informado'.")


# ----------------------------------------------------------------- texto da transcrição
def montar_transcricao(turnos: list[dict], nomes: dict, papeis: dict | None = None) -> str:
    papeis = papeis or {}
    linhas = []
    for t in turnos:
        f = t["falante"]
        quem = nomes.get(f) or f
        if papeis.get(f):
            quem += f" ({papeis[f]})"
        linhas.append(f"[{hms(t['inicio'])}] {quem}: {t['texto'].replace(chr(10) * 2, ' ')}")
    return "\n".join(linhas)


def descrever_participantes(falantes: list[str], nomes: dict, papeis: dict) -> str:
    itens = []
    for f in falantes:
        quem = nomes.get(f) or f
        itens.append(f"- {quem}" + (f" — {papeis[f]}" if papeis.get(f) else ""))
    return "\n".join(itens)


# --------------------------------------------------------------------------- prompts
def caminho_prompt(perfil: str) -> Path:
    if perfil not in PERFIS:
        raise ValueError("perfil inválido")
    return PASTA_PROMPTS / f"{perfil}.md"


def ler_prompt(perfil: str) -> str:
    return caminho_prompt(perfil).read_text(encoding="utf-8")


def gravar_prompt(perfil: str, texto: str) -> None:
    PASTA_PROMPTS.mkdir(exist_ok=True)
    caminho_prompt(perfil).write_text(texto, encoding="utf-8")


def preencher(modelo: str, participantes: str, transcricao: str) -> str:
    txt = modelo.replace("{{participantes}}", participantes)
    if "{{transcricao}}" in txt:
        return txt.replace("{{transcricao}}", transcricao)
    return f"{txt.rstrip()}\n\nTranscrição:\n\n{transcricao}"


# ------------------------------------------------------------------------------ Ollama
def ollama_ativo() -> bool:
    try:
        return httpx.get(f"{OLLAMA}/api/version", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


_processo: subprocess.Popen | None = None


def garantir_ollama() -> None:
    """Inicia um servidor Ollama próprio do painel (porta 11435, só local).

    Usa o backend CUDA 12: neste hardware o backend CUDA 13 padrão do Ollama falha ao inicializar.
    Os modelos baixados (~/.ollama/models) são compartilhados com a instalação normal."""
    global _processo
    if ollama_ativo():
        return
    exe = shutil.which("ollama") or os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    if not Path(exe).exists():
        raise RuntimeError("Ollama não está instalado (winget install Ollama.Ollama).")
    env = {**os.environ, "OLLAMA_HOST": OLLAMA.split("//")[1], "OLLAMA_LLM_LIBRARY": LIBRARY_CUDA}
    _processo = subprocess.Popen([exe, "serve"], env=env, creationflags=0x08000000,  # sem janela
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        if ollama_ativo():
            return
        time.sleep(1)
    raise RuntimeError("Não foi possível iniciar o Ollama.")


def parar_ollama() -> None:
    global _processo
    if _processo and _processo.poll() is None:
        # /T encerra também o processo filho que carrega o modelo na GPU.
        subprocess.run(["taskkill", "/PID", str(_processo.pid), "/T", "/F"], capture_output=True)
    _processo = None


def modelos_instalados() -> list[str]:
    try:
        r = httpx.get(f"{OLLAMA}/api/tags", timeout=3).json()
        return sorted(m["name"] for m in r.get("models", []))
    except Exception:
        return []


def _chat(modelo: str, usuario: str, cancelar: Callable[[], None]) -> str:
    corpo = {"model": modelo, "stream": True, "keep_alive": 0,
             "options": {"num_ctx": NUM_CTX, "temperature": 0.2},
             "messages": [{"role": "system", "content": SISTEMA}, {"role": "user", "content": usuario}]}
    partes: list[str] = []
    with httpx.stream("POST", f"{OLLAMA}/api/chat", json=corpo, timeout=httpx.Timeout(30, read=600)) as r:
        if r.status_code == 404:
            raise RuntimeError(f"Modelo '{modelo}' não instalado no Ollama (ollama pull {modelo}).")
        if r.status_code >= 400:
            r.read()
            try:
                detalhe = r.json().get("error", "")
            except ValueError:
                detalhe = ""
            raise RuntimeError(f"Ollama respondeu {r.status_code}: {detalhe or 'erro ao carregar o modelo'}")
        for linha in r.iter_lines():
            cancelar()
            if not linha:
                continue
            d = json.loads(linha)
            if "error" in d:
                raise RuntimeError(f"Ollama: {d['error']}")
            partes.append(d.get("message", {}).get("content", ""))
    # Modelos pequenos costumam embrulhar a resposta em ```markdown … ```: remove as cercas.
    linhas = [l for l in "".join(partes).splitlines() if l.strip().lower() not in ("```", "```markdown", "```md")]
    return "\n".join(linhas).strip()


def _blocos(transcricao: str, limite: int = PALAVRAS_POR_BLOCO) -> list[str]:
    blocos, atual, n = [], [], 0
    for linha in transcricao.split("\n"):
        w = len(linha.split())
        if atual and n + w > limite:
            blocos.append("\n".join(atual))
            atual, n = [], 0
        atual.append(linha)
        n += w
    if atual:
        blocos.append("\n".join(atual))
    return blocos


def gerar(perfil: str, participantes: str, transcricao: str, modelo: str,
          progresso: Callable[[float], None], cancelar: Callable[[], None]) -> str:
    """Devolve o documento contextualizado (Markdown)."""
    garantir_ollama()
    prompt_modelo = ler_prompt(perfil)
    blocos = _blocos(transcricao)
    if len(blocos) == 1:
        progresso(5)
        saida = _chat(modelo, preencher(prompt_modelo, participantes, blocos[0]), cancelar)
        progresso(100)
        return saida

    tarefa = preencher(prompt_modelo, participantes, "(trecho abaixo)")
    notas: list[str] = []
    total = len(blocos) + 1
    for i, b in enumerate(blocos, 1):
        progresso(100 * (i - 1) / total)
        notas.append(_chat(modelo, (
            f"Você receberá UM TRECHO ({i}/{len(blocos)}) de uma transcrição longa. "
            "Extraia notas objetivas e fiéis, mantendo os tempos [hh:mm:ss] e os nomes, "
            "que servirão depois para cumprir a seguinte tarefa final:\n\n"
            f"=== TAREFA FINAL ===\n{tarefa}\n=== FIM DA TAREFA ===\n\n"
            f"Participantes:\n{participantes}\n\nTrecho:\n{b}"), cancelar))

    # Reduz hierarquicamente se as notas ainda não couberem em um contexto.
    while len("\n".join(notas).split()) > PALAVRAS_POR_BLOCO + 500 and len(notas) > 1:
        grupos = _blocos("\n".join(f"### NOTAS {i}\n{n}" for i, n in enumerate(notas, 1)), PALAVRAS_POR_BLOCO)
        if len(grupos) >= len(notas):
            break
        notas = [_chat(modelo, "Condense estas notas sem perder decisões, prazos, nomes e tempos:\n\n" + g,
                       cancelar) for g in grupos]
    progresso(100 * len(blocos) / total)
    saida = _chat(modelo, preencher(
        prompt_modelo, participantes,
        "(Abaixo, notas extraídas da transcrição completa, em ordem cronológica.)\n\n"
        + "\n\n".join(notas)), cancelar)
    progresso(100)
    return saida
