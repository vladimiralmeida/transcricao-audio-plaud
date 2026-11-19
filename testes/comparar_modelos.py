"""Compara modelos locais na geração do documento de um trabalho do painel, sem imprimir o conteúdo.

Uso: python testes/comparar_modelos.py <id_do_trabalho> <pasta_saida> <modelo1> [modelo2 ...]
Imprime só métricas; cada resultado é salvo em <pasta_saida>/<modelo>.md para você ler.
Métricas: tempo, palavras, seções pedidas presentes, tempos [hh:mm:ss] citados (e quantos existem de fato na
transcrição, ±90 s), e “vocabulário novo” (palavras do documento sem correspondente na transcrição: proxy de invenção).
"""
import logging
import re
import sys
import time
import unicodedata
from pathlib import Path

from transcritor import contexto, db
from transcritor.config import carregar
from transcritor.engine import Motor
from transcritor.pipeline import registrar_dlls_nvidia  # noqa: F401  (garante os caminhos de DLL)

logging.getLogger("transcritor").setLevel(logging.WARNING)
SECOES = ["pontos discutidos", "pedidos", "tarefas", "duvidas", "referencias"]


def norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


jid, pasta = int(sys.argv[1]), Path(sys.argv[2])
modelos = sys.argv[3:]
pasta.mkdir(parents=True, exist_ok=True)
cfg = carregar()
db.iniciar(cfg.base / "dados" / "app.db")
motor = Motor(cfg)
job = db.obter(jid)
participantes, transcricao, _ = motor.textos_para_llm(job, False, [])
inicios = [int(t["inicio"]) for t in job["turnos"]]
vocab = {p[:5] for p in re.findall(r"[a-z]{4,}", norm(transcricao))}
print(f"transcrição: {len(transcricao.split())} palavras, {len(job['turnos'])} turnos\n")
print(f"{'modelo':34} {'tempo':>6} {'palav':>6} {'seções':>7} {'tempos':>7} {'válidos':>8} {'novo%':>6}")
for m in modelos:
    t0 = time.time()
    try:
        texto = contexto.gerar(job["perfil"], participantes, transcricao, m, lambda p: None, lambda: None)
    except Exception as exc:
        print(f"{m:34} ERRO {type(exc).__name__}: {str(exc)[:80]}")
        continue
    dt = time.time() - t0
    (pasta / (re.sub(r'[^\w.-]', '_', m) + ".md")).write_text(texto, encoding="utf-8")
    n = norm(texto)
    secoes = sum(s in n for s in SECOES)
    marcas = [int(h) * 3600 + int(mi) * 60 + int(s) for h, mi, s in re.findall(r"(\d\d):(\d\d):(\d\d)", texto)]
    validos = sum(any(abs(x - i) <= 90 for i in inicios) for x in marcas)
    palavras = [p for p in re.findall(r"[a-z]{6,}", n)]
    novas = sum(p[:5] not in vocab for p in palavras)
    print(f"{m:34} {dt:5.0f}s {len(texto.split()):6d} {secoes:5d}/5 {len(marcas):7d} {validos:8d} {100 * novas / max(len(palavras), 1):5.0f}%")
contexto.parar_ollama()
