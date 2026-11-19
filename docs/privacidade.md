# Privacidade

## Princípios

- **Sem rede no processamento.** `HF_HUB_OFFLINE=1` é o padrão; os modelos são baixados uma única vez. O único tráfego
  do app é local (`127.0.0.1`): navegador ↔ painel e painel ↔ Ollama próprio.
- **Sem telemetria**, sem fontes, scripts ou gráficos vindos de CDN.
- **Logs sem conteúdo.** Registram nome do arquivo, etapas e tempos. O `.log` em `erros/` guarda só a pilha técnica.
- **Nada versionado.** `entrada/`, `saida/`, `processados/`, `erros/`, `dados/`, bancos e áudios estão no `.gitignore`.
- **Token do Hugging Face** só na primeira instalação, por variável de ambiente, e depois revogado.

## Onde ficam seus dados

| O quê | Onde |
|---|---|
| Áudios originais | `entrada/` → `processados/<perfil>/` (ou `erros/<perfil>/`) |
| Transcrições (.md) | `saida/<perfil>/` |
| Texto editável, falantes, documentos, tabela de anonimização | `dados/app.db` |
| Áudios enviados pelo painel (até serem processados) | `dados/uploads/` |

“Remover do histórico” apaga só o registro no banco; arquivos `.md` e de áudio permanecem. Apague-os manualmente se
quiser eliminar a gravação.

## Entrevistas de pesquisa (dado sensível)

Trate conforme o TCLE e o comitê de ética. No painel:

- O texto enviado ao LLM local e o prompt “Copiar para o Claude” usam sempre a versão **anonimizada**; o botão de copiar
  é bloqueado para entrevistas sem anonimização.
- A anonimização é **por regras e não é infalível**: troca nomes informados e padrões (e-mail, CPF, CNPJ, telefone, CNJ).
  Não reconhece sozinha nomes não listados, apelidos, e dados indiretos (cargo + cidade, por exemplo).
  **Sempre revise o texto anonimizado** antes de usá-lo fora do computador.
- A tabela de correspondência (original ↔ código) fica só no banco local: não a compartilhe.

## O que pode sair do computador

Só o que você decidir: *Copiar prompt para o Claude* (texto na área de transferência), downloads (.md/.docx) e a
exportação ao Obsidian. Se o seu cofre do Obsidian estiver sincronizado em nuvem, a nota exportada também será.
