"""Benchmark do LLM local com texto sintético: python testes/bench_llm.py <porta> <modelo> <num_ctx>

Mede velocidade de leitura do prompt e de geração, e quanto do modelo ficou na GPU.
"""
import subprocess
import sys
import time

import httpx

porta, modelo, num_ctx = sys.argv[1], sys.argv[2], int(sys.argv[3])
base = f"http://127.0.0.1:{porta}"
texto = ("[00:10:00] Falante 1: Hoje vamos discutir o andamento do capítulo, a metodologia adotada e os prazos "
         "para a próxima entrega, além das dúvidas sobre a revisão da literatura.\n") * 110
prompt = "Resuma em tópicos curtos o texto abaixo.\n\n" + texto
t0 = time.time()
r = httpx.post(f"{base}/api/chat", timeout=900, json={
    "model": modelo, "stream": False, "keep_alive": "2m", "options": {"num_ctx": num_ctx, "temperature": 0.2, "num_predict": 300},
    "messages": [{"role": "user", "content": prompt}]}).json()
if "error" in r:
    print("ERRO:", r["error"][:200])
    sys.exit(1)
print(f"{modelo} ctx={num_ctx}: total {time.time()-t0:.0f}s | prompt {r['prompt_eval_count']} tok a "
      f"{r['prompt_eval_count']/(r['prompt_eval_duration']/1e9):.0f} tok/s | geração {r['eval_count']} tok a "
      f"{r['eval_count']/(r['eval_duration']/1e9):.1f} tok/s")
print(subprocess.run([sys.argv[4] if len(sys.argv) > 4 else "ollama", "ps"], capture_output=True, text=True,
                     env={**__import__("os").environ, "OLLAMA_HOST": f"127.0.0.1:{porta}"}).stdout)
