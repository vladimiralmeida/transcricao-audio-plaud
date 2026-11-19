# Roadmap

## Feito
- Pipeline local (Whisper + pyannote), CLI e monitor de pasta.
- Painel web: perfis, falantes (número, nome, papel), progresso e VRAM ao vivo, editor com áudio, histórico com busca.
- Documento contextualizado com LLM local, prompts editáveis, anonimização, exportação (Markdown, Word, Obsidian).

## Ideias
- **Voz cadastrada:** reconhecer automaticamente pessoas recorrentes (o orientador) por impressão de voz.
- **Importar `.md` antigos** gerados pela CLI para o histórico do painel.
- **Revisão assistida:** destacar trechos de baixa confiança do Whisper para conferir primeiro.
- **Glossário por projeto:** lista de nomes e termos técnicos para melhorar a transcrição (`hotwords`) e corrigir grafias.
- **Anonimização mais forte:** reconhecimento de nomes próprios por modelo local, além das regras.
- **Instalador:** script único que cria o venv, instala as dependências e testa a GPU.
- **Comparar modelos:** alternar entre `large-v3-turbo` e `large-v3` por trabalho no painel.
- **Atalho na área de trabalho** e inicialização automática opcional com o Windows.
