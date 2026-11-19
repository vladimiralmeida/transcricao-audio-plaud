"""Persistência local (SQLite + FTS5). O banco guarda o texto das transcrições: fica em dados/ (ignorado pelo Git)."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

_lock = threading.RLock()
_caminho: Path | None = None

CAMPOS_JSON = {"participantes", "turnos", "falantes", "anon"}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    perfil TEXT NOT NULL,
    origem TEXT NOT NULL DEFAULT 'upload',
    status TEXT NOT NULL DEFAULT 'fila',
    etapa TEXT NOT NULL DEFAULT '',
    progresso REAL NOT NULL DEFAULT 0,
    num_falantes INTEGER,
    participantes TEXT NOT NULL DEFAULT '[]',
    audio TEXT,
    md TEXT,
    duracao REAL,
    modelo TEXT,
    criado_em TEXT NOT NULL,
    concluido_em TEXT,
    erro TEXT,
    turnos TEXT NOT NULL DEFAULT '[]',
    falantes TEXT NOT NULL DEFAULT '{}',
    contexto TEXT NOT NULL DEFAULT '',
    ctx_status TEXT NOT NULL DEFAULT '',
    ctx_progresso REAL NOT NULL DEFAULT 0,
    ctx_erro TEXT,
    ctx_modelo TEXT,
    anon TEXT NOT NULL DEFAULT '{}'
);
CREATE VIRTUAL TABLE IF NOT EXISTS busca USING fts5(
    job_id UNINDEXED, nome, texto, contexto, tokenize = 'unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
"""


def iniciar(caminho: Path) -> None:
    global _caminho
    _caminho = Path(caminho)
    _caminho.parent.mkdir(parents=True, exist_ok=True)
    with conexao() as c:
        c.executescript(ESQUEMA)
        # Jobs interrompidos por um fechamento do painel voltam à fila na próxima inicialização.
        c.execute("UPDATE jobs SET status='fila', etapa='', progresso=0 WHERE status='processando'")
        c.execute("UPDATE jobs SET ctx_status='' WHERE ctx_status IN ('fila','gerando')")


@contextmanager
def conexao():
    with _lock:
        c = sqlite3.connect(_caminho, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _linha(r: sqlite3.Row | None, completo: bool = True) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    for k in CAMPOS_JSON:
        if k in d:
            d[k] = json.loads(d[k] or ("{}" if k in ("falantes", "anon") else "[]"))
    if not completo:
        for k in ("turnos", "contexto"):
            d.pop(k, None)
    return d


def criar_job(**campos) -> int:
    campos.setdefault("criado_em", agora())
    for k in CAMPOS_JSON & campos.keys():
        campos[k] = json.dumps(campos[k], ensure_ascii=False)
    cols = ", ".join(campos)
    marcas = ", ".join("?" for _ in campos)
    with conexao() as c:
        return c.execute(f"INSERT INTO jobs ({cols}) VALUES ({marcas})", list(campos.values())).lastrowid


def atualizar(job_id: int, **campos) -> None:
    for k in CAMPOS_JSON & campos.keys():
        campos[k] = json.dumps(campos[k], ensure_ascii=False)
    sets = ", ".join(f"{k}=?" for k in campos)
    with conexao() as c:
        c.execute(f"UPDATE jobs SET {sets} WHERE id=?", [*campos.values(), job_id])


def obter(job_id: int, completo: bool = True) -> dict | None:
    with conexao() as c:
        return _linha(c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone(), completo)


def listar(q: str = "", perfil: str = "", limite: int = 200) -> list[dict]:
    """Histórico: não inclui arquivos ainda 'aguardando' o início manual (veja `aguardando`)."""
    sql, args = "SELECT jobs.* FROM jobs", []
    cond = ["jobs.status != 'aguardando'"]
    if q.strip():
        sql += " JOIN busca ON busca.job_id = jobs.id"
        cond.append("busca MATCH ?")
        args.append(_consulta_fts(q))
    if perfil:
        cond.append("jobs.perfil = ?")
        args.append(perfil)
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY jobs.id DESC LIMIT ?"
    with conexao() as c:
        return [_linha(r, completo=False) for r in c.execute(sql, [*args, limite])]


def aguardando() -> list[dict]:
    with conexao() as c:
        return [_linha(r, completo=False) for r in c.execute(
            "SELECT * FROM jobs WHERE status='aguardando' ORDER BY id")]


def contar_aguardando() -> int:
    with conexao() as c:
        return c.execute("SELECT COUNT(*) FROM jobs WHERE status='aguardando'").fetchone()[0]


def audio_em_uso(caminho: str) -> bool:
    """True se já existe trabalho pendente ou em andamento para este arquivo."""
    with conexao() as c:
        return c.execute("SELECT 1 FROM jobs WHERE audio=? AND status IN ('aguardando','fila','processando')",
                         (caminho,)).fetchone() is not None


def _consulta_fts(q: str) -> str:
    """Transforma o texto digitado em consulta FTS segura (cada palavra vira prefixo)."""
    palavras = [p for p in "".join(ch if ch.isalnum() else " " for ch in q).split() if p]
    return " ".join(f'"{p}"*' for p in palavras) or '""'


def reindexar(job_id: int) -> None:
    j = obter(job_id)
    if not j:
        return
    texto = "\n".join(t["texto"] for t in j["turnos"])
    with conexao() as c:
        c.execute("DELETE FROM busca WHERE job_id=?", (job_id,))
        c.execute("INSERT INTO busca (job_id, nome, texto, contexto) VALUES (?,?,?,?)",
                  (job_id, j["nome"], texto, j["contexto"] or ""))


def remover(job_id: int) -> None:
    with conexao() as c:
        c.execute("DELETE FROM busca WHERE job_id=?", (job_id,))
        c.execute("DELETE FROM jobs WHERE id=?", (job_id,))


def ler_config(chave: str, padrao=None):
    with conexao() as c:
        r = c.execute("SELECT valor FROM config WHERE chave=?", (chave,)).fetchone()
    return json.loads(r["valor"]) if r else padrao


def gravar_config(chave: str, valor) -> None:
    with conexao() as c:
        c.execute("INSERT INTO config (chave, valor) VALUES (?,?) "
                  "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, json.dumps(valor)))
