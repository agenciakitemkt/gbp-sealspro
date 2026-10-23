# SealsPro: auditor de perfil do Google (GBP)

App local (Python, FastAPI e SQLite) que audita perfis do Google Business Profile e gera relatórios em PDF. Também tem uma extensão do Chrome para a pré análise de perfis de terceiros, a análise de ranking em grade, a busca de leads e o agendamento de postagens.

A especificação completa, com as regras de nota de cada item e as decisões técnicas, está em [CLAUDE.md](CLAUDE.md).

## Instalação

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
```

O relatório em PDF precisa do Google Chrome instalado. Se ele estiver fora do lugar padrão, informe o caminho na variável `GBP_CHROME`.

## Acesso ao Google

1. Crie um projeto no Google Cloud e ative as APIs do Business Profile (Account Management, Business Information e a API v4 de avaliações, mídia e postagens). O Google exige um pedido de cota para essas APIs.
2. Crie um client OAuth do tipo "Desktop" e preencha `GBP_CLIENT_ID` e `GBP_CLIENT_SECRET` no `.env`.
3. Faça o login: `./.venv/bin/python fase0.py login`. O refresh token é gravado no `.env`.

Se o app OAuth ficar em modo "Testing", o refresh token vence em 7 dias. Publique a tela de consentimento como "In production" para uso pessoal.

## Uso

```bash
./.venv/bin/python serve.py          # abre o app em http://127.0.0.1:8000
./.venv/bin/python coletar.py --help # comandos de linha (sincronizar, coletar, relatorio...)
```

A extensão do Chrome fica em `extension/`. Para instalar e configurar, veja a seção 13.10 do CLAUDE.md.

## Testes

```bash
./.venv/bin/python -m unittest discover -s tests -t .
cd extension && node --test tests/*.test.js
```

## Dados

Tudo o que é coletado fica em `data/`, fora do git, e pode conter dados de clientes. Nunca suba essa pasta nem o `.env`.

## Aviso

As curvas de nota são hipóteses calibradas contra uma ferramenta comercial (seções 4, 5 e 12 do CLAUDE.md) e ainda não foram validadas. A pré análise, o ranking e a busca de leads leem páginas do Google Maps pelo navegador, o que os termos do Google não permitem para extração automatizada. Use com moderação e por sua conta.
