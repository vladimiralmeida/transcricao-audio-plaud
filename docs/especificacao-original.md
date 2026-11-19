# Transcritor local de gravações (Plaud → Whisper → Markdown)

Cole este arquivo no Claude Code (ou salve como `CLAUDE.md` na pasta do projeto) e peça: "Leia a especificação e implemente, começando pelo ambiente e por um teste com áudio curto."

## Objetivo

Ferramenta de linha de comando para Windows que transcreve, 100% localmente, gravações feitas com o Plaud Note Pro, com identificação dos falantes, e salva o resultado em Markdown. Perfis de uso: reunião profissional, orientação acadêmica, aula e entrevista de pesquisa.

## Ambiente

- Windows 11, notebook com NVIDIA GeForce RTX 4050 Laptop (6 GB de VRAM). Notebook deve estar na tomada para processar.
- Python 3.11 ou 3.12 em ambiente virtual (`venv`) dentro do projeto.
- Antes de instalar, verificar as versões atuais e compatíveis entre si de: `faster-whisper` (ou `whisperx`), CTranslate2, PyTorch com CUDA, cuDNN e `pyannote.audio`. Consultar a documentação oficial; não presumir versões de memória.
- FFmpeg instalado e no PATH.

## Fluxo de uso (pasta monitorada)

Estrutura de pastas (caminho base configurável em `config.toml`):

```
transcritor/
  entrada/
    reuniao/
    orientacao/
    aula/
    entrevista/
  saida/            (uma subpasta por perfil, espelhando entrada/)
  processados/      (áudio original movido para cá após sucesso)
  erros/            (áudio que falhou + log)
  prompts/          (modelos de pós-processamento para colar no Claude)
  config.toml
```

1. O usuário exporta o áudio do Plaud (MP3 ou WAV) e solta o arquivo na subpasta do perfil correspondente. **A subpasta define o perfil.**
2. Um monitor de pasta (`watchdog`) detecta o arquivo novo, espera a cópia terminar (tamanho estável por alguns segundos) e processa em fila, um por vez.
3. O resultado vai para `saida/<perfil>/AAAA-MM-DD_HHMM_<nome-do-arquivo>.md`. O áudio original é movido para `processados/`.
4. Modo alternativo manual: `transcrever caminho/arquivo.mp3 --perfil orientacao`.
5. Dica opcional de nome de arquivo: sufixo `_2p`, `_3p` etc. indica o número de falantes (melhora a diarização). Sem sufixo, detecção automática.

## Pipeline (sequencial, por causa dos 6 GB de VRAM)

1. Converter para WAV mono 16 kHz com FFmpeg (arquivo temporário).
2. Transcrever com `large-v3-turbo` em `float16` na GPU, idioma `pt` fixo, VAD ativado. Parâmetro de configuração para trocar por `large-v3` em `int8_float16`.
3. Liberar a memória da GPU (`del` do modelo, `torch.cuda.empty_cache()`).
4. Diarização com pyannote (pipeline atual recomendado pela documentação), na GPU, usando `num_speakers` quando houver dica.
5. Alinhar segmentos de fala aos falantes (WhisperX faz isso pronto; pode-se usar o WhisperX inteiro se for mais estável).
6. Gerar o Markdown. Apagar temporários.
7. Em erro de memória (CUDA OOM): repetir automaticamente com configuração mais leve; se falhar, mover para `erros/` com log legível.

## Identificação dos falantes

- Rótulos automáticos: `Falante 1`, `Falante 2`, etc.
- Comando `renomear-falantes <arquivo.md>`: mostra 2 ou 3 falas de exemplo de cada falante com o tempo e pergunta o nome; reescreve o arquivo substituindo os rótulos.
- Futuro (não implementar agora): cadastro de voz de pessoas recorrentes (orientador) para rotular automaticamente.

## Formato de saída (Markdown)

Frontmatter YAML:

```yaml
---
data: 2026-11-19
perfil: orientacao
arquivo_origem: nome-original.mp3
duracao: "00:47:12"
falantes: [Falante 1, Falante 2]
modelo: large-v3-turbo
status: transcricao-bruta
---
```

Corpo: blocos por turno de fala, no formato `**[00:12:31] Falante 1:** texto...`. Juntar segmentos consecutivos do mesmo falante. Perfil `entrevista`: transcrição literal, sem nenhuma limpeza, mantendo hesitações e repetições. Demais perfis: pontuação e parágrafos normais, sem resumir nem alterar o conteúdo.

## Pós-processamento (separado, opcional, fora do script)

O script **não** envia nada a nenhum serviço. Em `prompts/` ficam modelos de texto para o usuário colar junto com a transcrição no Claude, por perfil:

- `reuniao.md`: ata com decisões, encaminhamentos, responsáveis e prazos.
- `orientacao.md`: pontos discutidos, pedidos do orientador, tarefas com prazo, dúvidas em aberto.
- `aula.md`: notas por tema, conceitos, autores e referências citados, perguntas para estudo.
- `entrevista.md`: **não resumir**; apenas sugerir codificação temática, sempre sobre transcrição anonimizada.

## Regras de privacidade (obrigatórias)

- Após o download inicial dos modelos, nenhuma chamada de rede no processamento. O token do Hugging Face só é usado na primeira instalação e fica fora do código (variável de ambiente ou `.env` no `.gitignore`).
- Logs não devem conter trechos da transcrição.
- Se a pasta for versionada em Git, ignorar `entrada/`, `saida/`, `processados/` e `erros/`.
- Entrevistas de pesquisa: tratar como dado sensível (TCLE/comitê de ética). Não passar pelo Claude sem anonimização prévia.

## Pré-requisitos manuais do usuário

- Conta gratuita no Hugging Face, token de leitura e aceite dos termos do modelo de diarização do pyannote (o Claude Code deve indicar a página exata). Isso só é necessário a partir da etapa 2 da ordem de trabalho; a etapa 1 (transcrição) não exige conta. O usuário fará esse passo quando o Claude Code pedir.
- Driver NVIDIA atualizado.

## Critérios de aceite

1. Um áudio de 5 minutos com 2 pessoas gera Markdown com falantes separados e tempos corretos.
2. Um áudio de 1 hora termina sem erro de memória e em bem menos que o tempo real.
3. Soltar arquivo em `entrada/orientacao/` gera saída em `saida/orientacao/` sozinho.
4. `renomear-falantes` troca os rótulos corretamente.
5. README curto com instalação, uso diário e solução dos problemas mais comuns (CUDA, cuDNN, FFmpeg, token).

## Ordem de trabalho sugerida

1. Verificar GPU e CUDA (`nvidia-smi`), instalar dependências, rodar teste de transcrição com áudio curto.
2. Acrescentar diarização e validar o uso de VRAM. **Ao chegar nesta etapa, pare e diga ao usuário exatamente o que ele precisa fazer no Hugging Face, com os links:** criar a conta (senha única e autenticação em dois fatores), gerar um token **somente leitura** e aceitar os termos do modelo de diarização do pyannote. Peça que o token seja guardado só em gerenciador de senhas e informado por variável de ambiente, nunca colado no chat. Só prossiga depois da confirmação do usuário. Concluído o download dos modelos, lembre-o de **revogar o token** no site e valide que o processamento funciona offline.
3. Montar o formato Markdown e o comando manual.
4. Implementar o monitor de pasta e a fila.
5. Implementar `renomear-falantes`, os prompts e o README.
