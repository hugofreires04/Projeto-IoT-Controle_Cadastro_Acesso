# Relatório Final — Sistema de Controle de Cadastro e Acesso via RFID

> **Disciplina:** ENG4051 — Projeto Internet das Coisas (PUC-Rio)
> **Grupo:** A3
> **Tema:** Controle de cadastro e acesso de funcionários via cartão RFID com catraca física, painel web de administração e registro histórico de acessos.

---

## 1. O que o sistema faz

Um funcionário aproxima seu cartão RFID da catraca. Em cerca de um segundo, o sistema decide se ele pode passar, aciona (ou não) a solenoide que libera a catraca, mostra o resultado no display E-Paper e grava o evento no banco de dados — com o motivo exato em caso de negação. Tudo isso fica visível em tempo quase real num painel web, onde o administrador também cadastra funcionários, gerencia cartões, lugares e contas de acesso.

## 2. Arquitetura de ponta a ponta

```
[Cartão RFID]
     │  leitura (MFRC522, SPI)
[ESP32-S3 — Catraca]
     │  publica MQTT: a3/catraca/entrada  {"uid": "E7 45 D6 19", "tipo": "entrada"}
[Broker MQTT]
     │
[Node-RED]  ── HTTP ──►  GET  /api/acesso/<uid>     (decide: libera ou nega?)
     │      ── HTTP ──►  POST /api/acesso/log       (grava o resultado)
     │  publica MQTT: a3/catraca/resposta  {"nome", "autorizado", "isAdmin"}
[ESP32-S3 — Catraca]
     │  aciona relé/solenoide + feedback no display E-Paper
     ▼
[Flask (API REST)] ◄──── HTTP/JSON ────► [Painel Web (login + permissões)]
     │
[PostgreSQL + TimescaleDB]  (hipertabela de registros de acesso)
```

**Decisão de projeto importante:** o Flask **não** fala MQTT diretamente. Toda a comunicação com o broker passa pelo Node-RED, que faz a "tradução" MQTT ↔ HTTP. Isso mantém cada peça com uma responsabilidade só: o ESP32 cuida do hardware, o Node-RED orquestra o fluxo, o Flask concentra a regra de negócio e o banco guarda o histórico.

## 3. O fluxo de acesso, passo a passo

1. O ESP32 lê o UID do cartão (biblioteca MFRC522) e publica em `a3/catraca/entrada`.
2. O Node-RED recebe a mensagem e chama `GET /api/acesso/<uid>` no Flask.
3. O Flask **classifica** o cartão consultando o banco (função `_classificar_uid` em `routes/acessos.py`):
   - cartão não existe → `negado_desconhecido`
   - cartão ou funcionário inativo → `negado_inativo`
   - tudo ok → `liberado`
4. O Node-RED chama `POST /api/acesso/log`, que grava o registro na hipertabela `a3_registros_acesso` com o resultado detalhado.
5. O Node-RED publica a resposta em `a3/catraca/resposta`: `{"nome": "...", "autorizado": bool, "isAdmin": bool}`.
6. O firmware libera a catraca (relé + solenoide) se `autorizado=true` e mostra o nome no display.

### Modo cadastro pela catraca (feature do grupo)

Se o dono do cartão tem conta **admin** no painel, a resposta traz `isAdmin=true` e o firmware entra em **modo cadastro**: a próxima leitura de cartão vai para o tópico `a3/cadastros` em vez de `a3/catraca/entrada`. O Node-RED repassa esse UID para `POST /api/cadastros/uid-pendente`, e ele aparece na aba **Cadastrar** do painel como um banner "Cartão novo lido na catraca", com botões *Usar este UID* e *Descartar*. Os UIDs pendentes:

- **empilham** (várias leituras seguidas aparecem da mais recente para a mais antiga);
- **expiram em 5 minutos** (TTL), para não aparecer cartão "fantasma" dias depois;
- são **removidos automaticamente** quando o cadastro é concluído com aquele UID.

Isso resolve o problema prático de digitar UIDs à mão: o admin passa o próprio cartão, encosta o cartão novo, e o UID já chega pronto no formulário.

## 4. Modelagem do banco de dados

Todas as tabelas usam o prefixo `a3_` (banco compartilhado com a turma). O modelo evoluiu do schema original (funcionário com `uid_cartao` embutido) para um modelo relacional completo, via migrations versionadas:

| Tabela | Papel |
|---|---|
| `a3_funcionarios` | A pessoa (nome, cargo, flag `ativo`) |
| `a3_cartoes_rfid` | Cartões, separados da pessoa — **um funcionário pode ter N cartões**, cada um com flag `ativo` própria (ex.: cartão perdido é desativado sem desativar a pessoa) |
| `a3_areas` | Lugares físicos controlados (Recepção, Laboratório, Datacenter…) |
| `a3_permissoes` | N:N cartão × área — quais lugares cada cartão pode acessar |
| `a3_usuarios` | Contas de login do painel (hash bcrypt da senha, nível `admin`/`operador`, vínculo opcional com funcionário) |
| `a3_sessoes` | Tokens de sessão (UUID gerado pelo Postgres, com expiração de 8h) |
| `a3_registros_acesso` | **Hipertabela TimescaleDB** — cada leitura de cartão, com resultado detalhado |
| `a3_uids_pendentes` | Fila temporária (TTL 5 min) de UIDs lidos na catraca em modo cadastro |

