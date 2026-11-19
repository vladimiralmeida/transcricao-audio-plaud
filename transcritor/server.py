"""Painel web local (FastAPI). Escuta apenas em 127.0.0.1; nada é enviado para fora do computador."""
from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote, urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import contexto, db, exportar
from .config import Config
from .engine import PADRAO, Motor
from .perfis import PERFIS

WEB = Path(__file__).parent / "web"
EXTENSOES_AUDIO = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".wma", ".mp4", ".webm"}


class CorpoFalantes(BaseModel):
    falantes: dict[str, dict[str, str]]


class CorpoTurnos(BaseModel):
    turnos: list[dict]


class CorpoContexto(BaseModel):
    anonimo: bool = False
    termos: list[str] = []


class CorpoTexto(BaseModel):
    contexto: str


class CorpoCancelar(BaseModel):
    tipo: str = "t"


class CorpoPrompt(BaseModel):
    texto: str


class CorpoPasta(BaseModel):
    qual: str


class CorpoEscolher(BaseModel):
    perfil: str


class CorpoEscolhido(BaseModel):
    token: str
    perfil: str
    num_falantes: str = "auto"
    participantes: list[dict] = []


# Executado em um processo à parte (o Tk precisa do seu próprio laço de eventos).
SCRIPT_SELETOR = """
import sys, tkinter as tk
from tkinter import filedialog
r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True); r.update()
p = filedialog.askopenfilename(parent=r, initialdir=sys.argv[1], title='Escolha o áudio para transcrever',
    filetypes=[('Áudio', '*.mp3 *.wav *.m4a *.flac *.ogg *.opus *.aac *.wma *.mp4 *.webm'), ('Todos os arquivos', '*.*')])
print(p)
"""


