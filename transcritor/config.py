"""Leitura do config.toml."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    base: Path
    perfis: list[str]
    modelo: str
    compute_type: str
    idioma: str
    fallback_modelo: str
    fallback_compute_type: str
    extensoes: list[str]
    segundos_estavel: float

    @property
    def entrada(self) -> Path:
        return self.base / "entrada"

    @property
    def saida(self) -> Path:
        return self.base / "saida"

    @property
    def processados(self) -> Path:
        return self.base / "processados"

    @property
    def erros(self) -> Path:
        return self.base / "erros"

    def garantir_pastas(self) -> None:
        for p in (self.processados, self.erros):
            p.mkdir(parents=True, exist_ok=True)
        for perfil in self.perfis:
            (self.entrada / perfil).mkdir(parents=True, exist_ok=True)
            (self.saida / perfil).mkdir(parents=True, exist_ok=True)


def carregar(caminho: str | os.PathLike | None = None) -> Config:
    caminho = Path(caminho or os.environ.get("TRANSCRITOR_CONFIG") or RAIZ_PROJETO / "config.toml")
    dados = tomllib.loads(caminho.read_text(encoding="utf-8-sig"))
    g, m, mon = dados.get("geral", {}), dados.get("modelo", {}), dados.get("monitor", {})
    base = Path(g.get("base", caminho.parent))
    if not base.is_absolute():
        base = caminho.parent / base
    return Config(
        base=base,
        perfis=g.get("perfis", ["reuniao", "orientacao", "aula", "entrevista"]),
        modelo=m.get("nome", "large-v3-turbo"),
        compute_type=m.get("compute_type", "float16"),
        idioma=m.get("idioma", "pt"),
        fallback_modelo=m.get("fallback_nome", m.get("nome", "large-v3-turbo")),
        fallback_compute_type=m.get("fallback_compute_type", "int8_float16"),
        extensoes=[e.lower() for e in mon.get("extensoes", [".mp3", ".wav", ".m4a"])],
        segundos_estavel=float(mon.get("segundos_estavel", 5)),
    )