### Por que TimescaleDB?

`a3_registros_acesso` é uma série temporal: cresce continuamente e é consultada quase sempre por janela de tempo. A tabela foi convertida em **hipertabela** (`create_hypertable`), que particiona os dados por tempo automaticamente. O dashboard usa `time_bucket('1 day', data_hora)` — a mesma função apresentada em aula para os painéis do Grafana — para agregar os acessos por dia direto no banco.

### Resultado detalhado, não booleano

Em vez de um simples `autorizado: true/false`, cada registro guarda um dos quatro resultados: `liberado`, `negado_sem_permissao`, `negado_inativo`, `negado_desconhecido`. Isso permite auditoria real: dá para distinguir um cartão perdido/desativado de um cartão estranho tentando entrar.

## 5. Backend (Flask)

Organização em módulos pequenos, cada um com uma responsabilidade:

```
app.py               → cria a app, registra blueprints, CORS
config.py            → configuração via .env (python-dotenv)
db.py                → conexão psycopg2 (context manager) + normalização de UID
auth.py              → decorators @requer_login / @requer_admin
routes/
├── auth_routes.py   → login / logout / me
├── funcionarios.py  → cadastro completo + listagem + ativar/desativar pessoa e cartão
├── cadastros.py     → CRUD de lugares, CRUD de usuários, fila de UIDs pendentes
└── acessos.py       → listagem/estatísticas/CSV + endpoints consumidos pelo Node-RED
```

Pontos que valem destacar:

- **Autenticação feita "na mão"** (sem Flask-Login/JWT), de propósito, para o mecanismo ficar explícito: o login valida a senha com `bcrypt.checkpw`, cria uma linha em `a3_sessoes` com token UUID e expiração, e o decorator `@requer_login` valida o token no banco a cada requisição. Revogar sessão = deletar a linha (é o logout).
- **Senhas nunca em texto puro** — só o hash bcrypt (salt embutido). A mensagem de erro do login é a mesma para "e-mail inexistente" e "senha errada", para não vazar quais e-mails existem.
- **Todas as queries são parametrizadas** (`%s` do psycopg2) — proteção contra SQL injection.
- **Autorização no servidor, não na tela:** o operador só vê o próprio histórico porque o backend força o filtro pelo `id_funcionario` vinculado (em `_montar_filtros`); mesmo manipulando a URL da API não dá para ver dados de outra pessoa.
- **Cadastro transacional:** `POST /api/funcionarios` cria funcionário + cartão + permissões (+ conta de login opcional) numa única transação — ou grava tudo, ou nada.
- **Contrato estável com o Node-RED:** os endpoints da catraca respondem **sempre** JSON, mesmo em erro interno (o nó HTTP do Node-RED quebraria se recebesse a página HTML de erro do Flask).
- **Normalização de UID** (`db.py`): aceita `"E745D619"` ou `"E7 45 D6 19"` e armazena sempre no formato `XX XX XX XX` maiúsculo — evita duplicidade do mesmo cartão com formatação diferente.

## 6. Painel Web (frontend)

HTML/CSS/JavaScript **puros**, sem frameworks nem bibliotecas externas — tudo que aparece na tela é código do grupo. As páginas são servidas como arquivos estáticos pelo Flask e conversam com o backend só pela API REST.

### Páginas e permissões

| Página | Quem acessa | O que mostra |
|---|---|---|
| `login.html` | todos | Entrada com e-mail/senha; redireciona pelo nível |
| `admin.html` | admin | Painel completo em 6 abas |
| `operador.html` | operador | Apenas o próprio histórico de acessos |

### As abas do painel admin

1. **Dashboard** — visão geral: tiles com acessos de hoje (total, liberados, negados) e funcionários ativos, mais um **gráfico de colunas empilhadas dos últimos 7 dias** (liberados × negados × desconhecidos). Atualiza sozinho a cada 30 segundos, como um painel de monitoramento.
2. **Acessos** — tabela completa com filtros combinados (funcionário, lugar, período, resultado), aplicados automaticamente ao mudar; totalizador; paginação; **exportação CSV** respeitando os filtros ativos.
3. **Funcionários** — busca ao vivo por nome/cargo (com *debounce* de 300ms para não bombardear a API) e ativar/desativar pessoa ou cartão individualmente.
4. **Cadastrar** — formulário de cadastro completo + fila de UIDs pendentes vindos da catraca (atualizada a cada 5s).
5. **Lugares** — CRUD das áreas físicas.
6. **Usuários** — CRUD das contas do painel, com troca de nível direto na tabela e redefinição de senha.

### O gráfico do dashboard

Desenhado em **SVG puro via JavaScript** (`js/dashboard.js`), sem biblioteca de gráficos:

- agregação diária feita pelo banco (`time_bucket` do TimescaleDB) — o frontend só desenha;
- cores das séries **validadas para daltonismo** (separação ΔE ≥ 12 entre pares adjacentes sob deuteranopia) e com contraste ≥ 3:1 sobre o fundo;
- tooltip interativo por dia, legenda, eixo Y com valores "redondos", topo das colunas arredondado e respiro entre segmentos — detalhes que seguem boas práticas de visualização de dados;
- estado vazio amigável quando ainda não há registros.

### Design system em CSS

O `style.css` foi estruturado como um mini design system: todas as cores, sombras e raios vivem em **variáveis CSS** (`:root`), então o tema inteiro muda num lugar só. O visual usa a identidade navy do projeto na navegação e nos botões, cards brancos com sombra suave, badges em pílula para os status, anel de foco visível para navegação por teclado e layout responsivo (as abas rolam horizontalmente e as tabelas ganham scroll próprio no celular).

### Sessão no navegador

O token de sessão fica no `localStorage` e é enviado em toda chamada via header `Authorization: Bearer <token>` (wrapper `apiFetch` em `js/auth.js`). Qualquer resposta 401 derruba a sessão local e volta para o login — o tratamento é centralizado num único lugar.

## 7. Integração IoT (hardware ↔ nuvem)

- **Firmware (ESP32-S3 CAM):** leitor MFRC522 via SPI, display E-Paper WeAct 2.9" para feedback, relé SRD-05VDC acionando a solenoide JF-0530B, cliente MQTT com reconexão automática de WiFi/broker (padrão do curso: `reconectarWiFi()` + `reconectarMQTT()` no `setup()` e no `loop()`).
- **Tópicos MQTT:** `a3/catraca/entrada` (leituras), `a3/catraca/resposta` (decisão), `a3/cadastros` (modo cadastro). Prefixo `a3/` porque o broker é compartilhado com a turma.
- **Node-RED** (`nodered/flow_acesso.json`): assina os tópicos, chama a API do Flask e publica as respostas — é a cola entre o mundo MQTT e o mundo HTTP.
- **Servidor:** os serviços (broker, banco, Node-RED) rodam no servidor da disciplina; a aplicação Flask roda em **Docker** (arquivos em `.devcontainer/`, sobe com `docker compose -f .devcontainer/docker-compose.yml up`), lendo a configuração do `.env`.

## 8. Como rodar (resumo)

```bash
# 1. Banco: executar database/schema.sql e as migrations 002 → 003 → 004
# 2. Configuração
cp .env.example .env          # preencher DATABASE_URL etc.
# 3. Dependências e admin inicial
pip install -r requirements.txt
python setup_admin.py         # cria admin@sistema.com / admin123
# 4. Subir
python app.py                 # ou: docker compose -f .devcontainer/docker-compose.yml up --build
# → http://localhost:5000
```

O passo a passo completo (incluindo a importação do fluxo no Node-RED) está no `README.md`.

## 9. Linha do tempo do desenvolvimento

1. **Fluxo básico da catraca** — ESP32 → MQTT → Node-RED → Flask → banco, com log booleano de autorizado/negado.
2. **Login e permissões** — migration 002: cartões separados do funcionário, áreas, permissões N:N, usuários/sessões e o resultado de acesso detalhado; painel com níveis admin/operador.
3. **Prefixo `a3_`** — migration 003: convivência com os outros grupos no banco compartilhado.
4. **Cadastro pela catraca** — migration 004: modo cadastro via `isAdmin`, fila de UIDs pendentes com TTL e empilhamento; remoção do fluxo antigo de QR Code.
5. **Refino final** — correção de bugs (ativar/desativar funcionário), filtros de busca, CRUD de lugares e usuários, Docker, e a versão final do painel: redesign visual completo, aba Dashboard com estatísticas e gráfico, e código integralmente comentado.

## 10. Conceitos do curso aplicados

| Conceito (aula) | Onde aparece no projeto |
|---|---|
| RFID / MFRC522 (Teoria 05) | Leitura do UID na catraca; UID como identificador (sem gravar dados no cartão, por segurança) |
| MQTT (Teoria 02) | Toda a comunicação ESP32 ↔ servidor; tópicos `a3/*`; reconexão automática |
| TimescaleDB (Teoria 05) | Hipertabela `a3_registros_acesso`; `time_bucket` na agregação do dashboard |
| Node-RED | Orquestração MQTT ↔ HTTP do fluxo da catraca e do modo cadastro |
| Display E-Paper (Teoria 02) | Feedback visual ao funcionário na catraca |
| Relé + solenoide | Acionamento físico da catraca (nunca direto pelo ESP) |
| HTTPS/TLS e segurança | MQTT com TLS (porta 8883); bcrypt nas senhas; queries parametrizadas; autorização no servidor |
| Grafana (Teoria 05) | O mesmo padrão de painel temporal, implementado como dashboard próprio no painel web |

---

*Todo o código-fonte está comentado em português — cada arquivo explica no topo qual é o seu papel na arquitetura, e as decisões menos óbvias (TTL da fila de UIDs, contrato JSON com o Node-RED, restrição do operador no backend) estão documentadas junto do código que as implementa.*
