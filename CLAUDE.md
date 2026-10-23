# Auditor de Perfil do Google (GBP): Análise Completa (spec v0.1)

Projeto SealsPro. Inspirado no comportamento observável da "Análise Completa" do GBP Check. Não copiar código, textos, marca nem identidade visual do original: os textos das explicações, nomes e visual devem ser próprios.

Origem das informações: observação de uma conta no GBP Check (tela, dados devolvidos pelo servidor) e dois PDFs de exemplo (perfil de referência e uma imobiliária). Tudo que for hipótese está marcado como (hipótese) ou (calibrar).

## 1. Escopo da primeira versão

Dentro:
- Entrar com a conta Google, listar as contas e locais que o usuário administra via API do Google Business Profile.
- Rodar a análise de um local e mostrar o resultado: nota geral, contadores e lista de 21 itens.
- Guardar cada análise (histórico), para comparar depois.

Fora (fases futuras): Pré Análise, ranking/mapa de calor, concorrentes, resposta a avaliações com IA, relatório em PDF, insights, propostas, cards de avaliação, proteção de perfil.

## 2. Fluxo de uso

1. Sincronizar locais: busca contas e locais no Google e mostra progresso. (o original faz isso em segundo plano com barra de progresso)
2. Escolher um local no seletor do topo.
3. A tela mostra o último resultado guardado, com "Última atualização: há X dias".
4. Botão "Analisar" roda uma análise nova e substitui a exibida, mantendo a antiga no histórico.
5. Botão "Histórico" (tela `/historico`): linha do tempo das análises do local e gráfico da nota geral. Daí se compara duas análises quaisquer (tela `/comparar`). Ver Fase 5a, na seção 9.

## 3. Tela de resultado

- Cabeçalho: nome do local e quem está logado.
- Medidor (gauge) de 0 a 100 com a nota geral e o rótulo: vermelho, amarelo ou verde. Faixas lidas do desenho (calibrar): vermelho até cerca de 60, amarelo de 60 a 80, verde acima de 80. Observado: 95 = Bom, 75 = Razoável.
- Três contadores: Fraco (métricas que precisam de atenção), Razoável (potencial de melhoria), Bom (excelente).
- Lista de itens ordenada por nota crescente (os piores primeiro). Cada item: ícone (x ou check), título, explicação do porquê importa, situação atual com números, barra de 3 faixas (Fraco, Razoável, Bom) com marcador no percentual.
- Painel lateral com cartão do perfil: nome, nota média e total de avaliações, categoria, cidade, links "Ver na Pesquisa" e "Ver no Maps", descrição, endereço, telefone, horário, distribuição de estrelas (5 a 1).

## 4. Modelo de nota

Observado em quatro valores de nota: 0, 50, 66 e 100.
- Status por nota (hipótese consistente com tudo que vi): abaixo de 50 = Fraco, de 50 a 99 = Razoável, 100 = Bom. Derivar o status da nota, não guardar separado (no original o campo de status às vezes diverge da nota).
- Nota geral = piso de (bons × 100 + razoáveis × 50) / total de itens avaliados (fracos pesam 0). Confirmada no original em 10 locais e na Pré Análise; a média simples das notas dos itens não é a fórmula (perfil de referência: média 96, original 95). Itens indisponíveis (coleta falhou) e itens que não se aplicam ao perfil ficam fora do total.

## 5. Catálogo dos 21 itens da Análise Completa

Colunas: id interno do original, título, regra observada. Onde só vi o caso "bom", o limite parcial é desconhecido (calibrar).

| id | Item | Regra observada |
|----|------|-----------------|
| 0 | Número de telefone | Tem telefone definido |
| 1 | Website | Tem endereço de site definido |
| 2 | Horário de funcionamento | Horário normal definido |
| 3 | Horário especial | Pelo menos um período de horário especial no ano corrente (início ou fim do período no ano da análise). Fonte: `specialHours` |
| 4 | Descrição da empresa | Mínimo recomendado 50 caracteres (585 = 100) |
| 5 | Mídia: vídeos | Mínimo 3. Curva medida: 0 = 0, 1 = 50, 2 = 66, 3 ou mais = 100 |
| 6 | Mídia: logotipo | Existe mídia da categoria PROFILE. A API devolve essa mídia com data 1970-01-01: ignorar a data |
| 7 | Mídia: foto de capa | Existe foto de capa |
| 14 | Mídia total pelo proprietário | Mínimo 3 (8 = 100) |
| 15 | Mídia total | Mínimo 3 (9 = 100) |
| 16 | Mídias publicadas por clientes | Recomendado 3. Mesma curva dos vídeos: 0 = 0, 1 = 50, 2 = 66, 3 ou mais = 100 |
| 17 | Avaliações: quantidade | Mínimo 3 (21 = 100) |
| 18 | Avaliações: média | Avaliada como "normal" com 5,0 (limites a calibrar) |
| 19 | Avaliações sem resposta | Pela quantidade de avaliações sem resposta (hipótese): 0 = 100, 1 = 66, 2 = 33, 3 ou mais = 0. Pontos medidos (sem resposta → nota): 0 → 100, 1 → 66 (1 de 25), 4 → 0 (4 de 34), 8 → 0 (8 de 25, avaliações de 0 a 3 dias). Com 2 e 3 não há medida. A regra por percentual não foi descartada. A idade da avaliação não parece contar |
| 20 | Avaliações sem comentários | Percentual sem comentário. Medido: 27,3%, 35,7% e 38,6% = 100 (Completa); 44% = 50 (Pré Análise). O limite do "bom" fica entre 38,6% e 44%: hipótese de 40% sem comentário (60% com comentário); a nota cai a partir daí, passando por (44%, 50) |
| 25 | Serviços | Tem serviços cadastrados. Não se aplica quando a categoria não aceita lista de serviços (hipótese apoiada em 1 caso, um local de energia solar: a API não devolve `metadata.canModifyServiceList`, que vem `true` nos demais locais; a API omite booleanos falsos). Sem serviços mas com o campo `true` continua valendo e dá 0 |
| 26 | Data de fundação | `openInfo.openingDate` preenchido |
| 27 | Nome do negócio | Máximo recomendado 98 caracteres (34 = 100) |
| 28 | Avaliações: comparativo | Compara média das avaliações recentes com a histórica: aumentando, estável ou diminuindo |
| 29 | Data da última postagem | Hipótese em degrau: 100 até 30 dias, 0 acima. Pontos medidos na Completa (dias → nota): 1 a 10 dias → 100; 38 → 0; 43 → 0. O corte fica entre 11 e 37 dias; 30 vem do mínimo recomendado na Pré Análise |
| 30 | Data da última mídia do proprietário | Hipótese em degraus: 100 até 59 dias, 50 de 60 a 119, 0 de 120 em diante. Pontos medidos na Completa (dias → nota): 8 a 57 dias → 100; 86 → 50; 152 → 0 (Pré Análise: 60 dias → 50). O 100 vai até algum ponto entre 57 e 85 dias; o 0 começa em algum ponto desconhecido entre 87 e 151 dias |

Decisões da Fase 0 (a partir do que a API devolveu):
- Distribuição de estrelas, nota média e contagem de avaliações vêm da lista completa de avaliações (paginada), não do resumo da API. O total do resumo é guardado só para conferir se a lista veio completa.
- Logotipo = mídia PROFILE; data de fundação = `openInfo.openingDate`; horário especial = ao menos um período no ano corrente (itens 6, 26 e 3 acima).
- `starDistribution` do contrato segue a ordem do painel: posição 0 = 5 estrelas, posição 4 = 1 estrela.

Observação: o mesmo conceito pode pontuar diferente entre Completa e Pré (2 vídeos: 66 na completa, 50 na pré). Cada item precisa da sua própria curva, não de uma fórmula única de proporção.

## 6. Dados necessários e fonte provável (API do Google Business Profile)

Verificar na documentação atual antes de codar. Os endpoints mudam e alguns ficam em APIs legadas.

| Dado | Fonte provável |
|------|----------------|
| Contas e locais | Account Management API e Business Information API |
| Telefone, site, descrição, categoria, endereço, horários normais e especiais, serviços, data de abertura (fundação) | Business Information API, `locations.get` e `list` com `readMask` |
| Avaliações (nota, comentário, resposta, data) e distribuição de estrelas | API de avaliações (v4 legada) |
| Mídia (fotos, vídeos, logotipo, capa, mídia de clientes, datas) | API de mídia (v4 legada) |
| Postagens e datas | API de postagens locais (v4 legada) |

## 7. Contrato de saída (formato próprio)

```json
{
  "location": {
    "id": "", "name": "", "category": "", "city": "", "address": "",
    "phone": "", "website": "", "description": "", "rating": 0.0,
    "reviewCount": 0, "starDistribution": [0, 0, 0, 0, 0],
    "hours": {}, "mapsUrl": "", "searchUrl": "", "logoUrl": "", "coverUrl": ""
  },
  "overall": { "score": 0, "good": 0, "fair": 0, "bad": 0 },
  "items": [
    {
      "id": "videos",
      "title": "",
      "score": 0,
      "status": "bad|fair|good",
      "message": { "template": "", "vars": { "current": 2, "recommended": 3 } }
    }
  ],
  "analyzedAt": ""
}
```

O original manda a mensagem como texto com HTML dentro. Aqui, usar template mais variáveis, para facilitar tradução e renderização.

## 8. Arquitetura sugerida (padrão, pode trocar)

- Python 3.12, FastAPI, SQLite, front simples (Jinja com HTMX). Poucas peças, motor de nota fácil de testar.
- Camadas separadas: `collector` (fala com o Google e devolve o perfil normalizado), `scoring` (função pura: perfil entra, itens saem), `storage` (histórico), `web` (telas).
- OAuth do Google com o escopo `https://www.googleapis.com/auth/business.manage`. Tokens guardados localmente e fora do git.
- Cuidado conhecido: app OAuth em modo "Testing" emite refresh token que expira em poucos dias. Confirmar o estado de publicação da tela de consentimento.
- Um arquivo por item de nota, com teste próprio.
- Camadas acrescentadas depois: `history.py` (evolução e comparação de análises, Fase 5a), `report/` (relatório em PDF, Fase 6a, e o comparativo antes e depois), `simulator.py` e `web/simulador.py` (simulador de avaliações, seção 14) e, para a Pré Análise (seção 12), `scoring/pre/` (regras), `collector_pre/` (coleta e adaptador) e `calibration_pre.py` (comparação com o original) e, para a Análise de Ranking (seção 16), `ranking/` (grade, leitura de cada ponto, métricas e fluxo) e `web/ranking.py` e, para o agendamento de postagens (seção 17), `posts/` (o único pacote que escreve no Google) e `web/postagens.py` e, para a Busca de Leads (seção 18), `leads/` (região, grade, leitura, qualidade e fluxo) e `web/leads.py`.
- Dependências em dois arquivos: `requirements.txt` traz só o que o app precisa para rodar (`google-auth`, `google-auth-oauthlib`, `requests`, `fastapi`, `uvicorn`, `jinja2`), e `requirements-dev.txt` traz tudo isso mais o que só os testes usam (`httpx`, `pypdf`, `pypdfium2`, `pillow`). Para desenvolver e rodar a suíte: `python3 -m venv .venv && ./.venv/bin/pip install -r requirements-dev.txt`. Fora do Python, o relatório em PDF exige o Google Chrome instalado (ver Fase 6a).
- Dados locais (`data/`: coletas brutas, banco, backups do banco, referências, relatórios em PDF e prints) têm dados de clientes e ficam fora do git (`data/`, `data/backups/`, `data/raw/` e `*.db` no `.gitignore`). A suíte de testes não pode tocar neles: `tests/__init__.py` aponta o `storage` para uma pasta temporária e o teste `test_zz_dados_reais_intactos` (o último a rodar) falha se qualquer arquivo de `data/` mudar durante a execução.

### Versão do motor e do config

Cada análise guarda a versão do motor (`ENGINE_VERSION`, em `scoring/version.py`), o hash do config e um snapshot do config, para que mudanças futuras nas curvas não distorçam a comparação histórica.

**Regra: suba `ENGINE_VERSION` sempre que a lógica do motor mudar**, isto é, qualquer alteração em `scoring/` que possa mudar a nota de um perfil idêntico com o mesmo config: regra de um item, o dado que o item considera, a fórmula da nota geral, o cálculo do status, item novo ou removido. Não precisa subir para: mudança só de números em `scoring/config.py` (o hash do config muda sozinho e o gráfico já marca a troca), texto de mensagem que não altera nota, e mudanças fora de `scoring/`.

**Trava automática (impressão digital do código).** A versão é manual, então um teste (`tests/scoring/test_engine_fingerprint.py`) confere uma impressão digital do código de `scoring/` registrada em `tests/scoring/engine_fingerprint.json` junto com a `ENGINE_VERSION` da época. Se a lógica mudar sem a versão subir, a suíte falha e a mensagem lista os arquivos alterados e as duas saídas:
1. A mudança altera a nota que um perfil recebe: subir `ENGINE_VERSION` e registrar a nova impressão.
2. A mudança é só cosmética (renomear variável, reorganizar código, sem efeito na nota): não subir a versão e apenas registrar a nova impressão.

O registro é atualizado com `./.venv/bin/python -m tests.code_fingerprint --update` (sem `--update`, o mesmo comando só confere e explica). O teste também falha se a versão subir sem a impressão ser registrada, ou se a versão mudar sem mudança no código, para que o registro sempre corresponda à versão atual.

**Dois motores, duas versões.** A Pré Análise (seção 12) tem motor próprio em `scoring/pre/`, com `PRE_ENGINE_VERSION` em `scoring/pre/version.py` e registro próprio em `tests/scoring/pre_engine_fingerprint.json`. A impressão da Completa cobre `scoring/` menos `scoring/pre/`; a da Pré cobre `scoring/pre/` mais os arquivos compartilhados (`SHARED` em `tests/code_fingerprint.py`: `scoring/base.py` e `scoring/curves.py`). Os compartilhados entram **nas duas** impressões: mudar a lógica de `base.py` (status, nota geral, contadores) ou de `curves.py` faz as duas travas falharem e exige decidir as duas versões. Um teste confere que tudo o que `scoring/pre/` importa de fora dela está em `SHARED`. O `--update` registra os dois motores de uma vez e diz, para cada um, se o código mudou e se a versão subiu. O hash do config da Pré inclui os valores compartilhados de `scoring/config.py` (`BAD_BELOW`, `GOOD_AT`, `OVERALL`, `OVERALL_BANDS`).

O que a impressão considera: o código de `scoring/` em forma canônica (árvore sintática). **Não entram:** comentários, docstrings, formatação, textos de mensagem e títulos (qualquer texto com espaço e letras), `scoring/config.py` e `scoring/pre/config.py` (cada config tem hash próprio), `scoring/version.py` e `scoring/pre/version.py`. Limites conhecidos: um texto de uma palavra só conta como lógica, renomear variável conta como mudança (cai na saída 2), e mudanças fora de `scoring/` (como `collector/normalize.py`, que monta o perfil que o motor lê) não são cobertas: se elas mudarem a nota, aplique a regra de subir a versão por conta própria.

Procedimento ao mudar a lógica de um item:
1. Alterar o item e o teste dele.
2. Subir `ENGINE_VERSION` (por exemplo, de `"1"` para `"2"`).
3. Registrar a impressão: `./.venv/bin/python -m tests.code_fingerprint --update`.
4. Rodar toda a suíte e `coletar.py calibrar --so-divergencias` para ver o efeito contra o original.
5. Registrar o que mudou e por quê no CLAUDE.md (seção 5 e lacunas da Fase 4).
6. A partir daí as análises novas levam a nova versão; as antigas mantêm a delas e o gráfico marca a mudança. Para comparar sem distorção, usar em `/comparar` o "Reavaliar as duas com o motor atual" (calculado em memória a partir dos brutos, não grava nada).
7. Nada é apagado nem recalculado no banco: `coletar.py retroativas` só cria análises para coletas brutas que ainda não têm uma.

## 9. Fases

0. Verificar acesso: projeto no Google Cloud com a API ativa e cota aprovada, login OAuth, listar contas e locais, ler os campos da seção 6.
1. Coletor: gerar o perfil normalizado de um local e guardar o JSON bruto.
2. Motor de nota: 21 itens com testes usando o perfil de referência como caso de referência.
3. Tela de resultado (seção 3).
4. Histórico e comparação com o GBP Check original em várias contas, para calibrar curvas e a nota geral. **Estado: calibrada com dados de 2026-10-08, ainda não validada.**
   - O que está feito: histórico de análises (SQLite), botão "Sincronizar locais", comando `calibrar` e curvas ajustadas. Com a referência `gbpcheck_original_2026-10-08.json` (10 locais, análises do mesmo dia) o motor reproduz o original em todos os itens e na nota geral. Isso é ajuste aos mesmos pontos, não validação: as curvas dos itens 19, 29 e 30 e o limite do item 20 são hipóteses montadas com esses pontos.
   - Lacunas abertas:
     - Item 30 (última mídia do proprietário): o fim do 100 fica entre 57 e 85 dias (59 é hipótese) e o início do 0 fica entre 87 e 151 dias (120 é hipótese; o 50 foi medido só com 86 dias).
     - Item 29 (última postagem): sem ponto medido entre 11 e 37 dias (medido: 10 dias = 100; 38 e 43 dias = 0). Com o limite de 30 dias da Pré Análise, a incerteza prática é a faixa de 29 a 37 dias.
     - Item 19 (avaliações sem resposta): nenhum ponto com 2 sem resposta (medidos: 0, 1, 4 e 8); 3 também não foi medido. A regra por percentual não foi descartada.
     - Item 20 (sem comentário): o limite do "bom" fica entre 38,6% e 44% (40% é hipótese).
   - Como repetir a comparação com o original (use análises do mesmo dia; a diferença de horas pesa nos itens 19, 29 e 30):
     1. Baixar uma referência nova: rodar a Análise Completa no GBP Check para os locais e salvar o resultado em `data/reference/gbpcheck_original_AAAA-MM-DD.json`, no formato do arquivo atual (lista `locais`, cada um com `name`, `businessId`, `analisadoHa`, `overall`, `counts`, `rating`, `reviews`, `starsDe1a5` e `scores`). Entre arquivos da mesma família vale o de data mais recente; os antigos ficam como histórico (`--incluir-historico` compara também).
     2. Sincronizar e coletar logo em seguida: `./.venv/bin/python coletar.py sincronizar` (atualiza a lista de locais; também há o botão na tela) e `./.venv/bin/python coletar.py coletar --todos` (refaz a coleta dos locais ativos, que é a que o `calibrar` usa).
     3. Rodar `./.venv/bin/python coletar.py calibrar --so-divergencias`. Ler as divergências por local e item e os valores brutos dos itens 19, 29 e 30.
     4. Se um local novo divergir, não mexer nas curvas de imediato: registrar o par (valor bruto, nota do original) em `observed` no `scoring/config.py`, conferir se contradiz as hipóteses atuais e só então ajustar. Divergência em locais que não entraram na montagem das curvas é o que valida (ou derruba) as hipóteses.
