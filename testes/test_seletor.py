"""Testes do seletor nativo de arquivos (o diálogo é simulado): python -m pytest testes/test_seletor.py"""
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from transcritor import db, server
from transcritor.config import carregar


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    base = tmp_path / "base"
    (tmp_path / "config.toml").write_text(f'[geral]\nbase = "{base.as_posix()}"\n', encoding="utf-8")
    cfg = carregar(tmp_path / "config.toml")
    app = server.criar_app(cfg)
    db.iniciar(base / "dados" / "app.db")  # o lifespan não roda sem `with`; sem GPU nem Ollama neste teste
    estado = {"saida": "", "args": None}

    def falso_run(cmd, **kw):
        estado["args"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=estado["saida"] + "\n", stderr="")

    monkeypatch.setattr(server.subprocess, "run", falso_run)
    return TestClient(app, base_url="http://127.0.0.1:8765"), cfg, estado, tmp_path


def test_dialogo_abre_na_pasta_de_entrada_do_perfil(ctx):
    c, cfg, estado, _ = ctx
    r = c.post("/api/escolher-arquivo", json={"perfil": "aula"})
    assert r.json() == {"cancelado": True}
    assert estado["args"][-1] == str(cfg.entrada / "aula")  # diretório inicial do diálogo
    assert (cfg.entrada / "aula").is_dir()


def test_arquivo_fora_da_entrada_e_copiado_e_original_preservado(ctx):
    c, cfg, estado, tmp = ctx
    orig = tmp / "Downloads" / "reuniao.mp3"
    orig.parent.mkdir()
    orig.write_bytes(b"ID3-conteudo")
    estado["saida"] = str(orig)
    e = c.post("/api/escolher-arquivo", json={"perfil": "reuniao"}).json()
    assert e["nome"] == "reuniao.mp3" and e["na_entrada"] is False
    r = c.post("/api/jobs/escolhido", json={"token": e["token"], "perfil": "reuniao", "num_falantes": "2",
                                            "participantes": [{"nome": "Ana", "papel": "Coordenador(a)"}, {"nome": "Bia"}]})
    j = db.obter(r.json()["id"])
    assert orig.read_bytes() == b"ID3-conteudo" and orig.exists()  # original intocado
    assert Path(j["audio"]).parent == cfg.base / "dados" / "uploads" and Path(j["audio"]).read_bytes() == b"ID3-conteudo"
    assert j["origem"] == "upload" and j["num_falantes"] == 2 and j["participantes"][0]["nome"] == "Ana"


def test_arquivo_dentro_da_entrada_e_usado_no_lugar(ctx):
    c, cfg, estado, _ = ctx
    f = cfg.entrada / "orientacao" / "sessao_2p.mp3"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"x")
    estado["saida"] = str(f)
    e = c.post("/api/escolher-arquivo", json={"perfil": "orientacao"}).json()
    assert e["na_entrada"] is True
    j = db.obter(c.post("/api/jobs/escolhido", json={"token": e["token"], "perfil": "orientacao"}).json()["id"])
    assert Path(j["audio"]) == f and j["origem"] == "pasta" and f.exists()


def test_validacoes(ctx):
    c, cfg, estado, tmp = ctx
    ruim = tmp / "programa.exe"
    ruim.write_bytes(b"MZ")
    estado["saida"] = str(ruim)
    assert c.post("/api/escolher-arquivo", json={"perfil": "aula"}).status_code == 400
    assert c.post("/api/escolher-arquivo", json={"perfil": "inexistente"}).status_code == 400
    assert c.post("/api/jobs/escolhido", json={"token": "forjado", "perfil": "aula"}).status_code == 404
    bom = tmp / "a.wav"
    bom.write_bytes(b"RIFF")
    estado["saida"] = str(bom)
    token = c.post("/api/escolher-arquivo", json={"perfil": "aula"}).json()["token"]
    assert c.post("/api/jobs/escolhido", json={"token": token, "perfil": "aula"}).status_code == 200
    assert c.post("/api/jobs/escolhido", json={"token": token, "perfil": "aula"}).status_code == 404  # token de uso único


def test_seletor_indisponivel_devolve_501(ctx, monkeypatch):
    c, *_ = ctx
    monkeypatch.setattr(server.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "erro"))
    assert c.post("/api/escolher-arquivo", json={"perfil": "aula"}).status_code == 501
