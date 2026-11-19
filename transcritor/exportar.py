"""Geração de Markdown, exportação para o Obsidian e para Word (.docx)."""
from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path

from .markdown import hms, montar_markdown
from .perfis import PERFIS


def nome_seguro(s: str, limite: int = 80) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s).strip(" .")
    return s[:limite] or "arquivo"


def _mapas(job: dict) -> tuple[dict, dict]:
    nomes = {k: v.get("nome", "") for k, v in job["falantes"].items()}
    papeis = {k: v.get("papel", "") for k, v in job["falantes"].items()}
    return nomes, papeis


def rotulos(job: dict) -> list[str]:
    vistos: list[str] = []
    for t in job["turnos"]:
        if t["falante"] not in vistos:
            vistos.append(t["falante"])
    return vistos


def markdown_transcricao(job: dict) -> str:
    nomes, papeis = _mapas(job)
    return montar_markdown(perfil=job["perfil"], arquivo_origem=job["nome"], duracao_s=job["duracao"] or 0,
                           modelo=job["modelo"] or "", turnos=job["turnos"], falantes=rotulos(job),
                           nomes=nomes, papeis=papeis,
                           status="transcricao-revisada" if job["contexto"] else "transcricao-bruta",
                           hoje=datetime.fromisoformat(job["criado_em"]).date())


def escrever_md(job: dict, pasta_saida: Path) -> Path:
    """Grava (ou regrava) o .md do job em saida/<perfil>/. O banco é a fonte da verdade."""
    destino = Path(job["md"]) if job.get("md") else None
    if destino is None:
        criado = datetime.fromisoformat(job["criado_em"])
        base = pasta_saida / job["perfil"]
        base.mkdir(parents=True, exist_ok=True)
        destino = base / f"{criado:%Y-%m-%d_%H%M}_{nome_seguro(Path(job['nome']).stem)}.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(markdown_transcricao(job), encoding="utf-8")
    return destino


def nota_obsidian(job: dict) -> str:
    cab, _, corpo = markdown_transcricao(job).partition("\n---\n")
    doc = PERFIS[job["perfil"]]["documento"]
    partes = [cab + "\n---\n"]
    if job["contexto"]:
        partes.append(f"## {doc}\n\n{job['contexto'].strip()}\n")
    partes.append(f"## Transcrição\n\n{corpo.strip()}\n")
    return "\n".join(partes)


def exportar_obsidian(job: dict, cofre: Path, subpasta: str = "Transcrições") -> Path:
    cofre = Path(cofre)
    if not cofre.is_dir():
        raise FileNotFoundError("Pasta do cofre do Obsidian não encontrada.")
    pasta = cofre / subpasta / PERFIS[job["perfil"]]["nome"]
    pasta.mkdir(parents=True, exist_ok=True)
    criado = datetime.fromisoformat(job["criado_em"])
    destino = pasta / f"{criado:%Y-%m-%d_%H%M}_{nome_seguro(Path(job['nome']).stem)}_{job['id']}.md"
    destino.write_text(nota_obsidian(job), encoding="utf-8")
    return destino


# -------------------------------------------------------------------------------- Word
def _runs(par, texto: str) -> None:
    for i, trecho in enumerate(re.split(r"\*\*(.+?)\*\*", texto)):
        if trecho:
            par.add_run(trecho).bold = bool(i % 2)


def _md_para_docx(doc, md: str) -> None:
    for linha in md.splitlines():
        s = linha.rstrip()
        if not s.strip():
            continue
        if m := re.match(r"^(#{1,4})\s+(.*)", s):
            doc.add_heading(m.group(2), level=min(len(m.group(1)), 3))
        elif m := re.match(r"^\s*[-*•]\s+(.*)", s):
            _runs(doc.add_paragraph(style="List Bullet"), m.group(1))
        elif m := re.match(r"^\s*\d+[.)]\s+(.*)", s):
            _runs(doc.add_paragraph(style="List Number"), m.group(1))
        else:
            _runs(doc.add_paragraph(), s)


def docx_bytes(job: dict, tipo: str) -> bytes:
    from docx import Document

    nomes, papeis = _mapas(job)
    doc = Document()
    perfil = PERFIS[job["perfil"]]
    if tipo == "ata":
        doc.add_heading(perfil["documento"], level=0)
    else:
        doc.add_heading("Transcrição", level=0)
    doc.add_paragraph(f"{perfil['nome']} · {Path(job['nome']).stem} · duração {hms(job['duracao'] or 0)}")
    if tipo == "ata":
        _md_para_docx(doc, job["contexto"] or "(documento contextualizado ainda não gerado)")
    else:
        for t in job["turnos"]:
            quem = nomes.get(t["falante"]) or t["falante"]
            if papeis.get(t["falante"]):
                quem += f" ({papeis[t['falante']]})"
            p = doc.add_paragraph()
            p.add_run(f"[{hms(t['inicio'])}] {quem}: ").bold = True
            p.add_run(t["texto"].replace("\n\n", " "))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