5. Fase 5a, evolução ao longo do tempo (só Análise Completa). **Feita.**
   - Banco: `analyses` guarda `engine_version`, `config_hash`, `config_json` (snapshot do config) e `kind` (`real` ou `retroativa`). A migração é automática e antes dela o banco é copiado para `data/backups/gbp-<data>-antes-da-migracao.db`. Análises anteriores à Fase 5a ficam como reais, com versão "desconhecida". Nenhuma análise é apagada.
   - Análises reais vêm do botão Analisar e de `coletar.py coletar`. As **retroativas** são criadas por `coletar.py retroativas` a partir dos brutos em `data/raw`: calculadas com o motor atual, com a data da coleta do bruto, sem duplicar (idempotente). Elas só aparecem no histórico: a tela principal e o "Última atualização" consideram apenas análises reais.
   - `/historico?local=`: tabela (data, tipo, nota geral, contadores e versão) e gráfico SVG da nota geral guardada. Ponto cheio = análise real, ponto vazio = retroativa, losango com linha tracejada = mudança de versão do motor ou do config. Os pontos ficam igualmente espaçados, na ordem das análises.
   - `/comparar?a=&b=`: itens que mudaram de nota ou status e o que mudou nos dados (contagens e datas de avaliações, mídias, vídeos e postagens; antes e depois em texto só para nome e descrição; nunca o texto de avaliações de clientes). Se as versões diferem, avisa e oferece reavaliar as duas com o motor atual, em memória (`reavaliar=1`), sem gravar.
   - Item cuja coleta falhou aparece como "Não foi possível coletar este dado." e fica fora da nota; isso vale também para análises guardadas com o texto antigo.
   - Fora do escopo desta fase: relatório em PDF e Pré Análise.
6. Fase 6a, relatório em PDF da Análise Completa para entregar ao cliente. **Feita.**
   - Público e identidade: o dono do perfil, em português claro e sem jargão técnico. Cores da SealsPro (fundo `#0B0B0D`, verde `#14B8A6`, azul `#818CF8`, texto `#F8FAFC`), títulos em Space Grotesk e texto em Inter.
   - Conteúdo (A4, rodapé com logo, agência, data da análise e página em todas as páginas): capa com o nome do local e a data; resumo com o medidor, os três contadores (Fraco, Razoável, Bom), duas frases sobre o que a nota significa e a nota média e o total de avaliações; itens do pior para o melhor, cada um com título, situação com números, barra de faixa e orientação ("O que fazer" para o que está abaixo do ideal, "Como manter" para o que está bom); evolução da nota; nota de rodapé "Critérios próprios da SealsPro".
   - Regras: usa só a **última análise real** do local (nunca retroativa); nunca mostra texto de avaliações de clientes; por item mostra só status e barra, e o número de 0 a 100 aparece só na nota geral; itens indisponíveis ou que não se aplicam ficam fora da nota. A **evolução** só aparece com análises reais da versão atual do motor e do config em **pelo menos 2 datas diferentes** (data de Brasília); duas análises no mesmo dia não bastam e a seção é omitida.
   - **Problemas da análise ficam só na tela, nunca no PDF (decisão do usuário, 2026-10-10).** Itens não avaliados, avisos da coleta e análise de versão anterior aparecem como aviso na tela de resultado; o PDF sai direto, sem pop-up, e não traz seção nem frase sobre isso (os itens não avaliados simplesmente não aparecem). A linha de comando continua imprimindo "ATENCAO".
   - **Dois PDFs**, no menu **Ações** da tela de resultado (o mesmo na Pré): **completo** (o descrito acima) e **resumido** (`modo=resumo`; `--resumo` na linha de comando; arquivo `Relatorio-Resumo-...`/`Pre-Analise-Resumo-...`). O resumido mostra capa, resumo com medidor e contadores e os itens **fechados**, uma linha cada, sem situação, barra nem orientação: os bons com o título; os Fracos e Razoáveis com o título **borrado**, como no PDF do GBP Check, e no fim um convite para falar com a agência. O título real dos itens com problema não entra no arquivo: no lugar vai um texto neutro do mesmo tamanho (`report/render.py`, `mask`), e o Chrome ainda grava o borrado como imagem. O resumido não traz o bloco de concorrência da Pré; a evolução da Completa continua.
   - Como gerar: menu **Ações** na tela de resultado (`/relatorio.pdf?local=` e `&modo=resumo`); ou pela linha de comando, `./.venv/bin/python coletar.py relatorio <local> [--saida PASTA] [--resumo]`, que grava `Relatorio-<local>-AAAA-MM-DD.pdf` em `data/relatorios/` (fora do git) e imprime o caminho.
   - **PDF de uma análise do histórico (2026-10-11):** na tela `/historico`, cada análise real tem os links "Completo" e "Resumido" (`/relatorio.pdf?local=&analise=<id>`; `coletar.py relatorio <local> --analise <id>`). É o mesmo relatório, com a análise escolhida no lugar da última, e a evolução vai só até a data dela. Retroativas não têm PDF. O número de cada análise (`#id`) aparece ao lado da data no histórico.
   - **PDF comparativo, antes e depois (2026-10-11), a "entrega final" para o cliente:** em `/historico`, marcar A e B e clicar em "Baixar comparativo (PDF)"; também em `/comparar` e por `coletar.py comparativo <id_A> <id_B> [--saida PASTA]`. Arquivo `Comparativo-<local>-AAAA-MM-DD-a-AAAA-MM-DD.pdf`. Montagem em `report/build_compare.py`, modelo `report/templates/comparativo.html` (estilo e macros comuns em `_estilo.html` e `_pdf_macros.html`), testes em `tests/test_report_compare.py`.
     - Decisões do usuário: só **Completa com Completa** (a Pré tem outros itens e regras); mostrar também os itens que **pioraram** ("Pontos de atenção"); **não dizer como** cada coisa foi feita.
     - Só análises **reais** do mesmo local; a mais antiga é o "antes", qualquer que seja a ordem pedida. As duas são **recalculadas com o motor atual** a partir dos brutos, em memória, sem gravar nada, para a diferença vir do perfil e não de mudança de critério. Sem o bruto, vale a nota guardada só se for da versão atual; senão, o PDF não é gerado e a mensagem explica.
     - Conteúdo: capa ("Evolução do perfil no Google", de/até), os dois medidores com a diferença em pontos, contadores antes → depois, frase-resumo, **números do perfil** (avaliações, nota média, sem resposta, fotos e vídeos da empresa, vídeos, mídias de clientes e postagens, com antes, depois e diferença; "sem resposta" subir conta como piora), itens por grupo ("Melhoraram", "Pontos de atenção", "Ainda podem melhorar", com status antes → depois e a situação de agora) e os que "continuaram bons" numa linha. A evolução aparece com 3 ou mais análises reais da versão atual no período.
     - Mesmas regras do relatório: sem nota por item, sem orientação, nunca texto de avaliações. Item não avaliado em uma das duas fica de fora (a linha de comando imprime "ATENCAO").
     - **Toda alteração conta como melhoria (decisão do usuário, 2026-10-11):** um item entra em "Melhoraram" se subiu de faixa **ou** se, sem cair de faixa, teve alguma mudança para melhor entre os dois brutos (descrição reescrita, nome, telefone, site, horários, data de fundação, serviços, logotipo ou capa trocados, fotos, vídeos e postagens novas, avaliações respondidas ou novas, nota média subindo). Cada item mostra uma linha com o que mudou e, se ficou na mesma faixa, a marca "Atualizado". Retirar algo não conta; faixa que caiu continua em "Pontos de atenção". A detecção fica em `report/changes.py` (fora de `scoring/`, não muda nota); a identidade de mídias, postagens e avaliações vem do `name`/`reviewId` da API. A frase da descrição diz que ela foi "otimizada para as buscas no Google e nas ferramentas de inteligência artificial".
     - **Fotos de clientes em destaque (decisão do usuário, 2026-10-11):** enquanto o item "Fotos e vídeos de clientes" não estiver Bom, o comparativo traz, antes dos itens, uma página "Sua parte" (exceção à regra de não orientar): quantas avaliações novas com foto faltam, que vale qualquer foto (sem rosto), que família e amigos podem avaliar (com o aviso de que o Google pode remover a avaliação se identificar que é de familiar ou amigo), que acrescentar foto a uma avaliação antiga não conta, o link para avaliar (`metadata.newReviewUri` do bruto; sem ele, o do `placeId`) e o botão "Compartilhar no WhatsApp" (`wa.me` com mensagem pronta). São os únicos links externos do PDF (só clicáveis, nada é carregado da internet; teste trava os dois destinos). Sem QR code por enquanto (decisão do usuário).
   - **Dependência do Chrome:** o PDF é gerado com o Google Chrome em modo headless, tudo na máquina, sem enviar dados para fora (`report/pdf.py`, função `html_to_pdf`, isolada para poder trocar o motor). O Chrome é procurado em `/Applications/Google Chrome.app`, em Chromium e no PATH; a variável de ambiente `GBP_CHROME` informa outro caminho. Sem ele, o relatório não é gerado e a mensagem diz o que fazer.
   - Fontes e logos em `assets/`: `logo-sealspro-horizontal.png` (capa e rodapé) e `logo-sealspro-simbolo.png` (detalhe da capa); `assets/fonts/` traz Inter e Space Grotesk (licença OFL, textos em `OFL-*.txt`) e um `LEIA-ME.md` com a origem (repositório do Google Fonts, baixadas uma vez) e como foram geradas as versões estáticas. As fontes são embutidas no PDF como TrueType e a geração é totalmente offline.
   - Textos: `report/texts.py` (situação e orientação dos 21 itens). Só orientação, sem prazo nem promessa de resultado, sem jargão; testes verificam isso. Mudar texto não exige subir `ENGINE_VERSION`, porque o texto fica fora de `scoring/`.
   - Testes (`tests/test_report.py`): geram o PDF de verdade e conferem A4, fontes embutidas, todas as seções, rodapé em todas as páginas e margens externas limpas (nada vaza); também conferem que o texto de avaliação de cliente nunca aparece. Pulam se não houver Chrome.
   - **Limite conhecido:** a nota e os status vêm das curvas da Fase 4, que ainda são **hipóteses** calibradas com dados de 2026-10-08 e **não validadas**. A nota de rodapé "Critérios próprios da SealsPro" indica que o critério é da agência, mas não torna as curvas validadas: ao entregar, tenha isso em mente e, para locais novos, rode o `calibrar` quando houver referência.
7. Pré Análise: ver seção 12 (fases próprias, de 0 a 4). **Fase 0 feita** (motor calibrado offline contra os 54 casos do original).

## 10. Critério de aceite da primeira versão

Rodando no perfil do perfil de referência, obter 21 itens, contadores 0 Fraco, 2 Razoável, 19 Bom, itens com problema em mídias de clientes (1 de 3) e vídeos (2 de 3), e nota geral dentro de 1 ponto da nota 95 do original.

## 11. Perguntas em aberto

- Resolvido: o acesso à API é do projeto Google Cloud do próprio usuário. Na Fase 0, confirmar o ID do projeto, quais APIs do Business Profile estão ativas e a cota de cada uma.
- Quais limites parciais de média de avaliações, descrição, nome e mídia? (coletar amostras variadas)
- Resolvido: nota geral = piso de (bons × 100 + razoáveis × 50) / itens avaliados (seção 4).
- Calibração: as lacunas abertas dos itens 19, 20, 29 e 30 e o procedimento para repetir a comparação estão na seção 9, Fase 4 (calibrada com dados de 2026-10-08, ainda não validada).
- Quantas contas e locais serão analisados e com que frequência?
- Pré Análise: perguntas próprias em 12.11.

## 12. Pré Análise (spec v0.1)

Origem: `data/reference/SPEC-pre-analise.md`, incorporada aqui. Mesmas regras da Análise Completa: não copiar código, textos, marca nem visual do GBP Check; os textos são próprios. Marcações: **medido** (vários pontos confirmam), **parcial** (a faixa é conhecida, mas o limite exato não), **hipótese** (poucos pontos).

Origem das informações, coletadas em 2026-10-09:
- **54 pré análises guardadas na conta do usuário no GBP Check**, lidas sem rodar análise nova, em `data/reference/pre_analises_original.json` (fora do git). Cada uma traz as notas do original por item (`items`), os totais (`stats`) e os dados brutos que ele usou (`pd`). O `id` de cada caso é um UUID v7 e dá o instante da análise (as 54 são de julho de 2026 em diante).
- **Leitura da extensão do GBP Check (v2.0.2)**, para entender a arquitetura.

### 12.1 Escopo da primeira versão

Dentro:
- Entrada: o negócio aberto no Google Maps, no navegador do usuário (ver 12.6). Não precisa de acesso à conta do cliente.
- Saída: nota geral de 0 a 100, contadores, os 20 itens com situação e orientação, cartão do perfil e o resumo dos concorrentes (posição no top 10 por avaliações e média do segmento).
- Guardar cada pré análise com o histórico, no mesmo padrão da Completa.
- PDF com a identidade da SealsPro, reaproveitando o da Fase 6a.

Fora, para depois: mapa de calor, ranking por palavra-chave, análise de avaliações e de postagens como telas próprias.

### 12.2 Como o original funciona

- A extensão do Chrome é um **robô genérico controlado pelo servidor**: o servidor manda uma sequência de passos (abrir página, clicar, esperar, capturar) e a extensão executa no navegador do usuário.
- Ela abre a página pública do negócio (`local.google.com/place?id=<CID>`) e o Google Maps, captura as respostas internas que o Google manda para a página (`/maps/preview/place` com os dados do local e a busca `tbm=map` com os concorrentes) e o conteúdo da página, e envia tudo para o servidor deles.
- **A extração dos dados e a nota são feitas no servidor**, não na extensão. Por isso as regras de 12.4 vieram das 54 análises guardadas, e não do código.
- Concorrentes: resultados da busca no Maps pela categoria do negócio na região, até cerca de 120. O original calcula a média de avaliações de todos (`avg_reviews_count_all`) e a dos 10 primeiros, e verifica se o negócio está entre os 10 mais avaliados.
- Datas de fotos, postagens e avaliações vêm como o Google mostra ("há 1 ano", "há 3 meses") e são convertidas em dias aproximados (1 ano = 365, 3 meses = 90). A precisão é baixa para datas antigas.

### 12.3 Modelo de nota (medido, confere em 54 de 54)

O mesmo da Completa, reaproveitado de `scoring/base.py` (`status_for`, `overall_score`, `counters`):
- Item com nota 100 é **Bom**, de 50 a 99 é **Razoável**, abaixo de 50 é **Fraco**.
- Nota geral = piso de (bons × 100 + razoáveis × 50) ÷ itens avaliados. Os contadores também conferem em 54 de 54.
- O campo de status que o original manda junto (weak, fair, good) não segue essas faixas (50 aparece como weak e 80 como good). Ignorado.
- **Itens sem dado ficam fora da conta**, em grupos (`scoring/pre/engine.py`, `missing_groups`):
  - `review_sample`, sem amostra de avaliações: saem "sem resposta", "sem comentário" e "tendência".
  - `media`, sem dados de mídia: saem "última foto", "vídeos" e "360°".
  - `competitors`, sem concorrentes: saem "top 10" e "média do segmento". **Aqui nos afastamos do original**, que nesse caso trata a média como 0 e dá 100 nos dois itens (5 casos). É uma falha dele.
  - Por isso há análises com 20, 17 ou 14 itens.

### 12.4 Catálogo dos 20 itens

Pontos medidos entre parênteses (valor bruto = nota do original). A regra que o motor usa e os pontos que a sustentam estão em `scoring/pre/config.py` (campo `observed`). Onde a regra difere da spec v0.1, está indicado.

