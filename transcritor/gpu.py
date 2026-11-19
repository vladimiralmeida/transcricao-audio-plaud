"""Amostrador da GPU NVIDIA via nvidia-smi (1 leitura por segundo, local)."""
from __future__ import annotations

import subprocess
import threading
import time
from collections import deque

CONSULTA = "name,memory.used,memory.total,utilization.gpu,temperature.gpu"


class MonitorGPU:
    def __init__(self, intervalo: float = 1.0, tamanho: int = 300):
        self.intervalo = intervalo
        self.historico: deque[dict] = deque(maxlen=tamanho)
        self.nome = ""
        self.total_mib = 0
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

    def amostra(self) -> dict | None:
        try:
            r = subprocess.run(["nvidia-smi", f"--query-gpu={CONSULTA}", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=5)
            nome, usada, total, util, temp = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
            self.nome, self.total_mib = nome, int(float(total))
            return {"t": time.time(), "usada": int(float(usada)), "total": int(float(total)),
                    "util": int(float(util)), "temp": int(round(float(temp)))}
        except Exception:
            return None

    def _loop(self) -> None:
        while not self._parar.is_set():
            a = self.amostra()
            if a:
                self.historico.append(a)
            self._parar.wait(self.intervalo)

    def iniciar(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True, name="gpu")
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()

    @property
    def ultima(self) -> dict | None:
        return self.historico[-1] if self.historico else None
