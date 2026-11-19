"""Comandos: transcrever, monitorar, renomear-falantes."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import carregar


def _logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    for ruidoso in ("httpx", "httpcore", "watchdog"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)


def _arg_config(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", help="caminho do config.toml (padrão: o da pasta do projeto)")


def transcrever() -> None:
    p = argparse.ArgumentParser(prog="transcrever", description="Transcreve um áudio e salva em Markdown.")
    p.add_argument("audio", type=Path)
    p.add_argument("--perfil", required=True)
    p.add_argument("--falantes", type=int, help="número de falantes (sobrepõe o sufixo _2p do nome)")
    _arg_config(p)
    a = p.parse_args()
    _logging()
    cfg = carregar(a.config)
    if a.perfil not in cfg.perfis:
        p.error(f"perfil inválido; use um de: {', '.join(cfg.perfis)}")
    if not a.audio.is_file():
        p.error(f"arquivo não encontrado: {a.audio}")
    from .pipeline import transcrever_arquivo

    cfg.garantir_pastas()
    try:
        destino = transcrever_arquivo(a.audio, a.perfil, cfg, a.falantes)
    except Exception as exc:
        logging.getLogger("transcritor").error("Falhou: %s: %s", type(exc).__name__, exc)
        sys.exit(1)
    print(destino)


def monitorar() -> None:
    p = argparse.ArgumentParser(prog="monitorar", description="Monitora entrada/ e transcreve arquivos novos.")
    _arg_config(p)
    a = p.parse_args()
    _logging()
    from .monitor import Monitor

    Monitor(carregar(a.config)).rodar()


def painel() -> None:
    p = argparse.ArgumentParser(prog="painel", description="Abre o painel web local.")
    p.add_argument("--porta", type=int, default=8765)
    p.add_argument("--sem-navegador", action="store_true")
    _arg_config(p)
    a = p.parse_args()
    _logging()
    import threading
    import webbrowser

    import uvicorn

    from .server import criar_app

    app = criar_app(carregar(a.config))
    if not a.sem_navegador:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{a.porta}")).start()
    uvicorn.run(app, host="127.0.0.1", port=a.porta, log_level="warning")


def renomear_falantes() -> None:
    p = argparse.ArgumentParser(prog="renomear-falantes", description="Troca os rótulos 'Falante N' por nomes.")
    p.add_argument("arquivo", type=Path)
    p.add_argument("--mapa", nargs="*", metavar="ROTULO=NOME",
                   help='modo não interativo, ex.: --mapa "Falante 1=Maria" "Falante 2=João"')
    a = p.parse_args()
    from .renomear import renomear

    mapa_cli = None
    if a.mapa is not None:
        mapa_cli = dict(item.split("=", 1) for item in a.mapa if "=" in item)
    mapa = renomear(a.arquivo, mapa_cli)
    print("Renomeado:" if mapa else "Nada alterado.", ", ".join(f"{k} → {v}" for k, v in mapa.items()))
