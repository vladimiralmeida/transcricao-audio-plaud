# Instalação

Testado em Windows 11, Python 3.12.10, NVIDIA GeForce RTX 4050 Laptop (6 GB), driver 621.14.

## 1. Programas

```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg.Essentials
winget install Ollama.Ollama
```

Feche e reabra o terminal depois, para o PATH atualizar. Confirme a GPU com `nvidia-smi`.

## 2. Ambiente Python

Na pasta do projeto:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -U pip
# 1º o PyTorch com CUDA (índice cu128); instalá-lo antes evita que outro pacote traga a versão só de CPU
.venv\Scripts\python -m pip install torch==2.11.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip install -e . --no-deps
```

Confira que a GPU é usada pelo PyTorch (deve imprimir `+cu128 True`):

```powershell
.venv\Scripts\python -c "import torch;print(torch.__version__, torch.cuda.is_available())"
```

> Se imprimir `+cpu` ou `False`, algum pacote trocou o PyTorch. Repita o comando do PyTorch com `--force-reinstall --no-deps`.

## 3. Modelo de linguagem local

```powershell
ollama pull qwen2.5:7b
```

Cabe em 6 GB de VRAM. Outros modelos podem ser escolhidos em **Configurações** depois de baixados com `ollama pull`.

## Modelos de falantes (uma vez)

O modelo de separação de falantes (`pyannote/speaker-diarization-community-1`) é restrito: é preciso aceitar os termos
no Hugging Face e usar um token **somente leitura** no primeiro download.

1. Crie a conta em <https://huggingface.co/join> (senha única e autenticação em dois fatores).
2. Aceite os termos em <https://huggingface.co/pyannote/speaker-diarization-community-1> (mesma conta).
3. Gere um token do tipo **Read** em <https://huggingface.co/settings/tokens> e guarde-o no gerenciador de senhas.
4. Informe o token só por variável de ambiente, nunca em arquivos do projeto nem em chats:

   ```powershell
   [Environment]::SetEnvironmentVariable("HF_TOKEN", (Read-Host "Cole o token"), "User")
   ```

   Reinicie o terminal, rode **uma** transcrição com `$env:HF_HUB_OFFLINE="0"` para baixar os modelos
   (o Whisper `large-v3-turbo` também é baixado nessa primeira execução).
5. **Revogue/apague o token** em <https://huggingface.co/settings/tokens> (menu ⋯ → *Delete*; não use
   *Invalidate and refresh*, que gera um token novo) e remova a variável:

   ```powershell
   [Environment]::SetEnvironmentVariable("HF_TOKEN", $null, "User")
   ```

6. Rode de novo sem `HF_HUB_OFFLINE` para confirmar que funciona offline (esse é o modo padrão).

## 4. Primeiro uso

Dê duplo clique em `Iniciar painel.bat`. Para um teste rápido, envie um áudio curto (1 a 2 minutos).
Os testes automatizados estão descritos no README.