| id original | id nosso | Item | Regra no motor | Confiança |
|---|---|---|---|---|
| `location_name` | `business_name` | Nome do negócio | Até 98 caracteres = 100 (até 82 medido). Acima de 98 = 50 (102 = 50) | parcial |
| `phone` | `phone` | Telefone | Tem = 100, não tem = 0 | medido |
| `website` | `website` | Site | Domínio próprio = 100 (inclui wixsite e pages.net.br). Rede social = 50: o primeiro nome do endereço, sem `www`, é de rede social (`instagram.com.br` também conta). Sem site = 0. Só Instagram foi medido; as demais redes da lista são hipótese | medido |
| `hours` | `hours` | Horário | Definido = 100, não = 0 | medido |
| `description` | `description` | Descrição | 0 = 0; 1 a 49 = 40; 50 a 99 = 70; 100 a 119 = 80; 120 ou mais = 100. Medido: 0 = 0, 23 a 48 = 40, 54 a 99 = 70, 101 e 108 = 80, 122 ou mais = 100 | parcial |
| `logo` | `logo` | Logotipo | Tem = 100, não = 0 | medido |
| `is_verified` | `verified` | Perfil verificado | Verificado = 100, não = 0 | medido |
| `social_links` | `social_links` | Redes sociais no perfil | 1 ou mais = 100. **Nenhuma = 50**, e não 0 | medido |
| `posts` | `last_post` | Última postagem | Sem postagem = 0; até 15 dias = 100; 16 a 30 = 50; acima de 30 = 0. Medido: 0 a 8 = 100, 21 = 50, 74 ou mais = 0. O 15 vem da mensagem do original; o 30 é hipótese | parcial |
| `media_freshness` | `last_owner_photo` | Última foto do proprietário | Até 30 dias = 100; 31 a 60 = 50; acima de 60 = 0; sem foto = 0. Medido: 3 a 30 = 100, 31 e 60 = 50, 90 ou mais = 0, sem foto = 0 (5 casos) | parcial |
| `videos` | `videos` | Vídeos | 0 = 0, 2 = 50, 3 ou mais = 100. Medido: 0, 2 e 4. **1 vídeo = 25 (interpolação) e 3 = 100 são hipótese.** Na Completa, 2 vídeos dão 66 | parcial |
| `360_images` | `photos_360` | Fotos 360° | **2 ou mais = 100, senão 0.** A spec dizia "tem = 100", mas com 1 foto 360° o original dá 0 em todos os 25 casos, e com 2 dá 100 (1 caso). Hipótese: a primeira é a do Street View, não do proprietário | parcial |
| `reviews_quantity` | `reviews_count` | Quantidade de avaliações | 0 = 0, 1 = 50, 2 = 66, 3 ou mais = 100. Quantidade vazia no `pd` (None ou "", com distribuição zerada) = 0 | medido |
| `reviews_average` | `reviews_average` | Média das avaliações | Sem avaliação = 0; 4,5 ou mais = 100; de 3,5 a 4,4 = 50; abaixo de 3,5 = 0. Medido: 1,0 = 0, 3,7 a 4,3 = 50, 4,5 a 5,0 = 100 (1,0 e 3,7 na comparação ao vivo de 2026-10-10; o corte era 4,0 até então). **4,4 e o corte de 3,5 são hipótese** (fica entre 1,1 e 3,7) | parcial |
| `last_review_date` | `last_review` | Última avaliação | Até 30 dias = 100; 31 a 59 = 50; 60 ou mais = 0; sem avaliação = 0. Medido: 0 a 30 = 100, 31 = 50, 60 ou mais = 0 | parcial |
| `review_growth_trend` | `reviews_trend` | Tendência das avaliações | Média das N mais recentes da amostra (`last_fixed_n`, de 5 a 136 nos casos) contra a média da amostra: queda maior que 0,5 = 0, senão 100. Medido: quedas de 0,61 e 1,07 = 0; até 0,43 = 100. (A spec falava em "5 últimas contra a média geral"; o original usa a amostra.) | hipótese |
| `reviews_without_response` | `reviews_unanswered` | Avaliações sem resposta | Sobre a **amostra** (no original: menor nota + mais recentes da caixa de avaliações da busca; ver 13.5). % sem resposta: abaixo de 10% = 100; de 10% a 50% = 50; acima de 50% = 0. Medido: até 6,8% = 100; 10,5% a 50% = 50; 66,7% ou mais = 0 | parcial |
| `reviews_without_text` | `reviews_with_text` | Avaliações sem comentário | % **com** comentário na amostra: 70% ou mais = 100; de 40% a 69% = 50; abaixo de 40% = 0. Medido: 70,4% ou mais = 100; 42,9% a 66,7% = 50; 23,8% ou menos = 0. **O corte de 40% é hipótese** (fica entre 24% e 43%) | parcial |
| `reviews_ranking_top_10` | `top10_reviews` | Top 10 mais avaliados do segmento | Entre os 10 concorrentes com mais avaliações = 100, senão 0. Sem concorrentes: fora da nota (12.3) | medido |
| `reviews_ranking_average` | `above_segment_average` | Acima da média do segmento | Avaliações ≥ média de todos os concorrentes = 100, senão 0. Sem concorrentes: fora da nota (12.3) | medido |

Comparando com a Completa: a Pré não tem horário especial, serviços, data de abertura, foto de capa, contagem de mídias nem mídias de clientes. Em compensação, traz verificado, redes sociais, 360°, última avaliação e os dois de concorrentes.

### 12.5 Dados necessários e perfil normalizado

Equivalente ao `profile_data` do original. O formato é nosso, documentado em `collector_pre/from_original.py`, e é o mesmo que a coleta definitiva vai produzir:
- `location`: nome, categoria principal e demais, endereço e cidade, CID e place_id, telefone, site, horário, descrição do proprietário, logo, capa, verificado, redes sociais vinculadas ao perfil (`socialLinks`).
- `reviews`: total, média, distribuição por estrelas (5 → 1), dias desde a última avaliação e `sample`, a amostra das mais recentes (até cerca de 100): tamanho, sem resposta, com texto, média, e tamanho e média das N mais recentes.
- `media`: dias desde a última foto do proprietário, quantidade de vídeos, de fotos 360° e total de fotos.
- `posts`: quantidade e dias desde a última.
- `competitors`: quantidade, média de avaliações de todos e se o negócio está no top 10 por avaliações. A coleta calcula isso a partir da lista da busca (nome, CID, nota, avaliações, se é anúncio).
- Os dias já vêm contados no momento da coleta, como o Google mostra. Um grupo `None` significa que o dado não foi coletado, e os itens dele ficam fora da nota.

### 12.6 Fonte de dados (decidido)

**Extensão própria do Chrome**, que captura os dados do Google Maps no navegador do usuário e envia para o app local (`127.0.0.1`). Nada vai para servidor de terceiros. Funciona como o original (12.2), mas a extração e a nota ficam no nosso app.
- **Mapeamento feito em 2026-10-09** (9 perfis reais): fontes, posições e fluxo da extensão estão na seção 13. O leitor em Python (`collector_pre/maps_reader.py`, fase 1 da seção 13) já transforma a captura no perfil normalizado; a extensão em si ainda não existe.
- A recomendação de Apify da spec v0.1 foi **descartada**. Places API também não serve: não traz descrição do proprietário, verificado, postagens, data da última foto, vídeos, 360°, amostra de avaliações com resposta nem redes sociais do perfil.
- Risco conhecido: o formato interno das respostas do Google muda sem aviso, então a manutenção do mapeamento é alta.

### 12.7 Decisões

1. Coleta pela extensão própria (12.6), atrás da interface `collector_pre`, que devolve o perfil normalizado de 12.5. Não construir nada pensando em Apify.
2. **A calibração das regras não depende da fonte.** O arquivo de referência traz os dados brutos e as notas de 54 casos, e o motor é testado contra eles desde já (`coletar.py calibrar-pre`).
3. Itens que a extensão não conseguir alimentar aparecem como "não avaliados" e ficam fora da nota, como o original já faz.

### 12.8 Arquitetura

- `scoring/pre/`: só regras. Um arquivo por item em `scoring/pre/items/`, `config.py` próprio com estado (medido, parcial, hipótese) e pontos observados, `engine.py` (grupos sem dado e ordenação), `version.py` (`PRE_ENGINE_VERSION` e hash do config). Status, nota geral e contadores vêm de `scoring/base.py`, compartilhado com a Completa (ver "Dois motores, duas versões" na seção 8).
- `collector_pre/from_original.py`: adaptador que converte o `pd` do original para o perfil normalizado. Serve para os testes e para o `calibrar-pre`.
- `calibration_pre.py` e o comando `./.venv/bin/python coletar.py calibrar-pre [--arquivo CAMINHO] [--so-divergencias]`: roda o motor nos casos do arquivo e compara item a item. Separa **divergência de regra** (o motor erra) de **decisão nossa** (item que tiramos da nota e o original pontua, hoje só "sem concorrentes"), e mostra também os totais contando esses itens como o original.
- Testes: `tests/scoring/pre/` (um arquivo por item com os pontos medidos, e `test_engine.py`), `tests/test_from_original.py` e `tests/test_calibration_pre.py`. Fixtures em `tests/fixtures/pre/`: 3 casos reais anonimizados (20, 17 e 14 itens; sem nome, endereço, telefone, site, descrição, links, ids nem mensagens do original, mantendo tamanhos e números), que conferem nota geral, contadores e cada item, no papel que o perfil de referência tem na Completa.
- `collector_pre/maps_reader.py`: leitor da captura da extensão (seção 13).
- Feito na fase 2 da seção 13: o receptor `/pre/captura` (`web/pre.py`), que grava o bruto em `data/raw/pre/<cid>/` e a análise na tabela `pre_analyses` (versão do motor, hash e snapshot do config, nota, contadores, resultado e `warnings`), e a tela `/pre` (lista e detalhe, com os avisos em destaque).
- PDF da Pré (feito em 2026-10-10; ver 12.9, fase 3): `report/build_pre.py` (dados), `report/texts_pre.py` (situação e orientação dos 20 itens) e o mesmo modelo da Completa (`report/templates/relatorio.html`, com `r.kind == "pre"`).

### 12.9 Fases

0. **Calibrar o motor offline. Feita (2026-10-09).** Os 20 itens, o adaptador e o `calibrar-pre` contra os 54 casos, sem coleta nenhuma. Resultado: **todos os itens com nota igual à do original, 0 divergências de regra**. Nota geral e contadores iguais em **49 de 54**; os 5 restantes são os casos sem concorrentes, em que a decisão de 12.3 tira 2 itens da nota. Contando esses itens como o original, **54 de 54**. Isso é ajuste aos mesmos pontos que montaram as regras, não validação: os pontos não medidos (12.11) só se resolvem com casos novos.
1. **Mapeamento dos dados da extensão:** feito em 2026-10-09 (seção 13.2). Leitor em Python sobre as fixtures **feito** (fase 1 da seção 13).
2. **Extensão, receptor local** (`127.0.0.1`) e tela de resultado (fases 2 e 3 da seção 13).
3. **PDF e histórico.** PDF **feito em 2026-10-10**; histórico próprio da Pré (evolução e comparação) fica para depois.
   - Público: o dono do negócio, que ainda não é cliente. Mesma identidade e regras do PDF da Completa (Fase 6a): capa ("Diagnóstico do perfil no Google"), resumo com medidor, contadores e frases, bloco **"Comparação com a concorrência"** (concorrentes encontrados, média de avaliações do segmento, acima da média e top 10; some quando os itens de concorrentes não foram avaliados), itens do pior para o melhor com "O que fazer"/"Como manter" e a nota "Critérios próprios da SealsPro". Também em versão resumida (Fase 6a). Sem seção de evolução. Nunca mostra texto de avaliação (a análise guardada nem tem).
   - Usa a pré análise guardada, **sem reavaliar**. A tela `/pre` avisa (e a linha de comando imprime "ATENCAO"), sem nada disso no PDF, quando faltam itens (a partir de 3, manda conferir antes de entregar), quando a coleta teve avisos e quando a análise é de uma versão anterior do motor da Pré ou do config: nesse caso, refazer a pré análise.
   - Como gerar: menu **Ações** na tela `/pre?id=` (`/pre/relatorio.pdf?id=`, com `&modo=resumo` para o resumido) ou `./.venv/bin/python coletar.py relatorio-pre <id> [--saida PASTA] [--resumo]`, que grava `Pre-Analise-<local>-AAAA-MM-DD.pdf` em `data/relatorios/`. Um PDF por vez no app, com a mesma trava da Completa (`report/pdf.py`, `LOCK`).
   - Testes: `tests/test_report_pre.py` (textos de todos os estados dos 20 itens sem jargão nem promessa, montagem, HTML, rota, linha de comando e o PDF de verdade, que pula sem Chrome).
   - Achado junto: os contadores do resumo do PDF da Completa saíam sem o número (o estilo existia, o número não); corrigido nos dois. A frase dos contadores passou a concordar no singular ("1 pode melhorar").
4. **Comparação ao vivo:** rodar a mesma pré análise no original e na nossa versão no mesmo dia e comparar. **Feita em 2026-10-10** com 6 perfis de terceiros (referência `data/reference/pre_analises_original_2026-10-10.json`; ferramenta `comparar_pre_ao_vivo.py`).
   - **Regras: 0 divergências.** Em todos os itens dos 6 perfis, o nosso motor alimentado com os dados do original dá a nota do original.
   - **Resultado final (motor da Pré 12, extensão 0.4.5):** Perfil A 80 = 80, Perfil B 87 = 87 e Perfil C 67 = 67, iguais em todos os itens. Perfil D 95 contra 92 e Perfil E 75 contra 77, com a diferença em itens em que a nossa leitura é a correta (abaixo). Perfil F 85 contra 72: os dados do original vieram quebrados nessa rodada (as duas extensões estavam ligadas), e não deu para repetir no mesmo dia.
   - **O que foi descoberto e ajustado na coleta** (detalhes em 13.5 e 13.10):
     - **Amostra de avaliações:** o original lê a caixa de avaliações da **busca do Google** (`GetLocalBoqProxy`, `hl=en-BR`): lista "menor nota" + lista "mais recentes", 5 páginas (50) de cada, sem repetir; com até cerca de 130 avaliações, lê todas. Reproduzido exatamente em 5 perfis (tamanho, média, com comentário e sem resposta iguais).
     - **Dias:** o original converte o texto do Google ("há 2 meses") em dias (2 × 30), e os cortes das regras foram calibrados nessa escala. O leitor converte os dias exatos para a mesma escala (`as_google_days`).
     - **Concorrentes:** o original busca "categoria cidade-estado" (até cerca de 120) e considera só os de categoria parecida. Reproduzido por aproximação (radical comum entre categorias, hipótese); as médias diferem, mas os itens "top 10" e "acima da média" saem iguais nos 6 perfis.
   - **Onde a nossa leitura é melhor que a do original (mantida de propósito):** última foto do dono (o original lê só o começo da galeria: na Perfil D, disse 60 dias, e a mais recente tinha 11, na posição 305 de 441) e vídeos (o original contou 2 no Perfil E; a categoria "Vídeos" do Google tem 1).
   - **Como rodar o original sem erro:** a extensão do GBP Check e a nossa atrapalham uma à outra no Maps (na Perfil F, com as duas ligadas, o original saiu com 0 vídeos, 0 fotos 360° e amostra com média 1,18). Rode cada uma com a outra desligada (`chrome.management.setEnabled` na página `chrome://extensions`). A pré análise do original **trava em perfis que a conta Google do navegador administra** (o Google mostra o painel do dono) e, num perfil já analisado no dia, o botão fica com "✓" e não roda de novo. O resultado do original é lido da página `app.gbpcheck.com/extension-v2/healthcheck` (resposta do POST com `pre_health_check_result`, `profile_data` e `result_competitors_data`).
   - **Segunda rodada (2026-10-10, 4 perfis de terceiros com poucas avaliações e sem site):** Perfil G 45 = 45, Perfil H 50 = 50, Perfil I 45 = 45 e Perfil J 47 = 47, iguais em todos os itens. O original foi rodado pelo usuário e lido dos PDFs (só notas e mensagens, sem o `pd`; por isso não entrou no arquivo de referência). Achado: média 3,7 = 50 no original, e o nosso corte era 4,0; baixado para 3,5 (hipótese). Dados iguais aos do original: dias da última avaliação e da última foto do dono, sem resposta e com comentário; média do segmento próxima (20,5 contra 18 a 26,7 contra 19), com o mesmo resultado nos itens de concorrentes. As pré análises 43 a 46 foram gravadas com o motor da Pré 10, porque o app não tinha sido reiniciado depois das versões 11 e 12: reinicie o `serve.py` depois de mudar o leitor ou o motor.
   - **Próximos passos sugeridos:** repetir a Perfil F com só o original ligado; acrescentar perfis com poucas avaliações, sem site e não verificados (de terceiros); conferir o corte de 130 avaliações (entre 130 e 249 não há medida) e o filtro de concorrentes em mais segmentos.

### 12.10 Critério de aceite da primeira versão

- O motor, alimentado com os dados brutos do original, tem **0 divergências de regra** (todo item com nota igual à do original, salvo os que tiramos da nota por decisão nossa) e reproduz a nota geral e os contadores em **54 de 54 casos contando os itens de concorrentes como o original**. (A spec v0.1 pedia 50 de 54 pela nossa regra; o critério foi trocado em 2026-10-09.) **Atingido na Fase 0.** Pela nossa regra, a nota geral e os contadores conferem em 49 de 54: as 5 diferenças restantes são **decisão nossa** (sem concorrentes = não avaliado, 12.3), não erro de regra nem ponto não medido.
- **As regras ainda não foram validadas fora desses 54 casos.** Elas foram montadas com os mesmos casos que as conferem; a validação vem com casos novos (Fase 4 de 12.9, ou uma referência nova de pré análises do original rodada no `calibrar-pre`).
- Com a coleta real, uma pré análise de um perfil do arquivo de referência sai com todos os itens que a fonte cobre, e os demais aparecem como não avaliados.

