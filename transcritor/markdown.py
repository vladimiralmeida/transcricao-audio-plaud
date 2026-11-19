"""Alinhamento palavra→falante e geração do Markdown (sem dependências de GPU)."""
from __future__ import annotations

import re
from datetime import date

import numpy as np

PAUSA_PARAGRAFO = 2.5  # segundos de silêncio dentro de uma fala que abrem novo parágrafo


def hms(segundos: float) -> str:
    s = int(max(0, segundos))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def atribuir_falantes(palavras, turnos):
    """palavras: [(ini, fim, texto)]; turnos: [(ini, fim, rotulo_bruto)].
    Devolve [(ini, fim, texto, rotulo_bruto)]. Palavra vai para o turno que contém
    seu ponto médio; se nenhum contiver, para o turno mais próximo."""
    if not turnos:
        return [(a, b, t, "SPEAKER_00") for a, b, t in palavras]
    ini = np.array([t[0] for t in turnos])
    fim = np.array([t[1] for t in turnos])
    rot = [t[2] for t in turnos]
    saida = []
    for a, b, texto in palavras:
        meio = (a + b) / 2
        dentro = np.where((ini <= meio) & (meio <= fim))[0]
        if len(dentro):
            # em sobreposição, prefere o turno que começou por último (quem "tomou a vez")
            i = dentro[np.argmax(ini[dentro])]
        else:
            i = int(np.argmin(np.minimum(np.abs(ini - meio), np.abs(fim - meio))))
        saida.append((a, b, texto, rot[i]))
    return saida


def rotular_falantes(palavras_falante):
    """Troca rótulos brutos por 'Falante N' na ordem de primeira aparição."""
    mapa: dict[str, str] = {}
    for _, _, _, r in palavras_falante:
        if r not in mapa:
            mapa[r] = f"Falante {len(mapa) + 1}"
    return [(a, b, t, mapa[r]) for a, b, t, r in palavras_falante], list(mapa.values())


def agrupar_turnos(palavras_rotuladas):
    """Junta palavras consecutivas do mesmo falante: [(inicio, falante, [paragrafos])]."""
    turnos = []
    for a, b, texto, falante in palavras_rotuladas:
        if not turnos or turnos[-1]["falante"] != falante:
            turnos.append({"inicio": a, "falante": falante, "paragrafos": [texto], "ultimo_fim": b})
            continue
        t = turnos[-1]
        if a - t["ultimo_fim"] > PAUSA_PARAGRAFO:
            t["paragrafos"].append(texto)
        else:
            t["paragrafos"][-1] += texto
        t["ultimo_fim"] = b
    return [(t["inicio"], t["falante"], [p.strip() for p in t["paragrafos"] if p.strip()]) for t in turnos]


def _yaml_item(s: str) -> str:
    """Item seguro para lista YAML em fluxo ([a, b])."""
    return f'"{s}"' if re.search(r'[,:\[\]#"]', s) else s


def montar_markdown(*, perfil, arquivo_origem, duracao_s, modelo, turnos, falantes,
                    nomes=None, papeis=None, status="transcricao-bruta", hoje=None):
    """turnos: [{"inicio", "falante", "texto"}] com rótulos 'Falante N'.
    nomes/papeis: {rótulo: nome/papel}; se houver nome, ele substitui o rótulo."""
    hoje = hoje or date.today()
    nomes, papeis = nomes or {}, papeis or {}

    def mostrar(r):
        return nomes.get(r) or r

    cab = [
        "---",
        f"data: {hoje.isoformat()}",
        f"perfil: {perfil}",
        f"arquivo_origem: {arquivo_origem}",
        f'duracao: "{hms(duracao_s)}"',
        f"falantes: [{', '.join(_yaml_item(mostrar(f)) for f in falantes)}]",
    ]
    if any(papeis.get(f) for f in falantes):
        cab.append("papeis: [" + ", ".join(
            _yaml_item(f"{mostrar(f)} = {papeis[f]}") for f in falantes if papeis.get(f)) + "]")
    cab += [f"modelo: {modelo}", f"status: {status}", "---", ""]
    corpo = []
    for t in turnos:
        corpo.append(f"**[{hms(t['inicio'])}] {mostrar(t['falante'])}:** {t['texto']}")
        corpo.append("")
    if not corpo:
        corpo = ["*(nenhuma fala detectada)*", ""]
    return "\n".join(cab + corpo)
