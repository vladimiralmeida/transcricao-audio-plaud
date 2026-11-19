"""Teste de integração do painel (precisa do servidor rodando e de GPU).

Uso: python testes/teste_api.py <audio_curto.wav> <pasta_temporaria_cofre_obsidian>
"""
import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8765"
audio, cofre = Path(sys.argv[1]), Path(sys.argv[2])
c = httpx.Client(base_url=BASE, timeout=600)
ok = 0


def check(cond, msg):
    global ok
    assert cond, "FALHOU: " + msg
    ok += 1
    print("ok  -", msg)


def esperar(jid, campo="status", fim=("concluido", "erro", "cancelado", "pronto")):
    for _ in range(300):
        j = c.get(f"/api/jobs/{jid}").json()
        if j[campo] in fim:
            return j
        time.sleep(2)
    raise TimeoutError(campo)


# 1) entrevista: upload + processamento
partes = json.dumps([{"nome": "Carla Mendes", "papel": "Entrevistador(a)"}, {"nome": "João Pereira", "papel": "Entrevistado(a)"}])
r = c.post("/api/jobs", files={"arquivo": (audio.name, audio.read_bytes())},
           data={"perfil": "entrevista", "num_falantes": "2", "participantes": partes})
check(r.status_code == 200, "upload aceito")
jid = r.json()["id"]
j = esperar(jid)
check(j["status"] == "concluido" and len(j["turnos"]) >= 2, "transcrição de entrevista concluída")
check(Path(j["md"]).exists() and "processados" in j["audio"], "md gravado e áudio movido para processados")

# 2) segurança: prompt de entrevista exige anonimização
check(c.get(f"/api/jobs/{jid}/prompt").status_code == 409, "prompt de entrevista sem anonimizar é bloqueado")

# 3) nomes → anonimização no prompt
rot = list(j["falantes"])
c.put(f"/api/jobs/{jid}/falantes", json={"falantes": {rot[0]: {"nome": "Carla Mendes", "papel": "Entrevistador(a)"},
                                                       rot[1]: {"nome": "João Pereira", "papel": "Entrevistado(a)"}}}).raise_for_status()
p = c.get(f"/api/jobs/{jid}/prompt", params={"anonimo": "true", "termos": "capítulo"}).json()
check("Carla" not in p["prompt"] and "João" not in p["prompt"] and "Pereira" not in p["prompt"], "prompt anonimizado sem nomes")
check("ENTREVISTAD" in p["prompt"] and "capítulo" not in p["prompt"].lower().split("transcrição anonimizada")[-1], "códigos e termo extra aplicados")

# 4) edição de turno + busca + md regravado
j = c.get(f"/api/jobs/{jid}").json()
turnos = j["turnos"]
turnos[0]["texto"] = "Texto editado com palavra zebrinha."
c.put(f"/api/jobs/{jid}/turnos", json={"turnos": turnos}).raise_for_status()
check([x["id"] for x in c.get("/api/jobs", params={"q": "zebrinha"}).json()] == [jid], "busca encontra o texto editado")
check("zebrinha" in Path(j["md"]).read_text(encoding="utf-8"), "md regravado após edição")

# 5) contexto (LLM local) anonimizado
c.post(f"/api/jobs/{jid}/contexto", json={"anonimo": True, "termos": []}).raise_for_status()
j = esperar(jid, "ctx_status", ("pronto", "erro"))
check(j["ctx_status"] == "pronto" and len(j["contexto"]) > 80, "documento gerado pelo LLM local")
check("```" not in j["contexto"], "sem cercas de código na saída")
check(j["anon"]["ativa"] is True and len(j["anon"]["tabela"]) >= 2, "tabela de anonimização salva")

# 6) exportações
for fmt, magic in (("md", b"---"), ("docx", b"PK"), ("docx-ata", b"PK"), ("md-ata", b"")):
    r = c.get(f"/api/jobs/{jid}/exportar/{fmt}")
    check(r.status_code == 200 and r.content.startswith(magic), f"exportar {fmt}")
check(c.post(f"/api/jobs/{jid}/obsidian").status_code == 400, "obsidian sem cofre configurado dá erro claro")
c.put("/api/config", json={"obsidian_cofre": str(cofre)}).raise_for_status()
r = c.post(f"/api/jobs/{jid}/obsidian")
check(r.status_code == 200 and Path(r.json()["caminho"]).exists(), "nota criada no cofre do Obsidian")
c.put("/api/config", json={"obsidian_cofre": ""}).raise_for_status()

# 7) áudio com Range (necessário ao player) e proteções
r = c.get(f"/api/jobs/{jid}/audio", headers={"Range": "bytes=0-99"})
check(r.status_code == 206 and len(r.content) == 100, "áudio servido com Range")
check(c.get("/api/estado", headers={"Host": "evil.example"}).status_code == 403, "Host estranho bloqueado")
check(c.post("/api/jobs/1/cancelar", json={"tipo": "t"}, headers={"Origin": "http://evil.example"}).status_code == 403, "Origin estranha bloqueada")
check(c.put("/api/config", json={"foo": 1}).status_code == 400, "config inválida rejeitada")
check(c.post("/api/jobs", files={"arquivo": ("x.exe", b"MZ")}, data={"perfil": "aula"}).status_code == 400, "extensão não-áudio rejeitada")

# 8) remover do histórico mantém arquivos
md = Path(c.get(f"/api/jobs/{jid}").json()["md"])
c.delete(f"/api/jobs/{jid}").raise_for_status()
check(c.get(f"/api/jobs/{jid}").status_code == 404 and md.exists(), "remoção do histórico preserva o .md")
print(f"\n{ok} verificações passaram")
