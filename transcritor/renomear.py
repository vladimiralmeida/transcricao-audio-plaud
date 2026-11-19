"""renomear-falantes: troca 'Falante N' por nomes reais num arquivo .md gerado."""
from __future__ import annotations

import os
import re
from pathlib import Path

FALA = re.compile(r"^\*\*\[(\d\d:\d\d:\d\d)\] (.+?):\*\* ?(.*)$")
FRONT_FALANTES = re.compile(r"^falantes: \[(.*)\]\s*$")


def ler_falantes(linhas: list[str]) -> list[str]:
    for l in linhas[:30]:
        m = FRONT_FALANTES.match(l)
        if m:
            return [x.strip() for x in m.group(1).split(",") if x.strip()]
    return []


def exemplos(linhas: list[str], falante: str, n: int = 3):
    falas = [(m.group(1), m.group(3)) for l in linhas if (m := FALA.match(l)) and m.group(2) == falante]
    longas = [f for f in falas if len(f[1]) >= 40] or falas
    return longas[:n]


def aplicar(linhas: list[str], mapa: dict[str, str]) -> list[str]:
    """Substituição em passagem única (permite trocar 'Falante 1' e 'Falante 2' entre si)."""
    saida, em_front = [], False
    for i, l in enumerate(linhas):
        if i == 0 and l.strip() == "---":
            em_front = True
        elif em_front and l.strip() == "---":
            em_front = False
        if em_front and FRONT_FALANTES.match(l):
            nomes = ler_falantes([l])
            l = f"falantes: [{', '.join(mapa.get(n, n) for n in nomes)}]"
        elif (m := FALA.match(l)) and m.group(2) in mapa:
            l = f"**[{m.group(1)}] {mapa[m.group(2)]}:** {m.group(3)}"
        saida.append(l)
    return saida


def renomear(arquivo: Path, mapa_cli: dict[str, str] | None = None) -> dict[str, str]:
    arquivo = Path(arquivo)
    linhas = arquivo.read_text(encoding="utf-8").split("\n")
    falantes = ler_falantes(linhas)
    if not falantes:
        raise SystemExit("Nenhum falante encontrado no frontmatter deste arquivo.")
    mapa: dict[str, str] = {}
    for f in falantes:
        if mapa_cli is not None:
            nome = mapa_cli.get(f, "")
        else:
            print(f"\n=== {f} ===")
            for tempo, texto in exemplos(linhas, f):
                print(f"  [{tempo}] {texto[:160]}{'…' if len(texto) > 160 else ''}")
            nome = input(f"Nome para '{f}' (Enter mantém): ").replace("﻿", "").strip()
        if nome and nome != f:
            mapa[f] = nome
    if mapa:
        novo = "\n".join(aplicar(linhas, mapa))
        tmp = arquivo.with_suffix(".md.tmp")
        tmp.write_text(novo, encoding="utf-8")
        os.replace(tmp, arquivo)
    return mapa
