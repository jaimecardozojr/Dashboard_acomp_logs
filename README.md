# 📊 Dashboard de Acompanhamento de Automações

Monitoramento dos logs das automações diárias de RH (**admissão**, **férias** e **rescisão**).
Um robô lê os arquivos de log, extrai uma linha por execução e alimenta uma planilha do
Google Sheets, que por sua vez abastece um dashboard Streamlit publicável online.

```
   ┌──────────────┐      ┌───────────────┐      ┌──────────────────────┐
   │  Robô local  │ ───► │ Google Sheets │ ───► │  Dashboard Streamlit │
   │ (lê P:\logs) │      │  (execucoes)  │      │       (online)       │
   └──────────────┘      └───────────────┘      └──────────────────────┘
```

Por que o Google Sheets no meio? O dashboard online (Streamlit Cloud) **não enxerga o
drive de rede `P:\`**. O robô roda na máquina que tem acesso aos logs e publica os dados
agregados na planilha; o dashboard só lê a planilha. A camada de dados é trocável, então
dá para migrar para um banco depois sem mexer no dashboard.

---

## 📁 Estrutura

```
dashboard_acomp_log/
├── config.yaml                # caminhos, automações e backend de dados
├── requirements.txt
├── .env.example               # credenciais do robô (copie p/ .env)
├── log_dashboard/             # núcleo (sem Streamlit)
│   ├── parser.py              # logs .log  ->  RunRecord (1 por execução)
│   ├── models.py              # modelo de dados de uma execução
│   ├── config.py              # leitura do config.yaml
│   ├── collector.py           # o robô: parse -> storage
│   └── storage/               # camada trocável
│       ├── base.py            # interface (sync idempotente + upsert)
│       ├── local.py           # CSV local (dev)
│       └── gsheets.py         # Google Sheets (produção)
├── app/                       # dashboard
│   ├── streamlit_app.py       # página principal
│   ├── data.py                # carga de dados (Sheets ou CSV)
│   ├── ui.py                  # componentes + tema dos gráficos
│   └── assets/style.css       # estilo visual
├── scripts/
│   ├── run_collector.py       # entrypoint do robô (agendar)
│   └── run_dashboard.ps1      # sobe o dashboard local
└── tests/                     # testes do parser e do storage
```

### Duas entidades extraídas dos logs
1. **Execuções** (aba `execucoes`): cada arquivo contém **várias execuções por dia**.
   Uma execução vai de `🚀 Tentativa 1/3` até `✅ ...sucesso` ou `🚨 ...tentativas
   esgotadas` (retries fazem parte da mesma execução). Campos: status, tentativas,
   tarefas geradas, novos registros, erros/avisos e a última mensagem de erro.
2. **Tarefas criadas** (aba `tarefas`): cada `🔢 Tarefa gerada: <nº>` pareado com o
   `🛠️ Criando tarefa para <nome>` correspondente. Campos: **nome da pessoa, dia,
   número da tarefa**, título (rescisão), automação e horário. O número é gravado como
   texto para preservar os zeros à esquerda.

No dashboard, cada entidade tem sua aba (**📈 Execuções** e **✅ Tarefas criadas**), com a
tabela de tarefas exportável em CSV.

---

## 🚀 Setup rápido (local, sem Google)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 1) Crie seu config local a partir do modelo e ajuste o caminho dos logs
copy config.example.yaml config.yaml

# 2) Gera os dados a partir dos logs (modo CSV local)
python scripts/run_collector.py --backend local

# 3) Sobe o dashboard
streamlit run app/streamlit_app.py
```

> O `config.yaml` fica **fora do git** (contém caminhos/IDs internos). Versionamos apenas
> o `config.example.yaml`. Sem `config.yaml`, o projeto usa o modelo automaticamente.

O dashboard abre em `http://localhost:8501`. Sem segredos configurados, ele lê o CSV de
`data/execucoes.csv` automaticamente.

---

## ☁️ Colocando em produção (Google Sheets + online)

### 1. Criar a conta de serviço do Google
1. Acesse <https://console.cloud.google.com> → crie/escolha um projeto.
2. **APIs e serviços → Biblioteca**: ative **Google Sheets API** e **Google Drive API**.
3. **IAM → Contas de serviço → Criar conta de serviço**.
4. Na conta criada → **Chaves → Adicionar chave → JSON**. Baixe o arquivo e salve como
   `service_account.json` na raiz do projeto (já está no `.gitignore`).

### 2. Criar e compartilhar a planilha
1. Crie uma planilha no Google Sheets chamada **`Acompanhamento Automacoes`**
   (ou ajuste o nome no `config.yaml`).
2. Clique em **Compartilhar** e adicione o e-mail da conta de serviço
   (`...@...iam.gserviceaccount.com`) como **Editor**.

> A aba `execucoes` e o cabeçalho são criados automaticamente na primeira execução.

### 3. Rodar o robô apontando para o Sheets
```powershell
copy .env.example .env     # garanta GOOGLE_APPLICATION_CREDENTIALS=service_account.json
python scripts/run_collector.py            # backend gsheets (padrão do config.yaml)
```

### 4. Agendar o robô (Agendador de Tarefas do Windows)
Crie uma tarefa que rode, por exemplo, a cada hora:

- **Programa:** `C:\caminho\para\.venv\Scripts\python.exe`
- **Argumentos:** `scripts\run_collector.py`
- **Iniciar em:** `C:\caminho\para\dashboard_acomp_log`

A sincronização é **idempotente**: só grava execuções novas e atualiza as que estavam
`incompleto` (robô ainda rodando) quando elas concluem.

### 5. Publicar o dashboard (Streamlit Community Cloud — grátis)
1. Suba o projeto para um repositório no GitHub (**sem** o `service_account.json`).
2. Em <https://share.streamlit.io> → **New app** → aponte para `app/streamlit_app.py`.
3. Em **Settings → Secrets**, cole o conteúdo de
   [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example) preenchido com os
   dados do `service_account.json`, o nome da planilha e o `gestta_task_url`
   (o ID do dashboard Gestta fica nos secrets, não no repositório).
4. Deploy. Compartilhe o link com quem precisa analisar os logs.

---

## 🔧 Configuração

Tudo que muda de ambiente fica em `config.yaml` (caminhos, automações, backend) e em
segredos (`.env` para o robô, `secrets.toml` para o dashboard). Para adicionar uma nova
automação, basta criar a pasta de log correspondente e acrescentar uma entrada em
`automations:` no `config.yaml` — parser, robô e dashboard passam a cobri-la sem mudança
de código.

---

## ✅ Testes

```powershell
pip install pytest
python -m pytest tests/ -q
```

---

## 📈 Escalando depois

- **Mais automações:** só adicionar no `config.yaml`.
- **Banco de dados:** criar `log_dashboard/storage/postgres.py` implementando a interface
  `Storage` e registrar em `storage/__init__.py`. Dashboard e robô não mudam.
- **Histórico grande:** migrar do Sheets para Postgres/BigQuery (a planilha tem limite de
  ~10M células) usando o mesmo contrato de storage.
- **Alertas:** o `collector` já tem o resultado de cada execução — dá para disparar e-mail/
  Teams quando `status == 'falha'`.