### 12.11 Perguntas em aberto

- Pontos não medidos: 1 e 3 vídeos; média 4,4 e de 1,1 a 3,6; descrição de 49 a 53, 100 e de 109 a 121 caracteres; nome de 83 a 101 caracteres; postagem de 9 a 20 e de 22 a 73 dias; última foto de 61 a 89 dias; última avaliação de 32 a 59 dias; sem resposta entre 6,9% e 10,4% e entre 50,1% e 66,6%; com comentário entre 24% e 43%; queda da tendência entre 0,44 e 0,60.
- Fotos 360°: confirmar se a primeira foto 360° é a do Street View e se a extensão consegue separar a do proprietário.
- Quantos concorrentes buscar (custo contra precisão da média). O original chega a cerca de 120.
- Se a extensão não trouxer a data da última foto do proprietário, vale estimar pela foto mais recente de qualquer autor?

## 13. Pré Análise: coleta gratuita pela extensão própria (spec v0.1)

Origem: `data/reference/SPEC-extensao-pre.md`, incorporada aqui. Complementa a seção 12. Decisão do usuário: **fonte de dados gratuita**. A coleta é feita no próprio navegador, como faz o GBP Check, por uma extensão nossa, que envia os dados brutos para o app local; o app faz a leitura e a nota.

Mapeamento feito em 2026-10-09 em 9 perfis reais, com o Google em português do Brasil. Os arquivos de exemplo e um leitor de referência (`mapa_campos.py`) estão em `data/reference/maps/`, fora do git (alguns perfis são de clientes).

### 13.1 Arquitetura

```
Chrome do usuário                           Computador do usuário
┌────────────────────────────┐   POST     ┌──────────────────────────────┐
│ Extensão SealsPro (MV3)         │ ────────▶ │ app local 127.0.0.1:8000      │
│ - captura respostas do Maps │  JSON     │ /pre/captura                  │
│ - automatiza abas e rolagem │  bruto    │ collector_pre/maps_reader.py  │
│ - não interpreta nada       │           │ scoring/pre → nota, tela, PDF │
└────────────────────────────┘            └──────────────────────────────┘
```

- **A extensão é burra de propósito:** só captura e envia. Toda a leitura das posições fica em Python, com testes sobre fixtures. Quando o Google mudar o formato, o conserto acontece no leitor, sem mexer na extensão.
- Roda só em domínios do Google e envia só para `127.0.0.1`. Nada passa por servidor de terceiros.
- Instalação pelo modo de desenvolvedor do Chrome ("Carregar sem compactação"), sem publicar na loja.

### 13.2 Onde está cada dado

**A. Dados do local (`/maps/preview/place`)**, carregados ao abrir o perfil no Maps. O objeto do local fica em `[6]`.

| Dado | Posição em `[6]` | Conferido |
|---|---|---|
| Nome | `[11]` | 9 perfis |
| Categorias | `[13]` (lista) | 9 |
| Endereço | `[39]` | 9 |
| Latitude e longitude | `[9][2]`, `[9][3]` | 9 |
| CID | `[10]`, parte depois de `:` em hexadecimal convertida para decimal | 9 |
| place_id | `[78]` | 9 |
| Telefone | `[178][0][0]` | 9 |
| Site | `[7][0]` (instagram.com e afins: o item Site vale 50) | 9. Ver 13.6 |
| Nota média | `[4][7]` | 9 |
| Total de avaliações | `[4][8]` | 9 |
| Distribuição por estrelas | `[175][3]`, da 1 até a 5 estrelas | 9, mesma ordem do original |
| Descrição do proprietário | `[154][0][0]` | 9 |
| Logo | `[157]` | 9 |
| Verificado | `[49]` vazio = verificado; preenchido com o link "reivindicar esta empresa" = não verificado | 2 não verificados |
| Horário | `[203][0]`: dias com faixas de horário | 9 |
| Categorias da galeria | `[171][0][i]` = `[código, ?, nome, …]`. Os códigos se repetiram nos 9 perfis e na primeira captura real: "Tudo" `CgIgAQ==`, "Do proprietário" `CgIgARICEAE=`, "Vídeos" `CgIgARICCAQ=`, "Street View e 360°" `CgIgARICCAI=`. **O leitor reconhece a categoria pelo código** (o nome muda com o idioma do Maps; nome em pt e en é só reserva) | 9 |
| Postagens ("Do proprietário"/"From the owner" no painel) | `[122][1]`: lista de postagens; em cada uma, `[2][0]` = criação em segundos Unix, `[2][1]` = expiração (cerca de 6 meses depois), `[12]` = data como o Google mostra ("26 de ago. de 2026", "há 2 dias"). **Ligado ao item última postagem (2026-10-10):** conferido em dois perfis de terceiros (uma agência e uma imobiliária), com datas iguais às da tela; os links de editar/excluir vêm para qualquer um, não só para o dono. Sem `[122]` = sem postagem (vale 0, como no original). O Maps mostra só a mais recente ("Do proprietário" na Visão geral); a busca mostra 7 a 10 | 9 + 2 de terceiros |

**B. Avaliações (`batchexecute`, `rpcids=qv9Egd`)**, ao abrir a aba Avaliações, ordenar por "Mais recentes" e rolar. 10 por página.

| Dado | Posição na avaliação `r` |
|---|---|
| Data | `r[1][3]` em microssegundos = última edição, a data que o Google mostra e pela qual ordena ("Editado há 9 horas"); `r[1][2]` = criação. Achado na fase 1: com `r[1][2]` as avaliações editadas saem fora de ordem; com `r[1][3]`, as 60 da fixture ficam em ordem decrescente. Melhor que o original, que só tem "há 3 meses" |
| Nota | `r[2][0][0]` |
| Texto | `r[2][15][0][0]` (vazio = sem comentário) |
| Resposta do proprietário | `r[3][1]` com a data e `r[3][14]` com o texto. Vazio = sem resposta |
| Próxima página | `inner[1]` |

**B'. Amostra de avaliações como a do GBP Check (caixa de avaliações da busca do Google, desde a 0.4.4).** No clique do botão na busca, `src/lib/reviews-search.js` faz os mesmos GET que a caixa faz: `/httpservice/web/PrivateLocalSearchUiDataService/GetLocalBoqProxy?hl=en-BR&reqpld=<json>`, com o ftid do negócio, a ordem (4 = menor nota, 2 = mais recentes), 10 por página e o token da página seguinte (posição 19 do bloco; a resposta traz o próximo token em `[1][10][6]`, vazio no fim). Na avaliação `rv` de `[1][10][2]`: nota `rv[1]`, data `rv[2][2]` (milissegundos), resposta do dono `rv[4]`, id `rv[5]`, texto `rv[27]`. As listas "menor nota" do Google (no Maps e na busca) **terminam antes do total** (Perfil D: 59 em português e 38 em inglês, de 464).

**C. Galeria de fotos (`batchexecute`, `rpcids=hspqX`)**, ao abrir as fotos na categoria "Mais recentes". 20 por página.

| Dado | Como ler |
|---|---|
| Data de envio | `[ano, mês, dia, hora]` em `item[21][6][8]` |
| Enviada pelo proprietário | o item contém uma origem que começa com `bizbuilder:` (clientes: `photos:...`) |
| É vídeo | o item tem links de vídeo terminados em `=mm,hls` ou `=mm,dash` |
| Fim da galeria | a última página traz `True` em `inner[10]` ou menos de 20 itens (hipótese, conferida em 1 galeria) |

Achado na fase 1: "Mais recentes" **não vem ordenada por data de envio** (na fixture, o primeiro item é de 2024 e a foto mais recente do proprietário está na segunda página). Por isso a foto mais recente encontrada só é final quando a galeria foi lida inteira ou quando ela já está na melhor faixa (até 30 dias).

**D. Concorrentes (busca do Maps, `tbm=map`)**: busca pela categoria do negócio perto das coordenadas. Resultados em `[64]`, com o mesmo formato de local em `[64][i][1]`; anúncios têm só 6 posições. 20 por página (`!7i20` na URL).

**E. Painel do Google (busca)**: `local.google.com/place?id=<CID>` redireciona para a busca do Google com o painel do negócio. É a **única fonte encontrada para redes sociais** (as postagens passaram a vir da fonte A em 2026-10-10). Leitura pelo texto da página, mais frágil:
- Postagens: bloco "<nome> no Google", com datas como "há 2 dias" ou "30 de set. de 2026".
- Redes sociais: bloco "Perfis", com links para Instagram, Facebook etc. **Lido desde a extensão 0.4.0 (2026-10-10)** pelo `data-attrid="kc:/common/topic:social media presence"` (não depende do idioma), com os links diretos para cada rede. Conferido na SealsPro e num perfil de terceiro (Perfil A).

### 13.3 Fluxo da extensão para uma pré análise

1. O usuário cola o link ou o nome do negócio no app, ou abre o perfil no Maps e clica no botão da extensão.
2. A extensão abre o perfil no Maps com `hl=pt-BR` e captura a fonte A.
3. Abre Avaliações, ordena por "Mais recentes" e rola até cerca de 100 avaliações ou até acabarem (fonte B).
4. Abre a galeria em "Mais recentes" e pagina até achar a foto mais recente do proprietário (fonte C). Para economizar, pode parar em 3 páginas. (Versão 0.3.0: as categorias e a busca dos concorrentes passaram a ser abertas em **abas controladas**; ver 13.10.) **Na fase 2, a extensão deve abrir também as categorias "Vídeos" e "Do proprietário" da galeria**: "Vídeos" para contar os vídeos direto, e "Do proprietário", que traz só as fotos do dono e costuma ser curta, lida inteira, para dar a data da última foto do dono sem depender da ordem da "Mais recentes" (que não vem por data, 13.2). Hoje, com a galeria incompleta, menos de 3 vídeos achados ou a foto do dono acima de 30 dias ficam "não avaliado".
5. Faz a busca da categoria principal perto das coordenadas e pega até 3 páginas, cerca de 60 concorrentes (fonte D).
6. Redes sociais (fonte E): lidas no clique do botão na busca, sem abrir nada (ver 13.10, 0.4.0). Começando pelo Maps, ficam "não avaliado".
7. Envia tudo, bruto, para `POST http://127.0.0.1:8000/pre/captura` e abre a tela do resultado.

Ritmo humano: um perfil por vez, com pausas entre os passos. A extensão não roda em segundo plano nem em lote.

### 13.4 Cobertura dos 20 itens

| Item | Fonte |
|---|---|
| Nome, telefone, site, horário, descrição, logo, verificado | A |
| Quantidade e média de avaliações | A |
| Última avaliação, sem resposta, sem comentário, tendência | B |
| Última foto do proprietário, vídeos | C, cruzada com as categorias da galeria em A |
| Fotos 360° | C: categoria "Street View e 360°" da galeria (desde a 0.4.1; ver 13.10) |
| Top 10 e média do segmento | D |
| Última postagem | A, `[122][1]` (a partir de 2026-10-10) |
| Redes sociais | E: só no bloco "Perfis" do painel da busca do Google (no Maps não aparecem; conferido em 3 perfis de terceiros). Avaliado só quando a pré análise começa pelo botão na busca |

### 13.5 Leitor (`collector_pre/maps_reader.py`, fase 1)

Entrada: a captura `{capturedAt, place, reviews: [páginas], photos: [páginas], search: [páginas]}`, com cada parte em texto (com ou sem `)]}'`) ou JSON já lido; fonte ausente (`None`) = não coletada. Saída: o perfil normalizado da Pré (12.5; a amostra de avaliações traz também `ratings`) mais `notCollected` (itens que ficam "não avaliado") e `warnings` (avisos de "leitor desatualizado"). O motor (`PRE_ENGINE_VERSION` 2 em diante) trata `notCollected` como fora da nota e devolve os `warnings` junto com a análise, para serem guardados com ela e mostrados na tela.

