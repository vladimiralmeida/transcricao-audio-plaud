# Arquitetura

## Visão geral

```
 Navegador (SPA em HTML/CSS/JS puro, sem CDN)
        │  HTTP + SSE (127.0.0.1:8765)
        ▼
 FastAPI (server.py) ── valida Host/Origin ── API REST
        │
        ▼
 Motor (engine.py): fila única + progresso em memória ── SQLite/FTS5 (db.py, dados/app.db)
   │        │                │
   │        │                └─ MonitorGPU (gpu.py): nvidia-smi a cada 1 s
   │        └─ Monitor de pasta (monitor.py, watchdog) → cria trabalhos de entrada/<perfil>/
   ▼
 pipeline.py                         contexto.py (LLM local)
 FFmpeg → Whisper → libera GPU →     Ollama próprio (127.0.0.1:11435, CUDA 12)
 pyannote → turnos                   blocos + notas + documento final
```

A GPU de 6 GB atende **um trabalho por vez**: transcrição, separação de falantes e LLM são etapas sequenciais, e o
modelo de cada etapa é descarregado antes da seguinte (`del` + `torch.cuda.empty_cache()`; o Ollama usa `keep_alive: 0`).

## Pipeline de transcrição (`pipeline.py`)

1. FFmpeg converte para WAV mono 16 kHz (temporário).
2. `faster-whisper` `large-v3-turbo`, `float16`, `pt`, VAD e *word timestamps*. Em erro de memória, repete com
   `int8_float16` (`config.toml`). Perfil *entrevista* usa um `initial_prompt` que estimula manter hesitações.
3. GPU liberada.
4. `pyannote` (`speaker-diarization-community-1`) com `num_speakers` quando informado. O áudio é entregue ao pyannote
   como tensor em memória, porque o `torchcodec` precisa de DLLs do FFmpeg que o Windows não tem aqui.
5. Cada palavra vai para o falante cujo turno contém seu ponto médio; falas consecutivas do mesmo falante são
   unidas em turnos, e pausas > 2,5 s abrem novo parágrafo.
6. O callback de progresso (0–100 %) pesa: conversão 1 %, Whisper 3–60 %, pyannote 60–96 %, montagem 97 %.
   O mesmo callback lança `Cancelado` para interromper o trabalho.

## Documento contextualizado (`contexto.py`)

Os prompts ficam em `prompts/<perfil>.md` com os marcadores `{{participantes}}` e `{{transcricao}}`.
Até ~2000 palavras o texto vai inteiro ao modelo. Acima disso: cada bloco gera notas fiéis (cientes da tarefa
final), as notas são condensadas se ainda forem grandes e uma última chamada produz o documento (*map-reduce*).
O contexto é de 8192 tokens. Notas intermediárias são limitadas (≈250 palavras, `num_predict` 700) e o modelo fica
carregado entre os blocos (`keep_alive` 10 min), sendo descarregado da VRAM ao final.

**Desempenho medido** (RTX 4050 6 GB, `qwen2.5:7b`, áudio real de 49 min ≈ 8 mil palavras): 6 chamadas de 18–52 s,
**171 s no total**. O 7B não cabe 100 % na VRAM (≈ 81 % GPU / 19 % CPU); *flash attention* e cache KV em `q8_0`
(`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, definidos pelo painel) deixaram a geração em ≈ 21 tok/s.
Antes dessa otimização (modelo recarregado a cada bloco, notas longas) o mesmo trabalho passava de 10 minutos por
bloco. `testes/bench_llm.py` mede velocidade e divisão CPU/GPU de qualquer modelo.
O Ollama às vezes devolve erro 500 ao carregar o modelo; o painel tenta de novo uma vez automaticamente.

**Limite de qualidade:** o 7B local pode omitir seções pedidas no prompt (num teste real faltaram *Dúvidas em aberto* e
*Referências*). Confira o documento contra a transcrição e ajuste o prompt em Configurações, ou troque o modelo.

### Ollama e CUDA

O painel sobe seu **próprio** servidor `ollama serve` em `127.0.0.1:11435` com `OLLAMA_LLM_LIBRARY=cuda_v12`, e o
encerra ao sair. Motivo: o backend CUDA 13 padrão do Ollama 0.40 falhava na inicialização nesta máquina
(`CUDA error: shared object initialization failed`, erro 500 no `/api/chat`). Os modelos são os mesmos de
`~/.ollama/models`. Se o painel for encerrado à força, esse servidor pode ficar ativo (sem usar VRAM) e é reaproveitado
na próxima abertura. Variáveis: `TRANSCRITOR_OLLAMA` (URL) e `TRANSCRITOR_OLLAMA_LIB` (biblioteca).

## Anonimização (`anonimizar.py`)

Regras, não aprendizado: nomes informados nos falantes (nome completo e cada parte com 3+ letras), termos extras
digitados e padrões (e-mail, CPF, CNPJ, telefone, número CNJ) viram códigos como `[ENTREVISTADO 1]`. Os rótulos
dos falantes viram o mesmo código. A tabela de correspondência é gravada só no banco local.

## Dados (`db.py`)

SQLite em `dados/app.db`: tabela `jobs` (estado, turnos e falantes em JSON, documento, anonimização), `busca`
(FTS5 com `remove_diacritics`, atualizada a cada edição) e `config`. O banco é a fonte da verdade: o `.md` em
`saida/` é regravado a cada alteração de turnos ou falantes. Ao reiniciar, trabalhos interrompidos voltam à fila.

## API

| Método e rota | Função |
|---|---|
| `GET /api/estado` | perfis, configuração, Ollama, GPU, cofres do Obsidian |
| `PUT /api/config` | `ollama_modelo`, `obsidian_cofre`, `obsidian_subpasta`, `monitor_ativo` |
| `GET /api/stream` | SSE a 1 Hz: GPU, trabalhos ativos e contador de versão |
| `GET /api/gpu/historico`, `GET /api/progresso` | histórico para os gráficos |
| `POST /api/jobs` | upload (`arquivo`, `perfil`, `num_falantes`, `participantes`) |
| `POST /api/escolher-arquivo` | abre o seletor nativo do Windows em `entrada\<perfil>`; devolve um token (o caminho fica no servidor) |
| `POST /api/jobs/escolhido` | cria o trabalho a partir do token (dentro de `entrada/`: usa no lugar; fora: copia) |
| `GET /api/jobs?q=&perfil=` | lista e busca |
| `GET/DELETE /api/jobs/{id}` | detalhe / remover do histórico (não apaga arquivos) |
| `PUT /api/jobs/{id}/falantes`, `/turnos`, `/contexto` | edições |
| `POST /api/jobs/{id}/contexto`, `/cancelar`, `/reprocessar`, `/obsidian` | ações |
| `GET /api/jobs/{id}/prompt` | prompt pronto para copiar (entrevista exige `anonimo=true`) |
| `GET /api/jobs/{id}/audio` | áudio com suporte a `Range` (player) |
| `GET /api/jobs/{id}/exportar/{md,md-ata,docx,docx-ata}` | downloads |
| `GET/PUT /api/prompts/{perfil}` | prompts |
| `POST /api/abrir-pasta` | abre uma pasta do projeto no Explorer |

## Segurança local

Escuta só em `127.0.0.1`; o middleware rejeita `Host` que não seja localhost (contra *DNS rebinding*) e `Origin`
externa em requisições que alteram estado. Nomes de arquivo enviados são saneados e só extensões de áudio são aceitas.
O HTML usa escape em todo conteúdo vindo do usuário.