def criar_app(cfg: Config) -> FastAPI:
    motor = Motor(cfg)
    escolhas: dict[str, Path] = {}  # token -> arquivo escolhido no seletor nativo

    @asynccontextmanager
    async def ciclo(app: FastAPI):
        motor.iniciar()
        yield
        motor.parar()

    app = FastAPI(title="Transcrição de áudio do Plaud Note Pro", lifespan=ciclo)
    app.state.motor = motor

    # ---------------------------------------------------------------- segurança local
    @app.middleware("http")
    async def so_local(request: Request, call_next):
        host = urlparse("//" + (request.headers.get("host") or "")).hostname
        if host not in {"127.0.0.1", "localhost", "::1"}:
            return JSONResponse({"detail": "Host não permitido."}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origem = request.headers.get("origin")
            if origem and urlparse(origem).hostname not in {"127.0.0.1", "localhost", "::1"}:
                return JSONResponse({"detail": "Origem não permitida."}, status_code=403)
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def job_ou_404(jid: int, completo: bool = True) -> dict:
        j = db.obter(jid, completo)
        if not j:
            raise HTTPException(404, "Trabalho não encontrado.")
        return j

    def regravar_md(jid: int) -> None:
        j = db.obter(jid)
        if j and j["status"] == "concluido":
            db.atualizar(jid, md=str(exportar.escrever_md(j, cfg.saida)))

    # ------------------------------------------------------------------------ estado
    def cofres_obsidian() -> list[str]:
        arq = Path(os.path.expandvars(r"%APPDATA%\obsidian\obsidian.json"))
        try:
            return [v["path"] for v in json.loads(arq.read_text(encoding="utf-8")).get("vaults", {}).values()]
        except Exception:
            return []

    @app.get("/api/estado")
    def estado():
        return {
            "perfis": {k: {**v, "pasta_entrada": str(cfg.entrada / k)} for k, v in PERFIS.items()},
            "config": {k: motor.config(k) for k in PADRAO},
            "ollama": {"ativo": contexto.ollama_ativo(), "modelos": contexto.modelos_instalados()},
            "cofres_obsidian": cofres_obsidian(),
            "gpu_nome": motor.gpu.nome,
            "gpu_total_mib": motor.gpu.total_mib,
            "modelo_whisper": f"{cfg.modelo} ({cfg.compute_type})",
            "monitor_ligado": motor.monitor is not None,
        }

    @app.put("/api/config")
    def gravar_config(corpo: dict):
        for k, v in corpo.items():
            if k not in PADRAO or type(v) is not type(PADRAO[k]):
                raise HTTPException(400, f"Configuração inválida: {k}")
            db.gravar_config(k, v)
        if "monitor_ativo" in corpo:
            (motor.ligar_monitor if corpo["monitor_ativo"] else motor.desligar_monitor)()
        return estado()

    @app.get("/api/gpu/historico")
    def gpu_historico():
        return list(motor.gpu.historico)

    @app.get("/api/progresso")
    def progresso_historico():
        """Pontos [tempo, %] dos trabalhos ativos, para o gráfico sobreviver a recarregar a página."""
        with motor.lock:
            return {str(k): list(v) for k, v in motor.hist.items()}

    @app.get("/api/stream")
    async def fluxo(request: Request):
        async def gerar():
            while not await request.is_disconnected():
                dados = {"gpu": motor.gpu.ultima, "ativos": motor.estado_ativos(),
                         "versao": motor.versao, "fila": motor.fila.qsize(), "t": time.time()}
                yield f"data: {json.dumps(dados)}\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(gerar(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/abrir-pasta")
    def abrir_pasta(corpo: CorpoPasta):
        alvo = (cfg.base / corpo.qual).resolve()
        if cfg.base.resolve() not in alvo.parents and alvo != cfg.base.resolve():
            raise HTTPException(400, "Pasta fora da base do projeto.")
        alvo.mkdir(parents=True, exist_ok=True)
        os.startfile(alvo)  # noqa: S606 - abre o Explorer local
        return {"ok": True}

    # ------------------------------------------------------------------------- jobs
    def participantes_e_n(num_falantes: str, participantes) -> tuple[list[dict], int | None]:
        try:
            lista = [{"nome": str(p.get("nome", ""))[:120], "papel": str(p.get("papel", ""))[:60]}
                     for p in (json.loads(participantes) if isinstance(participantes, str) else participantes)][:12]
        except (ValueError, AttributeError):
            raise HTTPException(400, "Participantes inválidos.")
        n = int(num_falantes) if num_falantes.isdigit() and 1 <= int(num_falantes) <= 12 else None
        if n is None and len(lista) > 1:
            n = len(lista)  # a lista de participantes informa quantas pessoas falam
        return lista, n

    @app.post("/api/escolher-arquivo")
    def escolher_arquivo(corpo: CorpoEscolher):
        """Abre o seletor de arquivos NATIVO do Windows já na pasta entrada\\<perfil>.

        (Um navegador não permite escolher a pasta inicial; como o painel roda neste PC, o servidor abre o diálogo.)
        O caminho escolhido fica guardado no servidor e o navegador recebe só um token."""
        if corpo.perfil not in PERFIS:
            raise HTTPException(400, "Perfil inválido.")
        inicial = cfg.entrada / corpo.perfil
        inicial.mkdir(parents=True, exist_ok=True)
        try:
            r = subprocess.run([sys.executable, "-I", "-c", SCRIPT_SELETOR, str(inicial)], capture_output=True,
                               text=True, encoding="utf-8", timeout=900,
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        except subprocess.TimeoutExpired:
            raise HTTPException(408, "Tempo esgotado no seletor de arquivos.")
        if r.returncode != 0:
            raise HTTPException(501, "Seletor nativo indisponível; use o seletor do navegador.")
        caminho = r.stdout.strip()
        if not caminho:
            return {"cancelado": True}
        p = Path(caminho)
        if not p.is_file() or p.suffix.lower() not in EXTENSOES_AUDIO:
            raise HTTPException(400, "Escolha um arquivo de áudio.")
        token = uuid.uuid4().hex
        escolhas[token] = p
        return {"token": token, "nome": p.name, "tamanho": p.stat().st_size,
                "na_entrada": cfg.entrada.resolve() in p.resolve().parents}

    @app.post("/api/jobs/escolhido")
    def criar_de_escolhido(corpo: CorpoEscolhido):
        """Cria o trabalho a partir de um arquivo escolhido no seletor nativo.
        Arquivo dentro de entrada/ é usado no lugar (e movido para processados/ ao final, como sempre);
        arquivo de qualquer outra pasta é COPIADO para dados/uploads, preservando o original."""
        if corpo.perfil not in PERFIS:
            raise HTTPException(400, "Perfil inválido.")
        p = escolhas.pop(corpo.token, None)
        if p is None or not p.is_file():
            raise HTTPException(404, "Arquivo não encontrado; escolha-o novamente.")
        lista, n = participantes_e_n(corpo.num_falantes, corpo.participantes)
        dentro = cfg.entrada.resolve() in p.resolve().parents
        if dentro:
            audio, origem = p, "pasta"
        else:
            pasta = motor.dados / "uploads"
            pasta.mkdir(parents=True, exist_ok=True)
            audio = pasta / f"{time.strftime('%Y%m%d-%H%M%S')}_{exportar.nome_seguro(p.name)}"
            shutil.copyfile(p, audio)
            origem = "upload"
        return {"id": motor.novo_job(p.name, corpo.perfil, audio, origem, n, lista)}

    @app.post("/api/jobs")
    async def criar_job(arquivo: UploadFile = File(...), perfil: str = Form(...),
                        num_falantes: str = Form("auto"), participantes: str = Form("[]")):
        if perfil not in PERFIS:
            raise HTTPException(400, "Perfil inválido.")
        nome = exportar.nome_seguro(Path(arquivo.filename or "audio").name)
        if Path(nome).suffix.lower() not in EXTENSOES_AUDIO:
            raise HTTPException(400, "Formato de áudio não suportado.")
        lista, n = participantes_e_n(num_falantes, participantes)
        pasta = motor.dados / "uploads"
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{time.strftime('%Y%m%d-%H%M%S')}_{nome}"
        with open(destino, "wb") as f:
            while pedaco := await arquivo.read(1 << 20):
                f.write(pedaco)
        jid = motor.novo_job(nome, perfil, destino, "upload", n, lista)
        return {"id": jid}

    @app.get("/api/jobs")
    def listar(q: str = "", perfil: str = ""):
        return db.listar(q, perfil)

    @app.get("/api/jobs/{jid}")
    def detalhe(jid: int):
        j = job_ou_404(jid)
        j["ativo"] = next((a for a in motor.estado_ativos() if a["id"] == jid), None)
        return j

    @app.delete("/api/jobs/{jid}")
    def remover(jid: int):
        job_ou_404(jid, False)
        if any(a["id"] == jid for a in motor.estado_ativos()):
            raise HTTPException(409, "Cancele o trabalho em andamento antes de remover.")
        db.remover(jid)  # só o registro no histórico; arquivos .md e de áudio permanecem em disco
        motor._bump()
        return {"ok": True}

    @app.post("/api/jobs/{jid}/cancelar")
    def cancelar(jid: int, corpo: CorpoCancelar):
        job_ou_404(jid, False)
        motor.cancelar(jid, "c" if corpo.tipo == "c" else "t")
        return {"ok": True}

    @app.post("/api/jobs/{jid}/reprocessar")
    def reprocessar(jid: int):
        j = job_ou_404(jid, False)
        if j["status"] in ("fila", "processando"):
            raise HTTPException(409, "Já está em processamento.")
        if not j["audio"] or not Path(j["audio"]).exists():
            raise HTTPException(410, "Arquivo de áudio não encontrado.")
        motor.reprocessar(jid)
        return {"ok": True}

    @app.put("/api/jobs/{jid}/falantes")
    def gravar_falantes(jid: int, corpo: CorpoFalantes):
        job_ou_404(jid, False)
        limpo = {k: {"nome": v.get("nome", "").strip()[:120], "papel": v.get("papel", "").strip()[:60]}
                 for k, v in corpo.falantes.items()}
        db.atualizar(jid, falantes=limpo)
        regravar_md(jid)
        return {"ok": True}

    @app.put("/api/jobs/{jid}/turnos")
    def gravar_turnos(jid: int, corpo: CorpoTurnos):
        j = job_ou_404(jid, False)
        try:
            turnos = [{"inicio": float(t["inicio"]), "falante": str(t["falante"]), "texto": str(t["texto"])}
                      for t in corpo.turnos]
        except (KeyError, ValueError, TypeError):
            raise HTTPException(400, "Turnos inválidos.")
        db.atualizar(jid, turnos=turnos)
        falantes = dict(j["falantes"])
        for t in turnos:
            falantes.setdefault(t["falante"], {"nome": "", "papel": ""})
        db.atualizar(jid, falantes=falantes)
        db.reindexar(jid)
        regravar_md(jid)
        return {"ok": True}

    # --------------------------------------------------------- contexto / anonimização
    @app.post("/api/jobs/{jid}/contexto")
    def gerar_contexto(jid: int, corpo: CorpoContexto):
        j = job_ou_404(jid, False)
        if j["status"] != "concluido":
            raise HTTPException(409, "A transcrição ainda não terminou.")
        if j["ctx_status"] in ("fila", "gerando"):
            raise HTTPException(409, "Já está gerando.")
        motor.contextualizar(jid, corpo.anonimo, corpo.termos)
        return {"ok": True}

    @app.put("/api/jobs/{jid}/contexto")
    def editar_contexto(jid: int, corpo: CorpoTexto):
        job_ou_404(jid, False)
        db.atualizar(jid, contexto=corpo.contexto)
        db.reindexar(jid)
        return {"ok": True}

    @app.get("/api/jobs/{jid}/prompt")
    def prompt_pronto(jid: int, anonimo: bool = False, termos: str = ""):
        """Prompt completo para copiar e colar em outro serviço (ex.: Claude)."""
        j = job_ou_404(jid)
        if j["perfil"] == "entrevista" and not anonimo:
            raise HTTPException(409, "Entrevistas de pesquisa só podem ser copiadas anonimizadas.")
        extras = [t for t in termos.split("|") if t.strip()]
        participantes, transcricao, tabela = motor.textos_para_llm(j, anonimo, extras)
        return {"prompt": contexto.preencher(contexto.ler_prompt(j["perfil"]), participantes, transcricao),
                "tabela": tabela}

    @app.get("/api/prompts/{perfil}")
    def ler_prompt(perfil: str):
        if perfil not in PERFIS:
            raise HTTPException(404)
        return {"texto": contexto.ler_prompt(perfil)}

    @app.put("/api/prompts/{perfil}")
    def gravar_prompt(perfil: str, corpo: CorpoPrompt):
        if perfil not in PERFIS:
            raise HTTPException(404)
        contexto.gravar_prompt(perfil, corpo.texto)
        return {"ok": True}

    # ------------------------------------------------------------- áudio e exportação
    @app.get("/api/jobs/{jid}/audio")
    def audio(jid: int):
        j = job_ou_404(jid, False)
        caminho = Path(j["audio"] or "")
        if not caminho.is_file():
            raise HTTPException(404, "Áudio não encontrado.")
        return FileResponse(caminho, media_type=mimetypes.guess_type(caminho.name)[0] or "audio/mpeg")

    @app.get("/api/jobs/{jid}/exportar/{formato}")
    def exportar_arquivo(jid: int, formato: str):
        j = job_ou_404(jid)
        base = exportar.nome_seguro(Path(j["nome"]).stem)
        if formato == "md":
            corpo, tipo, nome = exportar.markdown_transcricao(j).encode("utf-8"), "text/markdown", f"{base}.md"
        elif formato == "md-ata":
            corpo, tipo, nome = (j["contexto"] or "").encode("utf-8"), "text/markdown", f"{base}_ata.md"
        elif formato in ("docx", "docx-ata"):
            corpo = exportar.docx_bytes(j, "ata" if formato == "docx-ata" else "transcricao")
            tipo = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            nome = f"{base}{'_ata' if formato == 'docx-ata' else ''}.docx"
        else:
            raise HTTPException(404)
        return Response(corpo, media_type=tipo,
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nome)}"})

    @app.post("/api/jobs/{jid}/obsidian")
    def para_obsidian(jid: int):
        j = job_ou_404(jid)
        cofre = motor.config("obsidian_cofre")
        if not cofre:
            raise HTTPException(400, "Defina a pasta do cofre do Obsidian em Configurações.")
        try:
            destino = exportar.exportar_obsidian(j, Path(cofre), motor.config("obsidian_subpasta"))
        except FileNotFoundError as e:
            raise HTTPException(400, str(e))
        return {"caminho": str(destino)}

    if WEB.is_dir():
        app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    return app
