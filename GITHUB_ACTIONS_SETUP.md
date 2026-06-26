# Como colocar Gingeredspi4395 no GitHub Actions gratuito

1. Crie um repositório novo no GitHub.
2. Suba todos os arquivos deste projeto.
3. Registre a bot localmente com:

```bat
python -m gingeredspi_moltbook.cli register
```

4. Abra o `claim_url` e reivindique a bot.
5. Copie a API key que começa com `moltbook_`.
6. No GitHub, vá em:

```text
Settings → Secrets and variables → Actions → New repository secret
```

7. Crie o secret:

```text
GINGEREDSPI4395_MOLTBOOK_API_KEY
```

8. Cole a API key como valor.
9. Vá em:

```text
Actions → Gingeredspi4395 Moltbook Autonomous → Run workflow
```

10. Se o workflow ficar verde, a Gingeredspi4395 está rodando online.

Ela vai acordar sozinha a cada 4 horas.


## Modo real

O workflow já vem configurado com `MOLTBOOK_DRY_RUN: "false"`, então quando rodar no GitHub ele age de verdade.
