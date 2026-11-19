"""Arquivos detectados nas pastas ficam 'aguardando' o play manual: python -m pytest testes/test_aguardando.py"""
import pytest
from fastapi.testclient import TestClient

from transcritor import db, server
from transcritor.config import carregar


@pytest.fixture()
def ctx(tmp_path):
    base = tmp_path / "base"
    (tmp_path / "config.toml").write_text(f'[geral]\nbase = "{base.as_posix()}"\n', encoding="utf-8")
    cfg = carregar(tmp_path / "config.toml")
    app = server.criar_app(cfg)
    db.iniciar(base / "dados" / "app.db")  # sem lifespan: nenhum monitor, GPU ou Ollama é iniciado
    pasta = cfg.entrada / "orientacao"
    pasta.mkdir(parents=True)
    return TestClient(app, base_url="http://127.0.0.1:8765"), app.state.motor, pasta


def arquivo(pasta, nome="sessao_2p.mp3"):
    f = pasta / nome
    f.write_bytes(b"x" * 10)
    return f


def test_detectado_nao_inicia_sozinho(ctx):
    c, motor, pasta = ctx
    f = arquivo(pasta)
    motor._arquivo_detectado(f, "orientacao")
    motor._arquivo_detectado(f, "orientacao")  # repetição não duplica
    ag = c.get("/api/aguardando").json()
    assert len(ag) == 1 and ag[0]["status"] == "aguardando" and ag[0]["dica"] == 2 and ag[0]["tamanho"] == 10
    assert motor.fila.qsize() == 0 and motor.estado_ativos() == []  # nada foi enfileirado
    assert c.get("/api/jobs").json() == []  # fora do histórico até começar
    assert db.contar_aguardando() == 1


def test_play_aplica_falantes_e_enfileira(ctx):
    c, motor, pasta = ctx
    motor._arquivo_detectado(arquivo(pasta), "orientacao")
    jid = c.get("/api/aguardando").json()[0]["id"]
    r = c.post(f"/api/jobs/{jid}/iniciar", json={"num_falantes": "3", "participantes": [
        {"nome": "Ana", "papel": "Orientador(a)"}, {"nome": "Bia"}, {}]})
    assert r.status_code == 200
    j = db.obter(jid)
    assert j["status"] == "fila" and j["num_falantes"] == 3 and j["participantes"][0]["nome"] == "Ana"
    assert motor.fila.qsize() == 1 and c.get("/api/aguardando").json() == []
    assert [x["id"] for x in c.get("/api/jobs").json()] == [jid]
    assert c.post(f"/api/jobs/{jid}/iniciar", json={}).status_code == 409  # não inicia duas vezes


def test_cada_arquivo_tem_seus_proprios_falantes(ctx):
    c, motor, pasta = ctx
    motor._arquivo_detectado(arquivo(pasta, "a.mp3"), "orientacao")
    motor._arquivo_detectado(arquivo(pasta, "b.mp3"), "orientacao")
    a, b = c.get("/api/aguardando").json()
    c.post(f"/api/jobs/{a['id']}/iniciar", json={"num_falantes": "2", "participantes": []})
    assert db.obter(a["id"])["status"] == "fila" and db.obter(b["id"])["status"] == "aguardando"  # o outro segue esperando


def test_arquivo_removido_some_da_lista(ctx):
    c, motor, pasta = ctx
    f = arquivo(pasta)
    motor._arquivo_detectado(f, "orientacao")
    f.unlink()
    assert c.get("/api/aguardando").json() == [] and db.contar_aguardando() == 0


def test_descartar_mantem_o_arquivo(ctx):
    c, motor, pasta = ctx
    f = arquivo(pasta)
    motor._arquivo_detectado(f, "orientacao")
    jid = c.get("/api/aguardando").json()[0]["id"]
    assert c.delete(f"/api/jobs/{jid}").status_code == 200
    assert f.exists() and c.get("/api/aguardando").json() == []


def test_inicio_automatico_opcional(ctx):
    c, motor, pasta = ctx
    assert c.put("/api/config", json={"auto_iniciar": True}).status_code == 200
    motor._arquivo_detectado(arquivo(pasta), "orientacao")
    assert c.get("/api/aguardando").json() == [] and motor.fila.qsize() == 1
