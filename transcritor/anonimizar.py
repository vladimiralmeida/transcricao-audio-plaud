"""Anonimização por regras (nomes informados + padrões como e-mail, telefone, CPF).

LIMITAÇÃO: não é infalível. Só troca o que foi informado ou reconhecido por padrão;
nomes não listados, apelidos e dados indiretos (cargo + local, por exemplo) podem permanecer.
Sempre revise o texto anonimizado antes de enviá-lo a qualquer serviço externo.
"""
from __future__ import annotations

import re

PADROES = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("CNJ", re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")),
    ("CPF", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("CNPJ", re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")),
    ("TELEFONE", re.compile(r"(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}(?!\d)")),
]
PARTICULAS = {"de", "da", "do", "das", "dos", "e", "di", "du", "van", "von"}


def _variantes(termo: str) -> list[str]:
    """'Maria da Silva' → o nome completo e cada parte com 3+ letras (exceto partículas)."""
    termo = termo.strip()
    partes = [p for p in re.split(r"\s+", termo) if len(p) >= 3 and p.lower() not in PARTICULAS]
    return sorted({termo, *partes}, key=len, reverse=True) if termo else []


def anonimizar(turnos: list[dict], termos: list[dict], nomes_rotulos: dict) -> tuple[list[dict], list[dict]]:
    """termos: [{"termo": "Maria da Silva", "codigo": "ENTREVISTADO 1"}].
    Devolve (turnos anonimizados, tabela de correspondência [{termo, codigo}])."""
    pares: list[tuple[str, str]] = []
    for t in termos:
        for v in _variantes(t.get("termo", "")):
            pares.append((v, f"[{t['codigo']}]"))
    pares.sort(key=lambda p: len(p[0]), reverse=True)
    regex = [(re.compile(rf"(?<!\w){re.escape(v)}(?!\w)", re.IGNORECASE), c) for v, c in pares]

    # Rótulos de falantes (inclui nomes reais já atribuídos) viram o código do termo correspondente.
    codigo_de = {}
    for rotulo, nome in nomes_rotulos.items():
        for t in termos:
            if nome and nome.strip().lower() == t.get("termo", "").strip().lower():
                codigo_de[rotulo] = t["codigo"]

    contadores: dict[str, int] = {}

    def aplicar(texto: str) -> str:
        for rx, cod in regex:
            texto = rx.sub(cod, texto)
        for nome, rx in PADROES:
            def sub(m, nome=nome):
                chave = f"{nome}:{m.group(0)}"
                if chave not in contadores:
                    contadores[chave] = sum(1 for k in contadores if k.startswith(nome + ":")) + 1
                return f"[{nome} {contadores[chave]}]"
            texto = rx.sub(sub, texto)
        return texto

    novos = []
    for t in turnos:
        novos.append({**t, "texto": aplicar(t["texto"]),
                      "falante": codigo_de.get(t["falante"], t["falante"])})
    tabela = [{"termo": t["termo"], "codigo": t["codigo"]} for t in termos]
    tabela += [{"termo": k.split(":", 1)[1], "codigo": f"{k.split(':', 1)[0]} {n}"} for k, n in contadores.items()]
    return novos, tabela
