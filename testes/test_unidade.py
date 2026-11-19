"""Testes de unidade (sem GPU): python -m pytest testes/test_unidade.py"""
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

from transcritor import anonimizar, contexto, db, exportar
from transcritor.markdown import agrupar_turnos, atribuir_falantes, hms, montar_markdown, rotular_falantes
from transcritor.renomear import aplicar, ler_falantes


def palavras():
    return [(0.0, 0.5, " Bom"), (0.5, 1.0, " dia."), (1.2, 1.8, " Oi,"), (1.8, 2.2, " tudo"), (2.2, 2.6, " bem?"),
            (9.0, 9.4, " Certo.")]


def test_alinhamento_e_turnos():
    turnos = [(0, 1.1, "SPEAKER_01"), (1.1, 3, "SPEAKER_00"), (8.5, 10, "SPEAKER_01")]
    rot, falantes = rotular_falantes(atribuir_falantes(palavras(), turnos))
    assert falantes == ["Falante 1", "Falante 2"]
    t = agrupar_turnos(rot)
    assert [x[1] for x in t] == ["Falante 1", "Falante 2", "Falante 1"]
    assert t[0][2] == ["Bom dia."] and t[1][2] == ["Oi, tudo bem?"]


def test_markdown_com_nomes_e_papeis():
    turnos = [{"inicio": 3725, "falante": "Falante 1", "texto": "Olá."}]
    md = montar_markdown(perfil="aula", arquivo_origem="a.mp3", duracao_s=3800, modelo="m", turnos=turnos,
                         falantes=["Falante 1"], nomes={"Falante 1": "Ana: Silva"}, papeis={"Falante 1": "Professor(a)"},
                         hoje=date(2026, 11, 19))
    assert '**[01:02:05] Ana: Silva:** Olá.' in md
    assert 'falantes: ["Ana: Silva"]' in md and "papeis:" in md and hms(3725) == "01:02:05"


def test_renomear_troca_cruzada():
    linhas = ["---", "falantes: [Falante 1, Falante 2]", "---", "", "**[00:00:01] Falante 1:** a", "**[00:00:02] Falante 2:** b"]
    novo = aplicar(linhas, {"Falante 1": "Falante 2", "Falante 2": "Falante 1"})
    assert novo[4].startswith("**[00:00:01] Falante 2:**") and novo[5].startswith("**[00:00:02] Falante 1:**")
    assert ler_falantes(novo) == ["Falante 2", "Falante 1"]


def test_anonimizacao():
    turnos = [{"inicio": 0, "falante": "Falante 1", "texto": "Eu sou Maria da Silva, da Universidade Alfa. Fale com maria@ex.com ou (81) 99999-1234."},
              {"inicio": 5, "falante": "Falante 2", "texto": "Certo, Silva. Meu CPF é 123.456.789-09."}]
    termos = [{"termo": "Maria da Silva", "codigo": "ENTREVISTADO 1"}, {"termo": "Universidade Alfa", "codigo": "TERMO 1"}]
    novos, tabela = anonimizar.anonimizar(turnos, termos, {"Falante 1": "Maria da Silva"})
    texto = " ".join(t["texto"] for t in novos)
    for vazado in ("Maria", "Silva", "Alfa", "maria@ex.com", "99999", "123.456.789-09"):
        assert vazado not in texto, vazado
    assert novos[0]["falante"] == "ENTREVISTADO 1" and novos[1]["falante"] == "Falante 2"
    assert any(r["codigo"].startswith("CPF") for r in tabela)


def test_transcricao_para_llm_e_prompt():
    turnos = [{"inicio": 61, "falante": "Falante 1", "texto": "Primeira.\n\nSegunda."}]
    t = contexto.montar_transcricao(turnos, {"Falante 1": "Ana"}, {"Falante 1": "Orientadora"})
    assert t == "[00:01:01] Ana (Orientadora): Primeira. Segunda."
    p = contexto.preencher("X {{participantes}} Y {{transcricao}}", "- Ana", t)
    assert "- Ana" in p and t in p and "{{" not in p
    assert len(contexto._blocos("a b c\n" * 3000, 2000)) > 1


def test_banco_busca_sem_acento(tmp_path: Path):
    db.iniciar(tmp_path / "t.db")
    jid = db.criar_job(nome="Reunião.mp3", perfil="reuniao", audio="x", turnos=[{"inicio": 0, "falante": "Falante 1", "texto": "Discutimos o capítulo da metodologia"}])
    db.reindexar(jid)
    assert [j["id"] for j in db.listar("capitulo")] == [jid]
    assert [j["id"] for j in db.listar("metod")] == [jid]
    assert db.listar("inexistente") == [] and db.listar('" OR 1=1 --') == []
    db.remover(jid)
    assert db.listar("capitulo") == []


def test_exportacoes(tmp_path: Path):
    job = {"id": 7, "nome": "Aula 1.mp3", "perfil": "aula", "criado_em": "2026-11-19T10:00:00", "duracao": 90, "modelo": "m", "md": None,
           "turnos": [{"inicio": 0, "falante": "Falante 1", "texto": "Texto."}], "falantes": {"Falante 1": {"nome": "Ana", "papel": "Professor(a)"}},
           "contexto": "# Notas\n\n- **Tema** um\n1. dois"}
    assert exportar.docx_bytes(job, "transcricao")[:2] == b"PK" and exportar.docx_bytes(job, "ata")[:2] == b"PK"
    nota = exportar.exportar_obsidian(job, tmp_path)
    assert nota.exists() and "## Transcrição" in nota.read_text(encoding="utf-8") and "## Notas de estudo" in nota.read_text(encoding="utf-8")
    md = exportar.escrever_md(job, tmp_path / "saida")
    assert md.exists() and "Ana" in md.read_text(encoding="utf-8")