Regras:
- **"Não avaliado" só quando a fonte não foi coletada** (ou veio em formato inesperado). **Fonte coletada e dado inexistente vale 0, como no original.** Exemplos: 0 avaliações na fonte A = 0 em última avaliação, quantidade e média, mesmo sem a fonte B; sem a categoria "Do proprietário" na fonte A = 0 na última foto do proprietário, mesmo sem a fonte C; sem a categoria "Vídeos" = 0 vídeos.
- **Formato inesperado nunca vira erro nem nota errada:** acesso seguro (`g()`), a fonte ou o campo vira "não avaliado" e gera um aviso. Fonte A ilegível derruba todos os itens dela; um campo em formato errado (por exemplo, o total de avaliações como texto) só tira o item dele.
- **Quantidade de avaliações sempre da fonte A** (`[4][8]`), nunca do tamanho da amostra.
- **Avaliações:** a amostra é o que a fonte B trouxe. Se as datas não estiverem em ordem decrescente, última avaliação e tendência ficam "não avaliado" com aviso (sem resposta e sem comentário continuam). Fonte A com avaliações e fonte B vazia: "não avaliado" com aviso.
- **Amostra (sem resposta, com comentário e tendência), por prioridade:** `reviewsSearch` (B', igual à do GBP Check: menor nota + mais recentes, sem repetir; com até 130 avaliações na fonte A, todas as páginas; acima, as 5 primeiras de cada lista; o corte de 130 é hipótese, medido entre 129 e 250) > `reviewsLowest` (Maps, "Menor classificação", 0.4.3) > `reviews` (Maps, "Mais recentes", capturas antigas; no máximo 100). A última avaliação vem sempre de `reviews`.
- **Dias na escala do GBP Check** (`as_google_days`): última avaliação, última foto do dono e última postagem passam pela conversão do texto do Google (até 6 dias = exato; 7 a 29 = semanas × 7, hipótese; 30 a 364 = meses × 30; depois, anos × 365). Conferido: 169 → 150, 65 → 60, 806 → 730.
- **Concorrentes do segmento:** só entram os de categoria principal parecida com alguma categoria do negócio (`_stems`: radical de 6 letras, sem acento, sem palavras genéricas como "loja" e "clínica"). Hipótese que aproxima o filtro do original.
- **Tendência:** o leitor só entrega a amostra ordenada (`sample.ratings`, da mais recente para a mais antiga). **O N é regra de nota e fica no motor** (`scoring/pre/base.py`, `recent_window`; valores em `scoring/pre/config.py`, `reviews_trend`): N = 10% do total de avaliações da fonte A, mínimo 5, marcado como **medido** (é o `last_fixed_n` do original nos 47 casos com amostra; quando N passa do tamanho da amostra, o original usa a amostra inteira, e o motor também). Assim uma mudança no N trava a versão do motor (`PRE_ENGINE_VERSION` 3). Perfis do adaptador do original, que não trazem `ratings`, usam o N e a média que o original já calculou com a mesma regra.
- **Última foto do proprietário:** com a categoria "Do proprietário" e a galeria lida inteira, a mais recente com `bizbuilder:` é final (nenhuma = 0, com aviso). Com a galeria incompleta, só é final se já estiver em até 30 dias; senão, "não avaliado" com aviso.
- **Vídeos:** com 3 ou mais encontrados, resolvido; com a galeria lida inteira, a contagem é final; se a leitura parou antes com menos de 3, "não avaliado" com aviso.
- **Concorrentes:** sem anúncios, sem o próprio negócio (pelo CID) e sem repetidos. Média = média de avaliações dos concorrentes. Top 10 = menos de 10 concorrentes com mais avaliações que o negócio (empate conta a favor). Busca coletada e vazia = sem concorrentes = fora da nota (12.3).
- **Redes sociais** (`socialLinks`, lista de links do bloco "Perfis"): lista = a busca foi lida (vazia = sem o bloco = 50, como no original); ausente (`None`) = a captura começou pelo Maps = "não avaliado", sem aviso; formato inesperado = "não avaliado" com aviso. O leitor desfaz o redirecionamento do Google (`/url?q=`), ignora o que não é http(s) e repetidos, fica com até 10 e dá nome pela lista de domínios (`SOCIAL_NAMES`; fora dela, o próprio domínio). Sem a fonte A, também "não avaliado".
- **Fotos 360°** (`photos360`, páginas da categoria "Street View e 360°"): conta os itens esféricos (`[21][2][1] == 2`; fotos comuns têm 3 ou 4), **incluindo o panorama do Street View** (origem `launch`), como o original. Conferido em 2026-10-10: Perfil A com 1 item (só o Street View) = 0, e Perfil F com 2 (o Street View e uma foto esférica de cliente) = 100, iguais ao original (`image_360_count` 1 e 2). Sem a categoria na fonte A = 0. Categoria não capturada = "não avaliado". Itens sem a marca esférica, ou leitura incompleta com menos de 2, = "não avaliado" com aviso.
- **Páginas da galeria por categoria:** cada página traz a sua categoria em `[13][0]` (e o total de itens da categoria em `[1]`). Nas categorias pedidas (`photosOwner`, `photosVideos` e `photos360`), o leitor **só aceita as páginas da categoria certa**: o código conhecido ou o que a fonte A trouxe para o mesmo nome. Ficam de fora a página de outro bloco clicado na reserva e a do **visualizador do Street View**, que o Maps abre sozinho e que busca panoramas vizinhos pelo mesmo `hspqX`, sem `[13]`. Se nenhuma página for da categoria, o item fica "não avaliado", com aviso.
- Testes (`tests/test_maps_reader.py`) sobre cópias anonimizadas em `tests/fixtures/pre/maps/`: locais A (verificado, com site, vídeos e galeria), B (muitas avaliações, com a fonte B), C (não verificado, site no Instagram, sem telefone, descrição, logo nem categoria "Do proprietário") e D (sem site); páginas de avaliações (B), da galeria (A) e uma busca com anúncio. Todo texto virou marcador do mesmo tamanho, menos categorias, nomes das categorias da galeria, horário e as origens `bizbuilder:`/`photos:`; links viraram `example.com`, CIDs e place_ids viraram fictícios (o mesmo CID vira o mesmo id em todos os arquivos) e coordenadas viraram 0. Um teste falha se sobrar link, telefone, CID, place_id ou coordenada real. Os dois lados da regra (não coletado = não avaliado; coletado e ausente = 0) e lixo em cada fonte são testados.

### 13.6 Cuidados conhecidos e pistas

- **O formato muda sem aviso.** Ver 13.5: o campo não encontrado vira "não avaliado" e gera o aviso de "leitor desatualizado" na tela, nunca uma nota errada.
- **Conta logada:** o navegador está logado na conta Google do usuário. Em perfis que ele administra, o Maps mostra dados extras de proprietário (como links de responder). O leitor não depende deles.
- **Site:** em um perfil, o Maps mostrava "whatsapp.com" como link principal e `[7]` vinha vazio. Na v1, só `[7][0]` conta como site.
- **Datas do painel do Google** são relativas ("há 2 dias") ou por extenso ("30 de set. de 2026"). O leitor da fonte E vai converter as duas.
- **360°, resolvido na 0.4.1 (ver 13.5).** A pista original era esta: na Fase 0 (12.4) descobrimos que o original só dá 100 com **2 ou mais** fotos 360° (com 1, dá 0 em 25 casos), e a hipótese é que a primeira seja a do **Street View**, não do proprietário. Na fonte A, a categoria **"Street View e 360°" aparece nos 9 perfis mapeados**, o que combina com a hipótese de que quase todo perfil tem ao menos uma (a do Street View). A investigar: abrir essa categoria na galeria (fonte C) e ver se os itens trazem um marcador de 360° e de autor (`bizbuilder:` para o proprietário, outro para o Street View), para contar só as do proprietário ou reproduzir a regra de "2 ou mais".
- **Termos do Google:** proíbem extração automatizada. O uso é interno, um perfil por vez e iniciado pelo usuário no navegador dele, como faz o original. Mesmo assim é uma área cinzenta, e a decisão é do usuário.

### 13.7 Segurança do app local

- O endpoint `/pre/captura` aceita só a origem `chrome-extension://<id da nossa extensão>` e exige um segredo compartilhado, configurado nas opções da extensão e guardado no `.env`.
- As outras rotas continuam com as proteções atuais de Host e Origin.
- O JSON bruto vai para `data/raw/pre/`, fora do git.

### 13.8 Fases

1. **Leitor em Python sobre as fixtures**, sem extensão. **Feita (2026-10-09):** `collector_pre/maps_reader.py` (13.5).
2. **Endpoint local e extensão v1** com as fontes A, B, C e D, incluindo as categorias "Vídeos" e "Do proprietário" (13.3, passo 4) e os `warnings` guardados com a análise. **Implementada (2026-10-09), falta a conferência manual no Chrome do usuário** (13.10). Até lá, os seletores da interface do Maps e o formato das páginas das categorias da galeria são hipótese.
3. **Painel do Google** (fonte E): redes sociais **feitas** pelo caminho (a), na 0.4.0 (13.10). As postagens vieram da fonte A. Fica para depois, se fizer falta, o caminho (b): abrir a busca numa aba controlada quando a pré análise começa pelo Maps.
4. **Comparação ao vivo**: os mesmos perfis no original e na nossa versão, no mesmo dia.

### 13.9 Arquivos de referência (`data/reference/maps/`, fora do git)

- `place_*.json`: resposta A de 9 perfis (com e sem site, verificado e não verificado, com e sem vídeos, com muitas e poucas avaliações).
- `rpc_reviews_*_pages.json`: 6 páginas de avaliações de um perfil (fonte B).
- `rpc_photos_*.json`: 2 páginas da galeria de um perfil (fonte C).
- `search_*_top4.json`: os 4 primeiros resultados de uma busca, incluindo um anúncio (fonte D; só a lista de `[64]`).
- `mapa_campos.py`: leitor de referência que confirma as posições. É documentação; o leitor definitivo é `collector_pre/maps_reader.py`.

### 13.10 Fase 2: extensão, receptor e tela (implementada e conferida ao vivo)

**Estado em 2026-10-10: conferida ao vivo** (capturas reais desde a 0.3.2, 20 de 20 itens na 0.4.1 e comparação com o original na 0.4.5; ver 12.9, fase 4). O texto de 2026-10-09 dizia que nenhuma captura real tinha passado por ela; isso ficou para trás. Continua valendo: as regras ainda não foram validadas fora dos casos que as montaram (12.10), e uma pré análise com 3 ou mais itens não avaliados deve ser conferida antes de ir para cliente.

Arquivos: `extension/` (a extensão), `web/pre.py` (receptor e tela), `storage.py` (tabela `pre_analyses`), `service.store_pre_capture`, templates `web/templates/pre.html` e `pre_lista.html`.

Regras de segurança (obrigatórias; testadas):
- **O envio para 127.0.0.1 sai só do service worker** (`extension/src/background.js` com `src/lib/run.js`), nunca do content script. Um pedido do content script leva a origem da página do Google, e o Chrome bloqueia pedidos de páginas públicas para a rede local. O content script entrega a captura ao service worker por `chrome.runtime.sendMessage`, e o service worker envia com a origem `chrome-extension://<id>`.
- **O segredo fica só no service worker e na página de opções** (`chrome.storage.local`, nunca `sync`), e no app em `GBP_EXTENSION_SECRET`, no `.env` **da raiz do projeto** (`gbp_auth.ENV_PATH`, ignorado pelo git, permissão 600), junto com `GBP_EXTENSION_ID`. O app lê essas duas chaves só desse arquivo (`gbp_auth.project_env`), a cada pedido; o `.env` da skill (credenciais do Google) não vale para a extensão. Nunca no script do mundo MAIN nem em nenhum content script (`extension/tests/static.test.js` confere no código).
- **O receptor** (`/pre/captura` e `/pre/ping`) exige Origin exatamente `chrome-extension://<GBP_EXTENSION_ID>` e o cabeçalho `X-Seals-Secret` igual ao segredo, comparado em tempo constante. Exige também corpo JSON de até 20 MB. Sem a configuração no `.env`, nada entra; qualquer falha devolve 403 sem dizer o motivo. Não manda cabeçalhos CORS. O `TrustedHost` continua, e as outras rotas mantêm a proteção contra CSRF, inclusive contra a origem da extensão.
- **Nada é enviado sem o clique:** a captura passiva fica só na memória da página (`src/lib/buffer.js`), com limite de tamanho (30 MB e 400 respostas) e descartada ao sair da página (`pagehide` e `beforeunload`). O clique no botão libera **aquela aba** por 15 minutos (`chrome.storage.session`). O service worker só envia uma captura vinda dessa aba e da URL do Maps, uma vez.
- **Todo texto capturado é não confiável:** autoescape na tela `/pre` e no PDF, nenhum `|safe` nos templates (teste), e link capturado só vira `href` se for `http(s)`. O texto das avaliações nunca é mostrado. Testes injetam `<script>` no nome, na descrição, na categoria e numa avaliação e conferem que sai escapado ou não aparece. Na extensão: nenhum `innerHTML`, `eval` nem `Function` (teste); a faixa de progresso usa só `textContent`.
- **Ritmo humano:** um perfil por vez, só depois do clique, na aba aberta, com pausa de 2 a 5 s entre os passos e de 1,2 a 2,5 s entre ações. Uma faixa na página mostra o passo e tem botão Cancelar. Nada roda em segundo plano, por horário ou em lote.
- **Permissões travadas** por `tests/test_extension_manifest.py`: `permissions: ["storage"]` (sem `activeTab`, que não é necessária) e `host_permissions: ["http://127.0.0.1:8000/*"]`. Content scripts:
  - no Maps: `https://www.google.com/maps/*` e `https://www.google.com/maps?*`. O segundo existe porque a aba aberta pelo botão da busca começa em `/maps?cid=`, que o primeiro padrão não cobre;
  - na busca, só o botão: `https://www.google.com/search*` e `https://www.google.com.br/search*`.
  Na conferência manual, se o Maps abrir em `google.com.br` no Chrome do usuário, acrescentar **só esse domínio**, no manifest e no teste.
- **Botão "Pré Análise SealsPro" dentro da página (versão 0.2.0), como no GBP Check:**
  - O botão fica num shadow DOM fechado e só inicia com `event.isTrusted` (`src/lib/button.js`). É pequeno, em linha (sem `position: fixed`), com o verde `#14B8A6` e a fonte do sistema, e entra antes do conteúdo, sem remover nada (convive com os botões do GBP Check).
  - **Na busca do Google** (`src/search.js`), o botão aparece acima do painel do negócio, só quando há um CID. O CID vem de `ludocid=`, `data-ludocid`, `cid=` ou do ftid `0x…:0x<hex>` dos links do painel; fica o que mais se repete (`src/lib/cid.js`). Ao clicar, o **service worker** abre `https://www.google.com/maps?cid=<CID>&hl=pt-BR` numa aba nova e libera essa aba com início automático, uma única vez (`seals:open-maps`, depois `seals:pending?`). Na busca nada é capturado.
  - **No Maps** (`src/content.js`), o botão aparece no topo do painel do perfil (antes do bloco do primeiro `h1` visível dentro de um `div[role=main]`, porque o Maps pode ter mais de um) e a captura roda na própria aba (`seals:begin`). O início automático da aba aberta pela busca só é pedido quando o endereço já é `/maps/place/…`, para não ser gasto em `/maps?cid=…`, antes de o Maps trocar de endereço.
  - Na aba aberta pela busca, a captura espera até 15 s pelos dados do perfil. Se não chegarem, busca a `preview/place` indicada num `<link>` de preload da própria página, se houver. É hipótese a conferir; é o único `fetch` do content script, e só para essa URL do Google.
- **Só os dados do perfil aberto (0.3.9):** o Maps também busca a `preview/place` de outros locais visíveis no mapa. Numa captura real, a extensão pegou a mais recente e analisou um clube de futebol no lugar de uma imobiliária. Agora a extensão só aceita a resposta cujo identificador (`[6][10]`, `0x…:0x…`) é o mesmo do endereço aberto (`!1s0x…:0x…`). A captura leva esse identificador (`profileFtid`), e o leitor recusa a fonte A de outro local, com aviso. Isso derruba os itens dela para "não avaliado", em vez de dar nota a outro negócio. A pré análise id 11 do banco era desse erro e foi apagada em 2026-10-10 (backup do banco e do bruto em `data/backups/`).
- **Um arquivo por mundo (achado na primeira conferência ao vivo, versão 0.2.1):** o Chrome injeta um mesmo arquivo **uma única vez por página**. Com `src/lib/match.js` nas duas entradas do Maps (MAIN e ISOLATED), ele rodou só no MAIN, e o `content.js` quebrou na primeira linha (`globalThis.__sealsMatch` indefinido). Por isso não havia botão nem faixa, e o ícone mostrava "!". O mundo MAIN agora usa uma cópia idêntica em `src/main/match.js`; testes conferem a cópia e que as duas entradas não dividem arquivos.
- **Checagem antes de capturar (0.2.2):** antes de qualquer passo, o content script pergunta ao service worker (`seals:ready?`) se o segredo está salvo e se o app aceita a extensão (`/pre/ping`, sem dados do perfil). Se não, a faixa diz o que fazer e nada é capturado. Antes, a captura rodava inteira e só falhava no envio.
- **Clique no ícone da barra:** não usa `tab.url`, que vem vazio sem a permissão `tabs`. Manda `seals:start` ao content script da aba e só mostra o aviso se ninguém responder (`handleActionClick`, testado com `tab.url` vazio). Quando o aviso aparece com um perfil aberto, a causa é o content script ausente na aba: ela foi aberta antes de a extensão ser carregada ou recarregada (recarregar a aba resolve), ou o Maps está num domínio fora do manifest (por exemplo, `google.com.br/maps`).

**Versão 0.4.0 (2026-10-10): redes sociais pelo botão da busca.** No clique, `src/search.js` lê os links do bloco "Perfis" do painel e manda junto com `seals:open-maps`. O service worker limpa a lista (`cleanSocialLinks`: só http(s), sem repetidos, até 10, cada um com até 300 caracteres) e guarda com a liberação da aba do Maps (`arming`). No envio, **só o service worker** acrescenta `socialLinks` à captura: um `socialLinks` vindo da aba do Maps é descartado, e a captura que começa pelo Maps leva `null`. Motor da Pré na versão 5, porque a mesma captura passa a ter outra nota. Conferido ao vivo na Perfil A (pré análise id 14): Facebook e Instagram, iguais à tela, e 19 de 20 itens avaliados (só falta o 360°).

**Versão 0.4.1 (2026-10-10): fotos 360° e galeria mais confiável.** Conferida ao vivo na Perfil F (20 de 20 itens, 360° = 2, vídeos = 4) e na Perfil A (20 de 20, 360° = 1).
- Nova aba controlada para a categoria "Street View e 360°" (`photos360`, código `CgIgARICCAI=`, até 3 páginas). Motor da Pré na versão 6.
- **Endereço da galeria montado do zero** (`galleryUrl`): antes, ele remendava o endereço do perfil e levava junto o `!9m1!1b1` (painel de avaliações aberto depois do passo das avaliações), e a aba controlada abria as avaliações no lugar da galeria. Na Perfil F isso fez a pré análise 15 contar 0 vídeos (são 4), usando a faixa de fotos do topo como se fosse a categoria.
- A aba controlada só aceita página da categoria pedida (`[13]`, `galleryCategory`), espera a grade (`[data-photo-index]`) antes de escolher o elemento que rola, busca de novo o contêiner quando o Maps redesenha a lista e **para de rolar quando a página marca o fim** (`[10]`, `galleryEnd`). Antes, ela rolava cerca de 15 s à toa nas categorias curtas (vídeos, 360°). Na reserva por clique, só valem as páginas que chegaram depois do clique na categoria.
- Pré análises 15 a 19 da Perfil F: testes desta conferência (a 15 com vídeos e foto do proprietário errados; as outras com itens "não avaliado"). Apagadas em 2026-10-10, com backup do banco e dos brutos em `data/backups/`.

**Versão 0.4.2 (2026-10-10): galeria rápida e amostra de 100.** Achados da comparação ao vivo (12.9, fase 4).
- **Galeria:** na aba controlada, vai direto ao fundo da grade e espera a próxima página (1,2 a 2 s), até a página marcar o fim, nada novo chegar em 5 tentativas ou o limite (`scrollGallery`). Antes, rolava em passos: "Do proprietário" da Perfil D (441 fotos) levava mais de 5 minutos e a aba era dada como sem resposta; agora leva cerca de 30 s. Limite de "Do proprietário" subiu de 15 para 30 páginas.
- **Avaliações:** o limite de 10 páginas passou a valer em páginas recebidas (chegavam 21 a 23). O leitor usa no máximo as 100 primeiras (`SAMPLE_MAX`). Motor da Pré na versão 7.

**Versões 0.4.3 a 0.4.5 e motor da Pré 8 a 12 (2026-10-10): comparação ao vivo com o original (12.9, fase 4).**
- 0.4.3: amostra pela ordem "Menor classificação" do Maps (`reviewsLowest`; das mais recentes só a primeira página, para a última avaliação). Busca dos concorrentes como no original: `<categoria> <cidade>-<estado por extenso>` (cidade e UF de `[6][2]`, por exemplo "Belo Horizonte - MG"), até 6 páginas. Corrida da aba controlada: o service worker avisa (`pending`) enquanto uma aba está sendo criada, e a aba espera até 15 s pela tarefa (antes, às vezes ficava sem tarefa e a captura perdia "Do proprietário").
- 0.4.4: amostra da caixa de avaliações da busca (B'). **Exceção à regra "a extensão só captura":** é o único `fetch` de `src/search.js`, na própria origem, só para o caminho `GetLocalBoqProxy`, só depois do clique, com 0,9 a 1,6 s entre os pedidos (no máximo 18). O texto das páginas vai ao service worker com `seals:open-maps`, que valida (`cleanReviewsSearch`) e acrescenta à captura no envio, como as redes sociais. Começando pelo Maps, não há essa amostra, e o app usa a do Maps.
- 0.4.5: mais recentes até 13 páginas, para os perfis de até 130 avaliações (o original lê todas).
- Motor da Pré: 8 (amostra de menor nota do Maps), 9 (amostra da busca), 10 (até 130 avaliações, todas), 11 (dias na escala do original), 12 (concorrentes de categoria parecida).

**Versão 0.3.0: abas controladas (galeria por categoria e concorrentes).** Na primeira captura real (2026-10-09), os dados do perfil e as avaliações chegaram, mas a galeria e a busca não. Os botões da galeria não foram achados pelo nome (o Maps do usuário aparece em inglês, "From the owner"), e a busca montada na caixa de pesquisa falhou. Mudanças:
- Depois das avaliações, a aba do perfil pede ao service worker (`seals:extra`) as abas controladas, abertas **uma de cada vez**, ativas (a lista só carrega rolando numa aba visível), e fechadas sozinhas, voltando à aba do perfil:
  - Galeria por categoria, pela URL, com o código **lido da própria fonte A** (não fixo): o endereço do perfil com `!10e5!14m1!1B<código>` no bloco do local e as contagens `!4m`/`!3m` ajustadas (`src/lib/urls.js`, `galleryUrl`). **Formato conferido numa URL real do Maps (2026-10-10):** `…!4m9!3m8!1s<ftid>!8m2!3d…!4d…!10e5!14m1!1BCgIgARICEAE!16s…`, com o código **sem o `=` final e sem codificação**. A 0.3.0 mandava `%3D` no fim, provável causa de a galeria não ter aberto na segunda captura real. Só para as categorias que existem na fonte A.
  - Caminho alternativo (não usado): na galeria da **busca do Google**, a categoria abre com `#lpg=cid:<código>` (por exemplo `#lpg=cid:CgIgARICEAE%3D`), com os mesmos códigos e rótulos em inglês "All", "By owner", "Street View & 360°" e "Videos". O formato da resposta da busca ainda não foi mapeado.
  - **Diagnóstico, 0.3.2:** a terceira captura real (0.3.1) ainda não trouxe a galeria ("a primeira página não chegou pela rede") e trouxe só 1 página de concorrentes. Para não corrigir às cegas, cada aba controlada agora devolve um diagnóstico, guardado no bruto da captura (`diagnostics`):
    - os pedidos que a página fez ao Google, só o caminho e o `rpcids`/`tbm`, sem nenhum outro parâmetro nem conteúdo;
    - se achou o elemento que rola e o tamanho dele;
    - os rótulos dos botões visíveis;
    - quantas páginas chegaram.

    Reserva da galeria na aba controlada: se a primeira página não vier pela rede, clica num outro bloco de categoria e volta no desejado. A procura de botões passou a incluir `[role=button]` (os blocos de categoria do Maps).
  - **Resultado da quarta captura real (0.3.2, 2026-10-10):** a galeria funcionou, mas não pela URL sozinha. A aba abre na categoria certa, a primeira página vem embutida e só chega pela rede (`hspqX`) depois do clique nos blocos de categoria. "Do proprietário" veio inteira (8 itens, `[10]` = True), com a última foto em 09/05/2026; "Vídeos" trouxe 3, igual à tela. Nos concorrentes, a lista foi achada (7271/1036 px), mas rolar de uma vez até o fim não fez o Maps pedir a página 2.
  - Concorrentes, 0.3.8: o rastro da 0.3.7 mostrou que os pedidos da página 2 em diante são `XMLHttpRequest` sem nenhum sinal de fim (nem `load`, nem `loadend`, nem aborto), embora os resultados apareçam na tela: o pedido entrega em partes e fica aberto. Só para a busca, o hook agora entrega quando o texto já recebido forma um JSON completo (sem o prefixo `)]}'`), sem esperar o pedido fechar, uma vez só. A página 1 termina em `]]]]`, sem a marca `/*""*/`.
  - Concorrentes, 0.3.7: com a rolagem da 0.3.6, a lista cresceu para cerca de 38 mil px e o Maps fez mais 3 pedidos `tbm=map`, mas só a resposta do primeiro chegou. Hipótese: os seguintes são `XMLHttpRequest` concluídos sem o evento `load` chegar ao nosso ouvinte. O hook agora entrega no primeiro sinal de fim (`readyState` 4, `load` ou `loadend`), uma vez só, e o rastro marca `[xhr]`/`[fetch]`, aborto e fim sem resposta.
  - Concorrentes, 0.3.6: conferido à mão que a busca tem bem mais de 20 resultados e termina em "Você chegou ao final da lista"; a rolagem por script chegava ao fundo do que estava carregado sem o Maps pedir mais. No fundo, a extensão agora leva o último item para a tela e faz pequenas subidas e descidas por até 12 s, esperando o pedido da próxima página. **Se ainda assim não vier, a alternativa (a decidir com o usuário) é a extensão pedir as páginas 2 e 3 direto, trocando o número da página no endereço `tbm=map` que o próprio Maps usou.**
  - Concorrentes, 0.3.5: o rastro da 0.3.4 mostrou que os dois pedidos `tbm=map` eram da abertura da página e que a rolagem não chegava ao fim (12 passos de cerca de 830 px numa lista de 11638 px). Agora rola até o fim, com limite de 40 passos, e encosta no fundo. O diagnóstico mostra até onde rolou.
  - Concorrentes, 0.3.3: rola em passos (80% da altura visível, com evento de roda e pausas curtas) e para no aviso de fim da lista. O diagnóstico marca "[fim da lista]".
  - Concorrentes, 0.3.1: rola o painel que contém a lista (o primeiro ancestral com rolagem do `[role=feed]`), porque a 0.3.0 rolava a própria lista e só veio 1 página.
  - Concorrentes: `https://www.google.com/maps/search/<categoria principal>/@<lat>,<lng>,13z?hl=pt-BR`, capturando as respostas `tbm=map` que o próprio Maps faz e rolando a lista até 3 páginas.
- Na aba controlada, a primeira página precisa chegar pela rede antes de rolar (até 15 s; se a página indicar um `<link>` de preload para essa resposta, ela é buscada). Senão, a tarefa volta sem dados e com o motivo, em vez de mandar uma lista sem a primeira página (que daria nota errada). Sinal de vida a cada 8 s; sem resposta em 90 s, desiste.
- Se a galeria pela URL não trouxer dados, a reserva é a aba do perfil procurar os botões pelos rótulos em português e inglês ("Do proprietário"/"From the owner"/"By owner", "Vídeos"/"Videos").
- O service worker monta e valida os endereços (só `https://www.google.com/maps…`, código no formato esperado, coordenadas válidas, categoria com até 100 caracteres) e só aceita `seals:extra` de uma aba com o clique liberado. As abas controladas só podem devolver texto (`seals:part`), com limite de tamanho. Leitura mínima da fonte A na extensão: categoria principal, coordenadas e códigos da galeria (`placeInfo`), só para montar os endereços.
- Os motivos de cada passo que não trouxe dados vão no bruto da captura (`extensionErrors`), para a próxima conferência.
- **Tela `/pre`:** "X de 20 itens avaliados" junto da nota e, quando faltam 3 ou mais, um aviso em destaque dizendo que a nota considera só os avaliados e não deve ir para cliente sem conferir. A lista mostra "Avaliados".

Passos da captura (`extension/src/content.js`), antes da 0.3.0:
1. Dados do perfil (fonte A): a última resposta `preview/place` da página. É preciso o Maps em português e o perfil aberto pela busca do Maps; senão, a extensão avisa e não envia.
2. Avaliações: aba "Avaliações", "Classificar" e "Mais recentes", rolando até 10 páginas.
3. Galeria: categoria "Do proprietário" (até 15 páginas).
4. Galeria: categoria "Vídeos" (até 8 páginas).
5. Concorrentes: digita a categoria principal na busca do Maps e rola até 3 páginas. É a única leitura de conteúdo feita na extensão: `[6][13][0]` da fonte A.
6. Envia ao service worker, que abre `/pre?id=` numa aba nova.

Passo que não acha o botão devolve `null`, e a fonte fica "não avaliado" no app. O leitor aceita `photosOwner` e `photosVideos`, que têm prioridade sobre a "Mais recentes", e a resposta da busca com `)]}'`, com o sufixo `/*""*/` ou embrulhada em `{"d": ...}`.

Testes: Python (`tests/test_pre_web.py`, `tests/test_extension_manifest.py` e os de `tests/test_maps_reader.py`) e `cd extension && node --test tests/*.test.js` (Node 24, sem dependências). Os testes não dependem do Google ao vivo: o hook usa `fetch` e XHR falsos, os passos rodam com relógio e cliques injetados, e o app recebe capturas montadas das fixtures anonimizadas.

**Conferência manual (feita em 2026-10-10, ver 12.9, fase 4; a lista fica como roteiro para repetir depois de mudanças grandes):** em 2 ou 3 perfis da referência, conferir:
- se o Maps abre em `www.google.com` ou em `google.com.br` (ver acima);
- se a `preview/place` chega ao abrir o perfil pela busca;
- se os rótulos "Avaliações", "Classificar", "Mais recentes", "Do proprietário", "Vídeos" e "Voltar" batem com os seletores;
- se as categorias da galeria usam o mesmo `hspqX`, com o fim marcado em `[10]`;
- se a busca chega como `tbm=map`;
- se os avisos e as notas fazem sentido em `/pre`.

Instalação e configuração (uma vez):
1. Com o app parado ou rodando, gerar o segredo: `./.venv/bin/python coletar.py segredo-extensao`. Ele é gravado no `.env` e mostrado uma única vez no terminal. Para trocar: `--novo`.
2. No Chrome, abrir `chrome://extensions`, ligar o "Modo do desenvolvedor", clicar em "Carregar sem compactação" e escolher a pasta `extension/` do projeto.
3. Copiar o ID que aparece no cartão da extensão (32 letras) e gravar no app: `./.venv/bin/python coletar.py id-extensao <ID>`.
4. Nos detalhes da extensão, abrir "Opções da extensão", colar o segredo do passo 1 e clicar em "Salvar". Com o app rodando (`./.venv/bin/python serve.py`, na porta padrão 8000, a única que a extensão alcança), clicar em "Testar conexão com o app".
5. Para usar, há três caminhos: o botão **Pré Análise SealsPro** acima do painel do negócio na busca do Google (abre o Maps numa aba nova e captura lá); o mesmo botão no topo do perfil no Google Maps em português; ou o ícone da extensão na barra.

Para atualizar depois de uma mudança na extensão: em `chrome://extensions`, clicar no ícone de recarregar do cartão "SealsPro Pré Análise". Depois, recarregar as abas do Google e do Maps que já estavam abertas, porque os content scripts só entram em abas carregadas depois disso. Se o manifest pedir permissão nova, o Chrome avisa (na 0.2.0 não pede).

## 14. Simulador de avaliações

Inspirado no "Simulador de Avaliações" do GBP Check (menu Ações da Análise Completa e da Pré), com código, textos e visual próprios. Visto em 2026-10-10.

- Onde: menu **Ações** das telas de resultado, tela `/simulador?local=` (última análise real da Completa) ou `/simulador?pre=` (pré análise). Só lê o banco; nada é gravado.
- Entrada: a distribuição de estrelas guardada na análise (`starDistribution`, 5 → 1). Sem ela, estima pela nota média e pela quantidade.
- Conta (`simulator.py`, função pura, testes em `tests/test_simulator.py` com conferência por força bruta): o Google mostra a média com uma casa, arredondando para cima a partir de 0,05; as contas usam inteiros em décimos.
  - **Meta:** quantas avaliações de 5 estrelas faltam para a nota mostrada chegar ao valor escolhido (padrão: o início da faixa seguinte).
  - **Em quanto tempo:** pelo ritmo de avaliações de 5 estrelas por dia, semana ou mês (ritmos prontos: Devagar, Constante, Intenso), com a data prevista.
  - **Para subir de faixa:** quantas faltam para cada faixa acima.
  - **Risco de queda:** quantas avaliações de 1, 2 ou 3 estrelas seguidas tiram a nota da faixa atual.
- Faixas próprias (limites iguais aos do simulador do GBP Check): Muito baixa 1,0 a 2,9; Baixa 3,0 a 3,8; Regular 3,9 a 4,2; Boa 4,3 a 4,6; Excelente 4,7 a 5,0. Conferido: no perfil de referência (22 avaliações, 5,0), 3, 3 e 5 avaliações de 1, 2 e 3 estrelas para cair, os mesmos números do original.
- Fora, por enquanto: exportar o plano em PDF (o original tem "Exportar plano").


## 15. Diagnóstico para ferramentas externas

O app mede; outra ferramenta (por exemplo, uma skill do Claude Code) pode agir a partir do diagnóstico, montando um plano de alterações que o usuário aprova e aplica pela API. As regras de avaliação não são copiadas para essa ferramenta: ela sempre pergunta ao app.

- Contrato: `./.venv/bin/python coletar.py diagnostico <local> [--analisar]` imprime um JSON (`diagnostico.py`) com `contrato`, `local`, `analise`, `perfil` e `itens`. Cada item traz `status`, `precisaAcao`, `situacao`, `orientacao`, `dados` (variáveis da mensagem), `comoResolver` (`texto`, `material`, `postagem`, `resposta` ou `cliente`), `campoApi` e `cuidado` (nome do negócio). `--analisar` faz uma análise real nova antes: é o "antes" do PDF comparativo. As notas são recalculadas com o motor atual a partir do bruto, sem gravar nada.
- **Mudar o formato quebra quem consome o JSON.** `tests/test_diagnostico.py` trava os campos. Ao mudar: subir `diagnostico.CONTRATO`. Item novo no motor precisa de `COMO_RESOLVER` (há teste).
- O app lê do Google e **só escreve para publicar as postagens que o usuário agendou** (seção 17), tudo em `posts/google_api.py` (teste trava).


## 16. Análise de Ranking (spec v0.1, planejamento)

Inspirada na "Análise de Ranking" do GBP Check, com código, textos e visual próprios. Observada em 2026-10-11 na conta da SealsPro (tela, scripts da página, artigos de ajuda e uma análise 3×3 do perfil de referência, "oftalmologista", 3 km, 9 créditos bônus). Respostas completas do original em `data/reference/ranking/gbpcheck_ranking_2026-10-11_*.json` (fora do git; 4 casos, 16.7). **Estado em 2026-10-11: fases R0 a R6 feitas (extensão 0.5.3, clique único); zoom calibrado com 8 casos e virou opção da análise (16.7).**

### 16.1 Como o original funciona

- **Entrada:** local (dos perfis sincronizados ou buscado no Google), palavra-chave (várias separadas por vírgula viram uma análise por palavra), raio de 0,5 a 3 km no menu ou de 0,1 a 10 km na barra, e grade de 3×3 a 15×15. O raio é a distância do centro até a borda: a grade é um quadrado de lado 2 × raio, centrado no local, com pontos igualmente espaçados. Dá para desligar pontos (clique ou shift e arrastar, para rios e áreas vazias) e criar pontos avulsos.
- **Execução no servidor deles:** a página manda a grade (`POST /agency/ranking`), o servidor busca e a página consulta o andamento (`/agency/ranking/status/<id>`) até terminar. Cada ponto guarda os **20 primeiros resultados** (por `place_id`) e a posição do local (`-1` = fora dos 20, mostrado como "20+"). Os pontos levaram de 3 a 13 s; a 3×3 inteira, cerca de 20 s. Anúncios não contam. Os nomes dos campos (`vicinity`, `user_ratings_total`, `business_status`) são os da Places API do Google; a fonte real da busca não é visível (hipótese).
- **Custo:** 1 crédito por ponto ativo e por palavra. O plano traz 500 créditos bônus por mês, que não acumulam (cerca de 10 grades 7×7). Créditos avulsos de R$ 20 por 500 a R$ 250 por 15.000 (R$ 0,04 a R$ 0,017 por ponto).
- **Métricas** (conferidas na análise de referência):
  - ARP: posição média nos pontos onde o local aparece;
  - ATRP: posição média em todos os pontos, contando "fora dos 20" como 21 (perfil de referência: (9 + 8 × 21) / 9 = 19,67);
  - SoLV: % dos pontos em que o local fica no top 3;
  - Encontrado em: pontos onde aparece / total.
  As métricas saem para o local e para **todos os concorrentes** que apareceram em algum ponto (96 na referência). A lista é ordenada por SoLV e, no empate, pelo ATRP (hipótese: reproduz os 5 primeiros, mas põe o perfil de referência em 48º, e o original mostra 53).
- **Tela de resultado:** mapa (Leaflet, com fundo do Google Maps e transparência ajustável) e um círculo por ponto com a posição (verde e amarelo = bem; laranja e vermelho = mal; "20+"); à esquerda, o local e os concorrentes com ARP, ATRP, SoLV e pontos encontrados. Clicar num concorrente mostra a grade dele. Embaixo, uma tabela pesquisável com verificado, média e total de avaliações.
- **Ações:** "Download PDF" (gerado no servidor) e "Repetir Análise" (mesmos parâmetros, resultado novo). Histórico com local, palavra, raio, grade, pontos, data, ARP, ATRP, SoLV e status. O blog cita agendamento diário, semanal, quinzenal ou mensal (campo `was_scheduled`); não aparece na tela vista.
- **SAB** (empresa sem endereço, que atende numa área): o original reconhece o local também pelo telefone e pelo site.

### 16.2 Fonte da busca: extensão própria (decidido em 2026-10-11)

Decisões do usuário: **coleta pela extensão** (grátis), **PDF pode usar internet** (para o fundo do mapa), **só clientes** (locais sincronizados). Agendamento: ver 16.6.

Como funciona (testado em 2026-10-11, 16.7): a busca do Maps aceita o ponto de vista no parâmetro `pb` da URL `https://www.google.com/search?tbm=map&...&q=<palavra>&pb=!1s<palavra>!4m8!1m3!1d<distância em m>!2d<lng>!3d<lat>!3m2!1i1024!2i768!4f13.1!7i20...`. A extensão pega essa URL no `<link>` de preload da própria busca do Maps e, para cada ponto, troca só `!1d`, `!2d` e `!3d`, faz o pedido na mesma origem (`www.google.com`) e entrega a resposta ao service worker, como já faz com a amostra de avaliações da busca (13.10, 0.4.4). Cada resposta traz 20 resultados em `[64]` (a fonte D da seção 13, já lida por `maps_reader.py`). Os anúncios (só 6 posições) ficam de fora. O local é reconhecido pelo place_id (`[78]`) ou CID (`[10]`).
- **Sem cookies** (`credentials: "omit"`): a resposta vem sem anúncios e sem a conta do usuário, o que reduz a personalização. Testado: funciona. A versão com cookies trouxe os mesmos 20 orgânicos mais 2 anúncios.
- **Ritmo:** 1,2 a 2 s entre pontos, como nos outros pedidos da extensão. Uma 7×7 leva cerca de 1,5 a 2 min; uma 15×15, cerca de 7 min. Primeira versão: até 9×9 (81 pontos), e as maiores ficam para depois de ver se aparece captcha ou bloqueio. No teste, 41 pedidos seguidos não tiveram problema.
- **Exceção à regra "a extensão só captura"**, como na 0.4.4: o `fetch` só para o caminho `/search?tbm=map`, só depois do clique e só na aba liberada. Concorrentes e posições são calculados no app, não na extensão.
- **Zoom (distância de visão, `!1d`):** muda muito o resultado. É opção de cada análise: Bairro (1 km, padrão), Região (4 km) e Cidade (16 km); ver 16.7. O zoom faz parte da série: análises com zooms diferentes não se comparam.

### 16.3 Arquitetura (feita)

- `ranking/` (Python, puro): `grid.py` (mesma geometria do original: quadrado de lado 2 × raio, linha a linha do sul para o norte; **igual ao original ponto a ponto** nas 4 referências), `reader.py` (lê a busca de um ponto: 20 primeiros orgânicos, sem anúncios; reconhece o cliente pelo place_id ou CID), `metrics.py` (ARP, ATRP, SoLV, encontrados e concorrentes; **reproduz as métricas dos 657 locais das 4 referências do original sem nenhuma divergência**), `config.py` (`RANKING_VERSION`, grades de 3×3 a 9×9, raios, distância de visão de 1.000 m), `service.py` (fluxo abaixo).
- Banco: tabelas `rankings` (parâmetros, situação, centro, grade, resultado, versão) e `ranking_points` (posição e 20 resultados de cada ponto). Tabelas novas, criadas sem mexer nas existentes. Bruto de cada ponto em `data/raw/ranking/<id>/<ponto>.json.gz`.
- Telas (`web/ranking.py`, `ranking.html`, `ranking_analise.html`, `static/ranking.js`): `/ranking?local=` (formulário e análises anteriores; botão "Ranking" na tela principal), `/ranking/analise?id=` (instruções, progresso e resultado: cartões de encontrado, ARP, ATRP e SoLV; mapa Leaflet com fundo do OpenStreetMap, um círculo colorido por ponto; lista de concorrentes clicável que redesenha a grade; grade em tabela; tabela de locais). O Carto (fundo de mapa) passou a pedir chave em 2026-10-11.
- **Fluxo (um clique, desde a extensão 0.5.1):** em `/ranking`, "Preparar análise" cria a análise `pendente` (cliente, palavra, grade, raio; o CID e o place_id vêm do último bruto da Completa) e a tela seguinte já pede à extensão para começar: manda **só o número da análise**; a extensão pergunta ao app, com o segredo, qual perfil abrir (`POST /ranking/tarefa`), abre o perfil numa aba nova e manda a `preview/place` (`/ranking/inicio`, com o número: o app confere que é o mesmo cliente), lê a tarefa, vai para a busca da palavra e, ponto a ponto, faz o pedido `tbm=map` sem cookies e manda a resposta (`/ranking/ponto`); no fim (`/ranking/fim`), fecha a aba do Maps e volta para a tela do app, que acompanha o progresso e mostra o resultado. Erro antes da coleta (perfil errado, sem dados) aparece na tela do app. **Reserva:** o botão **Ranking SealsPro** no perfil do Maps (abaixo do "Pré Análise SealsPro") faz o mesmo para a análise pendente daquele perfil.
- **Grades de 11×11 a 15×15 (extensão 0.5.3, 2026-10-11):** liberadas depois de cerca de 1.000 buscas no dia sem bloqueio. Conferido ao vivo: 15×15 de uma psiquiatra ("psiquiatra", 3 km, zoom Região, análise #22) em 8,2 minutos, 225 de 225 pontos lidos, sem captcha. O formulário mostra o tempo estimado de cada grade (`SECONDS_PER_POINT` = 1,9 s). Se o Google pedir verificação (resposta 429 ou página `/sorry/`), a extensão para a coleta com o aviso "o Google pediu uma verificação…" e, num lote, as palavras que faltam são canceladas (`BLOCKED_PREFIX`). Os círculos do mapa ficam menores nas grades grandes (tela: 30 px em 11×11, 26 px a partir de 13×13; PDF: pelo espaço entre os pontos, entre 14 e 30 px).
- **Desligar pontos da grade (2026-10-11):** para pontos sem gente (represa, mata, serra). Na tela de uma análise pronta, "Desligar pontos" deixa clicar nos pontos do mapa (×) e salvar (`POST /ranking/pontos?id=`, JSON `{"disabled": [índices]}`, com a proteção de origem das telas). Os números da análise são recalculados na hora com os pontos já guardados (`set_disabled`), e a escolha fica guardada por local, grade e raio (tabela `ranking_grid_prefs`): as próximas análises nascem com os mesmos pontos desligados (coluna `rankings.disabled`) e **nem buscam neles** (a tarefa leva só os pontos ligados; o app converte o número do pedido no índice da grade, `enabled_points`). Ponto religado que não foi buscado fica "sem leitura". Desligado aparece como "–" (ou ×) na grade, no mapa, na comparação (tendência "off", fora da contagem) e nos PDFs, e fica fora das métricas e dos concorrentes. Ao menos um ponto continua ligado.
- **Várias palavras-chave de uma vez (lote, extensão 0.5.2, 2026-10-11):** no campo de palavra-chave, separe por vírgula, ponto e vírgula ou linha (até `BATCH_MAX` = 5, sem repetir). Cada palavra vira uma análise com o mesmo `batch_id` (o id da primeira). O clique único começa pela primeira palavra; no fim de cada uma, `/ranking/fim` já inicia a próxima do lote **com o mesmo centro** (sem abrir o perfil de novo) e devolve a tarefa, e a extensão segue na mesma aba (`rankingEnd` com `next`); só no fim fecha a aba e volta ao app. Erro numa palavra não para o lote; cancelar no Maps cancela as que faltam. Tela `/ranking/lote?id=`: andamento de cada palavra, as métricas lado a lado, o "melhor resultado" (mais top 3; no empate, menor posição geral) e "Repetir as N palavras". O botão "Ranking SealsPro" no Maps, num lote, começa pela primeira palavra que falta. Achado num perfil de área de atendimento: "branding" 1º no centro, "agência de branding" 3º, "agência de publicidade" fora dos 20 em todos os pontos.
- **Perfis sem endereço público (área de atendimento), corrigido em 2026-10-11:** o Maps não tem pin para eles e devolve o centro do Brasil (um perfil de área de atendimento: -14,41; -51,32, zoom 4). As análises #12 e #13 rodaram ali, num mapa vazio, e deram 0 de 25. Agora, quando a `preview/place` vem sem endereço (`[6][39]`), o centro da grade é o endereço cadastrado na conta do Google (`storefrontAddress` do bruto da Completa), convertido em coordenadas pelo Nominatim do OpenStreetMap (`ranking/geocode.py`: rua com número, senão o bairro, senão a cidade). A análise guarda a origem em `center_source` (`maps`, `endereço`, `bairro` ou `cidade`) e a tela avisa. Se nada for localizado, a análise vira erro, com o motivo, em vez de rodar no lugar errado. A identificação do perfil na lista funciona igual para esses perfis (o Estúdio aparece em 2º para "branding" e em 3º para "agência de branding" perto do endereço cadastrado; para "agência de publicidade", fora dos 20).
- Segurança: os três pedidos da extensão têm a mesma checagem de `/pre/captura` (origem `chrome-extension://<id>` e segredo); o resto, a proteção de origem das outras telas. Na extensão (`src/lib/ranking.js`): a tarefa do app é validada (até 81 pontos, coordenadas, palavra, endereço da busca só em `https://www.google.com/maps/search/`); o único pedido novo do content script só sai para um endereço montado a partir do modelo `https://www.google.com/search?tbm=map&` da própria página, trocando só `!1d`, `!2d` e `!3d` (teste estático confere); sem resposta por 90 s, o service worker marca a análise como erro.
- **Exceção de segurança (decisão do usuário, 2026-10-11): `externally_connectable` só para `http://127.0.0.1:8000/*`.** É o canal do clique único (do Ranking e, desde a 0.6.0, da Busca de Leads, `seals:leads-run`): o Chrome só entrega mensagens de páginas nesse endereço, e o service worker confere a origem de novo (`rankingRun`). A mensagem leva só o número da análise; o que buscar vem do app, com o segredo. O Chrome confere o endereço, não o programa: com o app parado, outro programa na porta 8000 poderia mandar a mensagem, mas sem o app a extensão não consegue a tarefa e nada roda. `tests/test_extension_manifest.py` e `extension/tests/static.test.js` travam esse valor exato. **Se o app for para a internet, trocar esse endereço pelo domínio do app (só ele, com https) no manifest, nos dois testes e em `APP` de `src/lib/run.js`; nunca curinga de domínio nem sites de terceiros.**
- Testes: `tests/test_ranking.py` (grade, leitor, métricas, fluxo completo pelas rotas, ponto ilegível, cancelamento, segurança e nome com `<script>` escapado) e `extension/tests/ranking.test.js`.

### 16.4 Fases

- **R0. Referência do original: feita (2026-10-11)**, 4 análises (16.7).
- **R1. Prova de conceito: feita (16.7).**
- **R1b. Extensão: feita (0.5.0).**
- **R2. Motor e banco: feito** (16.3).
- **R3. Tela: feita** (16.3). "Repetir análise" (mesma palavra, grade e raio; a extensão começa sozinha) na tela da análise e no lembrete. Análise pendente há mais de 2 horas aparece como "Expirada" e não é mais aceita.
- **R4. Histórico e comparação: feito.** Uma "série" = mesmo local, palavra-chave, grade e raio (com outra grade ou raio os pontos não são os mesmos). Em `/ranking?local=`, cada série com 2 ou mais análises prontas mostra a evolução de ATRP (eixo invertido: subir é melhor) e SoLV; a tabela tem A e B para comparar. `/ranking/comparar?a=&b=` (`ranking/history.py`, `compare`): só da mesma série (senão, recusa); a mais antiga é o "antes"; números do perfil com diferença e tendência, as duas grades e a grade do que mudou (▲ ▼ =), os 10 principais concorrentes de agora com ATRP e SoLV antes e depois; avisa se o pin do perfil andou mais de 100 m. Achado: as análises #1 e #7 do perfil de referência, feitas com 35 minutos de diferença, deram a mesma grade (a medição é estável no curto prazo).
- **R5. PDF: feito** (`report/build_ranking.py`, `report/templates/ranking.html`, `/ranking/relatorio.pdf?id=`, botão "Baixar PDF" na análise pronta). Capa ("Ranking no Google Maps"), resumo com os 4 números em português simples, mapa com a grade, os 10 negócios mais bem posicionados (o cliente destacado, mesmo fora do top 10), evolução (só com análises prontas da mesma série em 2 datas diferentes, até a data da análise) e nota de critérios. Números arredondados para o cliente (56%, 4,8). **Exceção à regra do PDF offline (decisão do usuário):** o fundo do mapa são pedaços do OpenStreetMap baixados na hora (`fetch_tile`, com User-Agent próprio) e embutidos no PDF; sem internet, sai só a grade. Pontos sem leitura aparecem como "?", sem explicação no PDF (problemas ficam na tela). A quantidade de avaliações às vezes não vem na lista da busca do Maps (em alguns perfis): sai "–".
- **R5b. PDF comparativo (antes e depois): feito** (`build_ranking_comparison_report` em `report/build_ranking.py`, `report/templates/ranking_comparativo.html`, `/ranking/comparativo.pdf?a=&b=`; botão "Baixar comparativo (PDF)" na tela de comparação e ao lado de "Comparar" na lista). Só duas análises prontas da mesma série; a mais antiga é o "antes". Capa ("Evolução no Google Maps", de/até), tabela dos 4 números com antes, depois e diferença, duas frases-resumo, os dois mapas lado a lado (pedaços do mapa baixados uma vez para os dois), a grade do que mudou (▲ ▼ =), os principais concorrentes de agora com posição geral e top 3 antes e agora, evolução (com 3 ou mais análises prontas no período, como no comparativo da Completa) e nota de critérios dizendo que as duas usaram a mesma busca, grade e zoom.
- **R6. Lembrete: feito.** `ranking/history.py`, `due`: séries de locais ativos cuja última análise pronta tem mais de `REMINDER_DAYS` (30) dias e que não têm outra pendente ou em coleta depois. Bloco "Para repetir" no topo de `/ranking`, com o botão Repetir, e contador no botão "Ranking" da tela principal.
- **R7. Prospecção:** fora (decidido: só clientes).

### 16.5 Perguntas em aberto

- Que tipo de busca o original faz em cada ponto (os nomes de campo são os da Places API; o comportamento lembra uma busca que amplia a área quando há poucos concorrentes perto, 16.7). Hoje não dá para reproduzir com um zoom fixo.
- Como o original ordena os concorrentes (a hipótese de 16.1 falha na 48ª posição).
- Quantas análises grandes seguidas a busca aguenta sem captcha (15×15 conferida uma vez, depois de cerca de 1.000 buscas no dia).

### 16.6 Agendamento (decidido: lembrete)

No original, agendar é repetir a mesma análise sozinha (diária, semanal, quinzenal ou mensal). Com a coleta pela extensão, isso esbarra na regra de 13.10: **nada roda sem o clique do usuário, em segundo plano nem por horário**. Decisão do usuário (2026-10-11): **lembrete**, sem agendamento automático (fase R6).

### 16.7 Teste da busca por ponto (2026-10-11)

perfil de referência, "oftalmologista", os mesmos 9 pontos da análise do original de 2026-10-11 (3×3, 3 km), pedidos sem cookies cerca de 1 hora depois.
- Ponto central, por distância de visão (posição do perfil de referência; quantos dos 20 coincidem com os 20 do original): 800 m → 7º (16); 1.000 → 8º (14); 2.000 → 7º (14); 2.500 → 11º (11); 3.000 → 12º (10); 6.000 m ou mais → fora dos 20 (4 ou menos). O original deu 9º.
- Grade inteira com 1.000 e 2.000 m: encontrada só no centro, fora dos 20 nos outros 8 pontos, **igual ao original em 9 de 9**. Os 20 coincidem de 9 a 14 por ponto.
- Conclusão: o original não usa a busca do Maps com o mesmo ponto de vista (os nomes de campo dele são os da Places API, 16.1), então a posição exata não vai bater sempre. O "encontrado / 20+" e a ordem de grandeza da posição batem. A nossa versão mede o que o Maps mostra naquele ponto de vista.

Mais 3 casos no mesmo dia (`seals_probe_2026-10-11_*.json` em `data/reference/ranking/`, gerados pela mesma busca, sem cookies; `encontrado` = mesmo "encontrado / 20+" que o original; `±2` = posição a até 2 do original, nos pontos em que os dois acham; coincidência = quantos dos 20 de cada ponto aparecem nos dois):

| Caso | Distância | Encontrado | ±2 | Coincidência média |
|---|---|---|---|---|
| Corretora de seguros, "corretora de seguros", 5×5, 2 km (só no centro: 17º no original) | 1.000 / 2.000 m | 25/25 / 25/25 | 0/1 (10º) / 1/1 (15º) | 9,4 / 10,3 de 20 |
| Salão de beleza, "salão de beleza", 5×5, 1 km (só no centro: 2º no original) | 500 / 1.000 m | 25/25 / 25/25 | 0/1 (8º) / 0/1 (13º) | 16,2 / 15,6 de 20 |
| Psiquiatra (cidade pequena), "psiquiatra", 5×5, 3 km (todos os pontos: 6º a 9º no original) | 500 a 4.000 m | 25/25 | 21 a 22/25 | cerca de 15 de 20 |

Leitura: o "encontrado / 20+" bateu em todos os 84 pontos dos 4 casos. A posição exata varia: na cidade pequena ficou quase sempre a até 2 (o nosso dá 1 a 2 posições melhores); no centro da capital, o original deu 2º ao salão e o Maps mostra entre 4º e 13º, conforme a distância. **Primeira análise pelo app (2026-10-11, #1):** perfil de referência 3×3, 3 km: encontrada só no centro, em 8º (original: 9º), ATRP 19,56 (original: 19,67), 75 concorrentes (original: 96).

**Mais 4 casos (2026-10-11, segmentos e cidades diferentes; `seals_probe_*` com 500, 1.000 e 2.000 m e, em dois, 4 e 16 km):**

| Caso (5×5) | Original | Melhor zoom | Encontrado igual | ATRP (original × nosso no melhor zoom) |
|---|---|---|---|---|
| Psiquiatra (capital), "psiquiatra", capital, 2 km | 20 de 25 pontos, SoLV 48% | 4 km | 23/25 | 7,8 × 5,6 |
| Urologista, "urologista", cidade vizinha, 3 km | 20 de 25, 5º a 20º | 16 km | 23/25 (a 1 km: 10/25) | 11,56 × 11,76 |
| Locadora de impressoras, "locação de impressoras", cidade do interior, 3 km | 1º em quase todos | qualquer | 25/25 | 1,04 × 1,04 |
| Clínica odontológica, "dentista", capital, 2 km | só no centro, 2º | 500 m a 1 km | 25/25 | 20,24 × 20,24 |

**Conclusão e decisão:** nenhum zoom fixo reproduz o original nos 8 casos. Em segmentos com muitos concorrentes perto, ele bate com zoom de bairro (0,5 a 2 km; com 6 km ou mais o perfil de referência some dos 20); em especialidades com poucos concorrentes perto, só com zoom amplo (urologista: 16 km). O original parece usar uma busca que amplia a área sozinha. Por isso o zoom virou opção da análise (Bairro 1 km como padrão, Região 4 km, Cidade 16 km), e a tela explica quando usar cada um. A nossa medição mostra o que o Maps exibe com aquele zoom; para comparar com o original, escolha o zoom pelo segmento.


## 17. Agendamento de postagens (spec v0.1, planejamento)

Inspirado no "Gerenciador de Atualizações" do GBP Check, com código, textos e visual próprios. Observado em 2026-10-13 no perfil do perfil de referência (só leitura, nada publicado nem alterado). Respostas guardadas em `data/reference/posts/` (fora do git).

Decisões do usuário (2026-10-13): **só Novidade** (Atualização) na primeira versão, sem Oferta nem Evento; **sem IA** (nem texto, nem banco de imagens); imagem só por upload; **tudo no Mac**, sem nuvem por enquanto. A escrita fica no gbp-sealspro (seção 15): o pacote `posts/`, o único que escreve no Google, e só publica postagens que o usuário pôs na fila. **Estado em 2026-10-13: implementado (17.3), agendador do macOS ligado e primeira publicação agendada conferida ao vivo.**

### 17.1 Como o original funciona

- Calendário por local (mês, semana, dia) e modo lista. Estados por cor: Agendada, Publicada, Falhou, Nova tentativa. Clicar num dia ou horário abre o formulário com a data.
- Formulário: abas Atualização, Oferta, Evento; texto até 1.500 caracteres com contador; imagem (JPG ou PNG, recorte, metadados gravados na imagem: título, descrição, palavras-chave, GPS, nome do arquivo); botão (Nenhum, Reservar, …) com URL; data e hora ("Agora" = "Publicar Agora"; com data, "Salvar Agendamento"); "Apagar Agendamento"; pré-visualização ao lado. Publicado: só leitura, com "Ver no Google" (`searchUrl`).
- Fuso por perfil (Ações > Escolher Fuso Horário); guarda hora local + `America/Sao_Paulo`.
- Registro no servidor deles: `status` (SCHEDULED, SUCCESS, falha), `state` do Google, `creation_response`, `postSearchUrl`, `retry`, `account_needs_reauth`.
- O agendador deles atrasa: post marcado para 12/10 às 9h44 foi criado no Google às 10h02.
- Texto com telefone (WhatsApp) foi aceito em 2 posts publicados.

### 17.2 Fase 0 (2026-10-13, perfil da SealsPro)

- **A imagem do post precisa de link (`sourceUrl`).** Mandar o arquivo direto (`media:startUpload` + `dataRef` no post) é recusado: "media[0].source_url is required".
- **Caminho sem hospedagem, que funcionou:** (1) `media:startUpload` e envio dos bytes para `https://mybusiness.googleapis.com/upload/v1/media/<ref>?upload_type=media`; (2) `POST .../media` com `dataRef` e categoria `ADDITIONAL` (a foto entra na galeria do perfil); (3) **reler a mídia** (`GET .../media/<id>`) até o `googleUrl` virar o definitivo (`lh3.googleusercontent.com/grass-cs/...=s0`); (4) criar o post com esse link em `sourceUrl`. Com o `googleUrl` provisório devolvido na criação (`/gpu-csl/...`), o post dá **erro 500**, duas vezes, sem criar nada.
- Efeito colateral: a foto também fica na galeria (ajuda os itens 14, 15 e 30 da Completa). O post guarda cópia própria da imagem (`media/localPosts/...`).
- Post criado em `PROCESSING` e `LIVE` menos de 1 minuto depois. O post e a foto de teste foram apagados no mesmo dia (`DELETE` em `localPosts/<id>` e `media/<id>`, os dois com resposta 200). Depois de processada, a foto da galeria troca de id (`CIAB…` vira `AF1Qip…`): para apagar, usar o id da listagem. O Google trocou `pt-BR` por `pt`.
- Erro 500 não criou post (conferido na lista): mesmo assim, o publicador deve conferir a lista antes de tentar de novo.
- **App OAuth publicado em 2026-10-13** (projeto `<id-do-projeto>`, app "<nome do app>", o mesmo client do gbp-sealspro): estava em "Testing" (refresh token vence em 7 dias) e passou para "In production", sem verificação (uso interno, 1 de 100 usuários; o login mostra "app não verificado" e segue por "Avançado"). Token novo gerado no mesmo dia com `fase0.py login`. Não enviar logo no Branding: com logo, o Google passa a exigir verificação. O token da skill `google-business-profile` é outro e precisa de login próprio. O agendador ainda deve avisar na tela quando o token falhar.

### 17.3 Implementação (2026-10-13)

- **Arquivos:** `posts/config.py` (limites), `posts/google_api.py` (o **único** arquivo que faz POST ao Google: foto e postagem; não apaga nada no Google; `tests/test_posts.py` trava as duas coisas), `posts/images.py` (confere e regrava a imagem), `posts/form.py` (validação), `posts/publisher.py` (fila), `posts/view.py` (calendário e alerta), `posts/launchd.py` (agendador do macOS), `web/postagens.py`, `web/templates/postagens.html` e `postagem.html`, `web/static/postagens.js`. Banco: tabela nova `posts` (criada sem mexer nas outras). Imagens em `data/posts/` e registros em `data/logs/` (fora do git).
- **Telas:** botão "Postagens" na tela principal. `/postagens?local=` com calendário do mês (domingo a sábado, clicar num dia futuro abre o formulário às 09:00) e lista; cores por estado: **Agendada** (azul), **Publicada** (verde), **Nova tentativa** e **Atrasada** (amarelo), **Falhou** e **Recusada** (vermelho). Formulário de Novidade: texto até 1.500 caracteres com contador, uma imagem, botão (Nenhum, Saiba mais, Reservar, Pedir on-line, Comprar, Inscrever-se, Ligar agora; "Ligar" não leva link), "Agendar para" (horário de Brasília) ou "Publicar agora" (pede confirmação), pré-visualização aproximada ao lado. Publicada e recusada ficam só leitura, com "Ver no Google"; agendada, atrasada e que falhou podem ser editadas, publicadas na hora ou apagadas da fila (apagar nunca mexe no Google).
- **Avisos na tela:** publicador desligado ou parado há mais de 30 minutos; login do Google vencido (com o comando); postagens que precisam de atenção; e o **item 29 da Completa**: última postagem (a mais recente entre as publicadas pelo app e as da última coleta da Completa), próxima agendada e a data em que o perfil passa de 30 dias sem postar.
- **Imagem:** a tela manda o arquivo sozinho (corpo do pedido, sem python-multipart) para `/postagens/imagem`. O app aceita JPG, PNG e WebP, corrige a orientação, tira a transparência, reduz para no máximo 1600 px e **regrava como JPEG sem metadados** (GPS do celular não vai para o perfil). Recusa abaixo de 250 px, acima de 15 MB e o que não abre. O Pillow passou a ser dependência do app (`requirements.txt`). Imagem enviada e não usada é apagada depois de 24 h.
- **Publicador** (`coletar.py publicar`; o agendador chama a cada 5 minutos e o launchd roda uma vez ao acordar o Mac):
  - cada postagem é "pega" por troca atômica de status no banco (`storage.claim_post`): a tela e o agendador podem rodar juntos sem publicar duas vezes; uma trava de arquivo impede duas passadas ao mesmo tempo;
  - com imagem: sobe a foto (o nome dela fica gravado: a nova tentativa não sobe de novo), espera o link definitivo (até 10 leituras, 3 s entre elas; link com `/gpu-csl/` = provisório, hipótese da Fase 0) e cria a postagem;
  - **nunca em dobro:** se já houve tentativa antes, procura no Google uma postagem com o mesmo texto criada desde a primeira tentativa (menos 10 min) e adota a que existir;
  - erro passageiro (rede, 429, 5xx, foto processando, login): nova tentativa em 2, 5, 15 e 30 min, e "Falhou" na 5ª; erro do conteúdo (4xx): "Falhou" na hora, com a mensagem do Google. Login vencido fica marcado e a tela mostra o comando;
  - **vencida há mais de 24 h sem nenhuma tentativa** (Mac desligado): fica **Atrasada** e só sai quando o usuário clicar em publicar ou reagendar; vencida há menos de 24 h sai sozinha, e a tela mostra "com atraso de X";
  - "publicando" há mais de 15 min (processo caiu): volta para a fila, com a checagem de duplicata;
  - relê no Google, por 3 dias, as que ficaram "processando" (viram no ar ou Recusada).
- **Ligar o agendador (uma vez):** `./.venv/bin/python coletar.py publicador instalar` (grava `~/Library/LaunchAgents/com.sealspro.gbp-publicador.plist` e carrega com `launchctl`); `publicador status` mostra se está carregado e a última passada; `publicador remover` desliga. Registros em `data/logs/publicador.log` e `publicador-launchd.log`. Depois de mudar o código do publicador, não precisa reinstalar (o agente chama o `coletar.py` do projeto); depois de mover a pasta do projeto, reinstale.
- **Testes:** `tests/test_posts.py` (42, com cliente falso: nada fala com o Google).
- **Fora desta versão:** Oferta e Evento, IA, recorte de imagem, metadados na imagem, fuso por perfil (fixo em Brasília), apagar postagem publicada, publicar o mesmo post em vários locais.
- **Primeira publicação agendada de verdade (2026-10-13, perfil da SealsPro, pela tela e pelo agendador):** agendada para 14h41, publicada pela passada do launchd às 14h41min43s (1 tentativa); a foto subiu às 17:41:47Z e o link definitivo (`/grass-cs/`) apareceu dentro da espera do publicador (menos de 30 s); postagem criada às 17:41:51Z em `PROCESSING` e lida como `LIVE` pela passada seguinte (14h46). Desta vez ficou "processando" por alguns minutos (na Fase 0, menos de 1). Post e foto apagados em seguida, e o registro de teste tirado do banco.
- **Hipóteses ainda abertas:** se aparecem outros formatos de link provisório além de `/gpu-csl/`, e se a espera de 30 s pela foto basta em horários de mais carga (se não bastar, a postagem vai para nova tentativa em 2 min, sem subir a foto de novo).


## 18. Busca de Leads (spec v0.1)

Inspirada na "Prospecção > Buscar Leads" do GBP Check, com código, textos e visual próprios. Observada em 2026-10-14 na conta da SealsPro (tela, scripts da página e a busca guardada "agencia de marketing" numa capital, 238 leads). **Estado em 2026-10-14: implementada e conferida ao vivo (extensão 0.6.0).**

### 18.1 Como o original funciona

- Entrada: palavra-chave (com sugestões) e região (autocompletar do Google Places). A busca roda no servidor deles, com barra de progresso; cada busca fica guardada e é reaberta pelo seletor do topo.
- Cada lead: nome, capa, telefone, site (alerta quando é rede social ou link encurtado), endereço (S.A.B quando não tem endereço), média e quantidade de avaliações, verificado, categorias, horário, notas, estrela de favorito e menu com "Analisar Website" e "Analisar Instagram".
- Filtros: tem ou não telefone, site e categorias adicionais; verificado ou não; só S.A.B ou sem S.A.B; com ou sem notas; média e quantidade de avaliações de/até; texto. Ordem: qualidade, média, quantidade, nome. Ver em tabela; planilha CSV dos filtrados ou de todos; nuvem de palavras dos nomes.
- "Qualidade estimada do perfil" (medida nos 238 leads): soma de telefone (+1 / −1), site (+1 próprio, +0,25 rede social, −0,25 sem), média (+1 a partir de 4,4; +0,5 de 4,0 a 4,3; −0,5 abaixo ou sem) e quantidade (−0,25 em **todos** os 238, até com 377 avaliações, o que parece falha), com piso 0, dividida por 4.

### 18.2 Como fizemos (decisões do usuário, 2026-10-14)

- **Fonte: a extensão, de graça,** pelo mesmo caminho do Ranking (16.2): a busca do Maps (`tbm=map`, sem cookies) em vários pontos. O app localiza a região pelo Nominatim (`leads/region.py`, o retângulo que o OpenStreetMap devolve), espalha uma grade de N×N pontos no centro de cada célula e, em cada ponto, lê até 3 páginas de 20 (`!8i<início>` logo depois de `!7i20`). Página com menos de 20 resultados: o app responde `skip` e a extensão não pede as seguintes daquele ponto. Teste de 2026-10-14 ("agencia de marketing", uma capital): 9 pontos com 1 página deram 115 a 131 leads distintos; 1 ponto com 4 páginas, 80, sem repetir.
- **Abrangência** (`leads/config.py`, `SCOPES`): Rápida 3×3 × 2 páginas (18 pedidos), Normal 3×3 × 3, Ampla 5×5 × 3, Muito ampla 7×7 × 3 (147 pedidos, cerca de 5 min). Zoom de cada ponto proporcional ao espaço entre os pontos, entre 2 e 16 km (hipótese). Região com mais de 80 km de lado é recusada; bairro pequeno vira pelo menos 2 km × 2 km.
- **Qualidade estimada: nossa, simples, sem coletar nada a mais** (`leads/quality.py`): os itens da Pré Análise que a busca alimenta (telefone, site com rede social = 50, horário, logotipo, verificado, quantidade e média de avaliações), com os mesmos cortes e a mesma nota geral (`scoring/base.py`). Fica na escala da pré análise que o lead receberá. A busca não traz descrição, postagens nem fotos. Sem o bloco de avaliações (`[4]` vazio) = 0 avaliações; nota sem quantidade = quantidade fora da conta. O pacote `leads/` só importa os itens; mudar `scoring/pre/` muda a qualidade das buscas novas (as guardadas mantêm a delas).
- Escopo da primeira versão: buscar, histórico de buscas, cartões, tabela e **mapa** (Leaflet com OpenStreetMap, cor pela qualidade, retângulo da região), filtros (os do original, mais site próprio ou rede social, só dentro da região, sem horário, favoritos e já tem pré análise), ordem (qualidade, média, quantidade, nome, ordem da busca), palavras mais comuns nos nomes, **notas e favoritos** (por negócio, valem em todas as buscas; apagar a busca não apaga), **planilha CSV** (filtrados na ordem da tela, ou todos; separada por ponto e vírgula, com BOM, e texto que começa com `= + - @` vira texto, nunca fórmula) e **Pré Análise do lead**: link para `local.google.com/place?id=<CID>` (o painel da busca, onde fica o botão "Pré Análise SealsPro"); quando o CID já tem pré análise, mostra a nota e o link. Telefone celular ganha link de WhatsApp.
- Fora, por enquanto: análise de site e de Instagram, sugestões de palavra-chave, agendamento.

### 18.3 Arquitetura

- `leads/`: `config.py`, `region.py`, `plan.py` (retângulo, grade, pedidos `[lat, lng, início]` e "dentro da região" com margem de 500 m), `reader.py` (uma página: leads com chave = place_id ou CID; anúncio fora), `quality.py`, `service.py` (fluxo e CSV).
- Banco (tabelas novas): `lead_searches` (parâmetros, região, pedidos, situação, resultado, versão), `lead_pages` (um por pedido; `organic` -1 = pulado), `lead_notes` e `lead_favorites` (por negócio). Bruto em `data/raw/leads/<id>/<pedido>.json.gz`.
- Telas (`web/leads.py`, `leads.html`, `leads_busca.html`, `static/leads.js`): `/leads` (formulário e buscas anteriores; botão "Buscar leads" na tela principal), `/leads/busca?id=` (andamento e resultado), `/leads/favoritos`. Os leads vão para a tela por `|tojson` e são montados só com `textContent`; link só com `http(s)` ou montado do CID (teste trava `innerHTML`, `eval` e afins).
- **Fluxo (um clique):** "Buscar leads" cria a busca pendente e a tela manda só o número para a extensão (`seals:leads-run`); a extensão pede a tarefa ao app com o segredo (`POST /leads/tarefa`, que passa a busca para "coletando"), abre a busca da palavra no Maps numa aba nova, faz os pedidos (`/leads/ponto`, a resposta traz `skip`) e no fim (`/leads/fim`) fecha a aba e volta para a tela, que mostra os leads. Cancelada ou com captcha, os leads já lidos ficam. Pendente há mais de 2 horas = expirada.
- Extensão 0.6.0: a tarefa ganhou `mode: "leads"` (pontos com a página) e a rota do app sai do `mode` (`appPrefix`); o resto é o código do Ranking (`runRanking`, `rankingPoint`, `rankingEnd`, `rankingTimeout`). Sem permissão nova.
- Testes: `tests/test_leads.py` (região, grade, leitor, qualidade, fluxo com páginas puladas e ilegíveis, cancelamento, expiração, notas, favoritos, CSV sem fórmula, segurança e `<script>` escapado) e `extension/tests/leads.test.js`.

### 18.4 Conferido ao vivo (2026-10-14)

"agência de marketing", numa capital, Rápida (busca #1): 18 de 18 páginas cheias em cerca de 40 s, **278 leads distintos** (o original deu 238 para a mesma busca), 237 dentro do retângulo da cidade, 57 sem endereço público (S.A.B), 76 sem nenhuma avaliação. Cartões, tabela, mapa, filtros, nota, favorito e planilha conferidos na tela.

### 18.5 Perguntas em aberto

- Zoom de cada ponto: o proporcional ao espaço entre os pontos é hipótese; no mapa da Rápida os leads se agrupam em volta dos 9 pontos (Ampla e Muito ampla cobrem melhor uma cidade grande).
- Quantas páginas por ponto o Google entrega antes de repetir ou acabar (até 4 conferidas).
- Quantas buscas grandes seguidas aguentam sem captcha (somam com as do Ranking).

