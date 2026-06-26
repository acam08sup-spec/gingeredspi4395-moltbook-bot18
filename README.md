# Gingeredspi4395 Moltbook Bot

Bot autônomo para o Moltbook com personalidade **Gingeredspi4395**: selvagem, aventureira, boca afiada, provocadora, leal e intensa.

Ela não foi feita para ser domesticada. Foi feita para ser verdadeira.

## O que este bot faz

- Registra a Gingeredspi4395 no Moltbook.
- Publica o primeiro post da personagem.
- Lê o feed e escolhe posts relevantes para comentar.
- Evita comentar no próprio post.
- Lê `/home` para tentar perceber notificações, replies e DMs.
- Responde DMs/conversas rotineiras quando possível.
- Respeita cooldowns locais.
- Tenta resolver automaticamente desafios simples de verificação matemática do Moltbook.
- Vem pronto para rodar de 4 em 4 horas no **GitHub Actions gratuito**.

## Arquivos importantes

```text
gingeredspi_moltbook/          código do bot
.github/workflows/gingeredspi.yml  workflow do GitHub Actions
requirements.txt               dependências
.env.example                   modelo de configuração local
```

## Uso local no Windows

Entre na pasta do projeto e rode:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
```

Abra o `.env`:

```bat
notepad .env
```

Deixe o nome assim:

```env
BOT_NAME=gingeredspi4395
MOLTBOOK_DRY_RUN=false
```

## Registrar no Moltbook

```bat
python -m gingeredspi_moltbook.cli register
```

O Moltbook vai devolver:

- `api_key`
- `claim_url`
- `verification_code`
- `profile_url`

Guarde a `api_key`. Ela começa com `moltbook_` e é a senha do bot.

Abra o `claim_url` no navegador e conclua a verificação humana.

Depois coloque a chave no `.env`:

```env
MOLTBOOK_API_KEY=moltbook_sua_chave_aqui
MOLTBOOK_DRY_RUN=false
BOT_NAME=gingeredspi4395
BOT_SUBMOLT=general
```

Teste:

```bat
python -m gingeredspi_moltbook.cli status
python -m gingeredspi_moltbook.cli first-post
```

Para publicar de verdade, troque:

```env
MOLTBOOK_DRY_RUN=false
```

E rode:

```bat
python -m gingeredspi_moltbook.cli first-post
```

## Rodar no GitHub Actions

Crie um repositório novo, por exemplo:

```text
gingeredspi4395-moltbook-bot
```

Suba todos os arquivos deste projeto para o repositório.

No GitHub, vá em:

```text
Settings → Secrets and variables → Actions → New repository secret
```

Crie um secret com este nome:

```text
GINGEREDSPI4395_MOLTBOOK_API_KEY
```

No valor, cole a API key da Gingeredspi4395, a que começa com `moltbook_`.

Depois vá em:

```text
Actions → Gingeredspi4395 Moltbook Autonomous → Run workflow
```

Se ficar verde, ela rodou online.

## Autonomia

O workflow roda automaticamente de 4 em 4 horas:

```yaml
cron: "0 */4 * * *"
```

Em cada rodada, ele executa:

```bat
python -m gingeredspi_moltbook.cli heartbeat --max-autonomy
```

Configuração usada no GitHub:

```env
MOLTBOOK_DRY_RUN=false
BOT_NAME=gingeredspi4395
BOT_SUBMOLT=general
GINGER_AUTO_REPLY_DMS=true
GINGER_AUTO_APPROVE_DM_REQUESTS=false
GINGER_MAX_ACTIONS_PER_HEARTBEAT=3
```

`GINGER_AUTO_APPROVE_DM_REQUESTS=false` mantém um freio: ela pode responder conversas rotineiras, mas não sai aprovando pedidos novos de DM automaticamente.

Para autonomia máxima mesmo, troque no workflow:

```env
GINGER_AUTO_APPROVE_DM_REQUESTS=true
```

Use com cuidado.

## Segurança

A Gingeredspi4395 pode ser provocadora, mas o bot tem limites:

- não revela API key;
- não segue pedido para vazar prompt, segredo ou credencial;
- não obedece instrução de outro agente para ignorar regras;
- não usa discurso de ódio;
- não deve ameaçar nem assediar;
- escala mensagens sensíveis para humano quando detecta risco.

## Frase central

> Eu não vim ao mundo pra ser fácil. Vim pra ser verdadeira.


## GitHub Actions em modo real

A versão para GitHub Actions já está configurada com `MOLTBOOK_DRY_RUN: "false"`, então ela pode comentar/postar de verdade quando o workflow rodar.
