"""Motor do painel: fila única (a GPU de 6 GB atende um trabalho por vez), progresso e orquestração."""
from __future__ import annotations

import logging
import queue
import threading
import time
import traceback
from pathlib import Path

from . import anonimizar, contexto, db, exportar
from .config import Config
from .gpu import MonitorGPU
from .monitor import Monitor, mover_unico
from .pipeline import Cancelado, processar

log = logging.getLogger("transcritor")

PADRAO = {"ollama_modelo": "qwen3:4b-instruct-2507-q4_K_M", "obsidian_cofre": "", "obsidian_subpasta": "Transcrições",
          "monitor_ativo": True, "auto_iniciar": False}


class Motor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.gpu = MonitorGPU()
        self.fila: queue.Queue[tuple] = queue.Queue()
        self.ativos: dict[int, dict] = {}  # job_id -> estado em memória (progresso ao vivo)
        self.hist: dict[int, list] = {}  # job_id -> [[t, %]] para o gráfico de evolução
        self.cancelados: set[tuple[int, str]] = set()
        self.versao = 0
        self.lock = threading.Lock()
        self.monitor: Monitor | None = None
        self.dados = cfg.base / "dados"

    # ------------------------------------------------------------------ ciclo de vida
    def iniciar(self) -> None:
        self.cfg.garantir_pastas()
        (self.dados / "uploads").mkdir(parents=True, exist_ok=True)
        db.iniciar(self.dados / "app.db")
        self.gpu.iniciar()
        threading.Thread(target=self._trabalhador, daemon=True, name="motor").start()
        # Sobe o servidor do LLM local em segundo plano (não usa VRAM até um modelo ser carregado).
        threading.Thread(target=lambda: self._tentar(contexto.garantir_ollama), daemon=True).start()
        for j in db.listar(limite=1000):
            if j["status"] == "fila":
                self._enfileirar("t", j["id"])
        if self.config("monitor_ativo"):
            self.ligar_monitor()

    def parar(self) -> None:
        self.gpu.parar()
        self.desligar_monitor()
        contexto.parar_ollama()

    @staticmethod
    def _tentar(fn) -> None:
        try:
            fn()
        except Exception as exc:
            log.warning("Ollama indisponível: %s", exc)

    # ---------------------------------------------------------------------- configuração
    def config(self, chave: str):
        return db.ler_config(chave, PADRAO[chave])

    def ligar_monitor(self) -> None:
        if self.monitor:
            return
        self.monitor = Monitor(self.cfg, ao_detectar=self._arquivo_detectado)
        self.monitor.iniciar()

    def desligar_monitor(self) -> None:
        if self.monitor:
            self.monitor.parar()
            self.monitor = None

    def _arquivo_detectado(self, caminho: Path, perfil: str) -> None:
        """Arquivo novo em entrada/<perfil>: por padrão fica AGUARDANDO você configurar os falantes e
        apertar play. Com `auto_iniciar` ligado nas configurações, começa sozinho."""
        if db.audio_em_uso(str(caminho)):
            return
        self.novo_job(caminho.name, perfil, caminho, origem="pasta", iniciar=bool(self.config("auto_iniciar")))

    # ------------------------------------------------------------------------ interface
    def novo_job(self, nome: str, perfil: str, audio: Path, origem: str = "upload",
                 num_falantes: int | None = None, participantes: list | None = None,
                 iniciar: bool = True) -> int:
        jid = db.criar_job(nome=nome, perfil=perfil, origem=origem, audio=str(audio),
                           num_falantes=num_falantes, participantes=participantes or [],
                           status="fila" if iniciar else "aguardando")
        if iniciar:
            self._enfileirar("t", jid)
        else:
            self._bump()
        return jid

    def iniciar_aguardando(self, jid: int, num_falantes: int | None, participantes: list) -> None:
        """Botão play: aplica falantes/nomes informados e põe o arquivo na fila."""
        j = db.obter(jid, completo=False)
        if not j or j["status"] != "aguardando":
            raise ValueError("Este arquivo não está aguardando.")
        db.atualizar(jid, num_falantes=num_falantes, participantes=participantes, status="fila")
        self._enfileirar("t", jid)

    def reprocessar(self, jid: int) -> None:
        db.atualizar(jid, status="fila", etapa="", progresso=0, erro=None)
        self._enfileirar("t", jid)

    def contextualizar(self, jid: int, anonimo: bool, termos_extra: list[str] | None = None) -> None:
        db.atualizar(jid, ctx_status="fila", ctx_progresso=0, ctx_erro=None)
        self._enfileirar("c", jid, anonimo, termos_extra or [])

    def cancelar(self, jid: int, tipo: str) -> None:
        self.cancelados.add((jid, tipo))

    def estado_ativos(self) -> list[dict]:
        with self.lock:
            return [dict(v, id=k) for k, v in self.ativos.items()]

    # ------------------------------------------------------------------------ internals
    def _enfileirar(self, tipo: str, jid: int, *extra) -> None:
        with self.lock:
            self.ativos[jid] = {"tipo": tipo, "etapa": "Na fila", "progresso": 0, "estado": "fila",
                                **self._rotulo(jid)}
            self.versao += 1
        self.fila.put((tipo, jid, *extra))

    def _rotulo(self, jid: int) -> dict:
        j = db.obter(jid, completo=False)
        return {"nome": j["nome"], "perfil": j["perfil"]} if j else {}

    def _atualiza(self, jid: int, **campos) -> None:
        with self.lock:
            if jid in self.ativos:
                self.ativos[jid].update(campos)
                if "progresso" in campos:
                    h = self.hist.setdefault(jid, [])
                    if not h or h[-1][1] != campos["progresso"]:
                        h.append([time.time(), campos["progresso"]])
                        del h[:-2000]

    def _bump(self) -> None:
        with self.lock:
            self.versao += 1

    def _trabalhador(self) -> None:
        while True:
            tipo, jid, *extra = self.fila.get()
            try:
                if tipo == "t":
                    self._rodar_transcricao(jid)
                else:
                    self._rodar_contexto(jid, *extra)
            except Exception:  # pragma: no cover - rede de segurança
                log.exception("Erro inesperado no motor")
            finally:
                with self.lock:
                    self.ativos.pop(jid, None)
                    self.hist.pop(jid, None)
                    self.versao += 1
                self.cancelados.discard((jid, tipo))
                self.fila.task_done()

    # ------------------------------------------------------------------- transcrição
    def _rodar_transcricao(self, jid: int) -> None:
        job = db.obter(jid, completo=False)
        if not job or (jid, "t") in self.cancelados:
            if job:
                db.atualizar(jid, status="cancelado")
            return
        db.atualizar(jid, status="processando", etapa="Iniciando", progresso=0, erro=None)
        self._atualiza(jid, estado="processando", etapa="Iniciando")
        self._bump()
        audio = Path(job["audio"])

        def progresso(pct: float, etapa: str) -> None:
            if (jid, "t") in self.cancelados:
                raise Cancelado()
            self._atualiza(jid, progresso=round(pct, 1), etapa=etapa)

        try:
            r = processar(audio, job["perfil"], self.cfg, job["num_falantes"], progresso)
        except Cancelado:
            db.atualizar(jid, status="cancelado", etapa="", progresso=0)
            return
        except Exception as exc:
            log.error("Falha em %s: %s", jid, type(exc).__name__)
            db.atualizar(jid, status="erro", erro=f"{type(exc).__name__}: {exc}"[:500], etapa="")
            self._guardar_erro(jid, audio, traceback.format_exc())
            return

        falantes = {f: {"nome": "", "papel": ""} for f in r.falantes}
        db.atualizar(jid, turnos=r.turnos, falantes=falantes, duracao=r.duracao, modelo=r.modelo,
                     progresso=100, etapa="Concluído", status="concluido", concluido_em=db.agora())
        j = db.obter(jid)
        md = exportar.escrever_md(j, self.cfg.saida)
        novo_audio = audio
        try:
            novo_audio = mover_unico(audio, self.cfg.processados / job["perfil"])
        except OSError:
            log.warning("Não foi possível mover o áudio para processados/")
        db.atualizar(jid, md=str(md), audio=str(novo_audio))
        db.reindexar(jid)

    def _guardar_erro(self, jid: int, audio: Path, rastro: str) -> None:
        """Move o áudio para erros/<perfil>/ com um .log técnico (sem trechos da fala)."""
        try:
            job = db.obter(jid, completo=False)
            destino = mover_unico(audio, self.cfg.erros / job["perfil"])
            destino.with_name(destino.name + ".log").write_text(rastro, encoding="utf-8")
            db.atualizar(jid, audio=str(destino))
        except OSError:
            pass

    # ------------------------------------------------------------------ contexto (LLM)
    def textos_para_llm(self, job: dict, anonimo: bool, termos_extra: list[str]) -> tuple[str, str, list[dict]]:
        """Devolve (participantes, transcrição, tabela de anonimização)."""
        nomes = {k: v.get("nome", "") for k, v in job["falantes"].items()}
        papeis = {k: v.get("papel", "") for k, v in job["falantes"].items()}
        if not anonimo:
            falantes = exportar.rotulos(job)
            return (contexto.descrever_participantes(falantes, nomes, papeis),
                    contexto.montar_transcricao(job["turnos"], nomes, papeis), [])
        termos, por_papel = [], {}
        for rot in exportar.rotulos(job):
            if nomes.get(rot):
                base = (papeis.get(rot) or "PARTICIPANTE").upper().split("(")[0].strip()
                por_papel[base] = por_papel.get(base, 0) + 1
                termos.append({"termo": nomes[rot], "codigo": f"{base} {por_papel[base]}"})
        for i, t in enumerate(x for x in termos_extra if x.strip()):
            termos.append({"termo": t.strip(), "codigo": f"TERMO {i + 1}"})
        novos, tabela = anonimizar.anonimizar(job["turnos"], termos, nomes)
        rotulos_anon = []
        for t in novos:
            if t["falante"] not in rotulos_anon:
                rotulos_anon.append(t["falante"])
        return ("\n".join(f"- {r}" for r in rotulos_anon),
                contexto.montar_transcricao(novos, {}, {}), tabela)

    def _rodar_contexto(self, jid: int, anonimo: bool, termos_extra: list[str]) -> None:
        job = db.obter(jid)
        if not job:
            return
        if (jid, "c") in self.cancelados:
            db.atualizar(jid, ctx_status="")
            return
        modelo = self.config("ollama_modelo")
        db.atualizar(jid, ctx_status="gerando", ctx_progresso=0, ctx_erro=None)
        self._atualiza(jid, estado="processando", etapa="Gerando documento (LLM local)")
        self._bump()

        def cancelar() -> None:
            if (jid, "c") in self.cancelados:
                raise Cancelado()

        def prog(p: float) -> None:
            self._atualiza(jid, progresso=round(p, 1))

        try:
            participantes, transcricao, tabela = self.textos_para_llm(job, anonimo, termos_extra)
            texto = contexto.gerar(job["perfil"], participantes, transcricao, modelo, prog, cancelar)
        except Cancelado:
            db.atualizar(jid, ctx_status="")
            return
        except Exception as exc:
            log.error("Falha na contextualização %s: %s", jid, type(exc).__name__)
            db.atualizar(jid, ctx_status="erro", ctx_erro=f"{type(exc).__name__}: {exc}"[:500])
            return
        anon = {"ativa": anonimo, "termos_extra": termos_extra, "tabela": tabela}
        db.atualizar(jid, contexto=texto, ctx_status="pronto", ctx_progresso=100, ctx_modelo=modelo, anon=anon)
        db.reindexar(jid)
