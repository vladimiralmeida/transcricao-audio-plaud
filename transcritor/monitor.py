"""Monitor da pasta entrada/: detecta áudios novos e processa em fila, um por vez."""
from __future__ import annotations

import logging
import queue
import shutil
import threading
import time
import traceback
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .config import Config
from .pipeline import transcrever_arquivo

log = logging.getLogger("transcritor")


def mover_unico(origem: Path, pasta: Path) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    destino, n = pasta / origem.name, 2
    while destino.exists():
        destino, n = pasta / f"{origem.stem}-{n}{origem.suffix}", n + 1
    shutil.move(str(origem), str(destino))
    return destino


class Monitor:
    def __init__(self, cfg: Config, ao_detectar: Callable[[Path, str], None] | None = None):
        """ao_detectar(caminho, perfil): se informado (modo painel), é chamado quando o arquivo
        termina de ser copiado, em vez de transcrever aqui mesmo."""
        self.cfg = cfg
        self.ao_detectar = ao_detectar
        self.fila: queue.Queue[Path] = queue.Queue()
        self.vistos: set[Path] = set()
        self.lock = threading.Lock()
        self.observador: Observer | None = None

    def perfil_de(self, caminho: Path) -> str | None:
        """A subpasta imediata de entrada/ define o perfil."""
        try:
            partes = caminho.resolve().relative_to(self.cfg.entrada.resolve()).parts
        except ValueError:
            return None
        if len(partes) == 2 and partes[0] in self.cfg.perfis:
            return partes[0]
        return None

    def enfileirar(self, caminho: Path) -> None:
        caminho = Path(caminho)
        if caminho.suffix.lower() not in self.cfg.extensoes or self.perfil_de(caminho) is None:
            return
        with self.lock:
            if caminho in self.vistos:
                return
            self.vistos.add(caminho)
        log.info("Detectado: %s", caminho.name)
        self.fila.put(caminho)

    def varrer_existentes(self) -> None:
        for perfil in self.cfg.perfis:
            for f in sorted((self.cfg.entrada / perfil).glob("*")):
                if f.is_file():
                    self.enfileirar(f)

    def esperar_estavel(self, caminho: Path) -> bool:
        """Espera o tamanho ficar igual por `segundos_estavel` (cópia terminou)."""
        ultimo, desde = -1, time.time()
        while True:
            try:
                tam = caminho.stat().st_size
            except FileNotFoundError:
                return False
            if tam != ultimo:
                ultimo, desde = tam, time.time()
            elif tam > 0 and time.time() - desde >= self.cfg.segundos_estavel:
                try:
                    with open(caminho, "rb"):
                        return True
                except OSError:
                    desde = time.time()  # ainda em uso por outro programa
            time.sleep(1)

    def processar(self, caminho: Path) -> None:
        perfil = self.perfil_de(caminho)
        if not self.esperar_estavel(caminho):
            log.warning("Arquivo sumiu antes de ser processado: %s", caminho.name)
            return
        if self.ao_detectar:
            self.ao_detectar(caminho, perfil)
            return
        try:
            transcrever_arquivo(caminho, perfil, self.cfg)
            mover_unico(caminho, self.cfg.processados / perfil)
        except Exception:
            log.exception("Falha ao processar %s", caminho.name)
            destino = mover_unico(caminho, self.cfg.erros / perfil)
            # O log traz só a pilha de erro técnico, nunca trechos da transcrição.
            destino.with_name(destino.name + ".log").write_text(traceback.format_exc(), encoding="utf-8")

    def trabalhador(self) -> None:
        while True:
            caminho = self.fila.get()
            try:
                self.processar(caminho)
            finally:
                with self.lock:
                    self.vistos.discard(caminho)
                self.fila.task_done()

    def iniciar(self) -> None:
        """Inicia o monitoramento em segundo plano (não bloqueia)."""
        self.cfg.garantir_pastas()
        monitor = self

        class Handler(FileSystemEventHandler):
            def on_created(self, e):
                if not e.is_directory:
                    monitor.enfileirar(Path(e.src_path))

            def on_moved(self, e):
                if not e.is_directory:
                    monitor.enfileirar(Path(e.dest_path))

        threading.Thread(target=self.trabalhador, daemon=True).start()
        self.varrer_existentes()
        self.observador = Observer()
        self.observador.schedule(Handler(), str(self.cfg.entrada), recursive=True)
        self.observador.start()
        log.info("Monitorando %s", self.cfg.entrada)

    def parar(self) -> None:
        if self.observador:
            self.observador.stop()
            self.observador.join()
            self.observador = None

    def rodar(self) -> None:
        """Modo terminal: bloqueia até Ctrl+C."""
        self.iniciar()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("Encerrando…")
        finally:
            self.parar()
