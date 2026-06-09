"""Testes do parser usando logs sintéticos (não dependem do P:\\)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from log_dashboard.parser import date_from_filename, parse_file, parse_tasks_file  # noqa: E402

SUCESSO = """\
2026-06-09 07:06:07,937 [INFO] 🚀 Tentativa 1/3 — Iniciando automação unificada
2026-06-09 07:06:18,030 [INFO] Logado
2026-06-09 07:06:51,414 [INFO] 🚀 Processando: EMPREGADO
2026-06-09 07:07:04,637 [INFO] ✅ 2 novos registros adicionados
2026-06-09 07:07:34,476 [INFO] 🔢 Tarefa gerada: 0000015730
2026-06-09 07:07:41,094 [INFO] ✅ Automação finalizada com sucesso
"""

FALHA = """\
2026-06-02 12:23:00,000 [INFO] 🚀 Tentativa 1/3 — Iniciando automação unificada
2026-06-02 12:23:29,227 [ERROR] Erro ao processar tipo: estagiario
2026-06-02 12:23:31,651 [ERROR] ❌ Falha na tentativa 1/3
2026-06-02 12:25:00,000 [INFO] 🚀 Tentativa 2/3 — Iniciando automação unificada
2026-06-02 12:25:24,688 [ERROR] ❌ Falha na tentativa 2/3
2026-06-02 12:27:00,000 [INFO] 🚀 Tentativa 3/3 — Iniciando automação unificada
2026-06-02 12:27:16,996 [ERROR] ❌ Falha na tentativa 3/3
2026-06-02 12:27:21,109 [CRITICAL] 🚨 3 tentativas esgotadas. Encerrando aplicativo.
"""

# Duas sessões no mesmo arquivo (robô roda várias vezes ao dia)
DUAS_SESSOES = SUCESSO + """\
2026-06-09 07:28:05,886 [INFO] 🚀 Tentativa 1/3 — Iniciando automação unificada
2026-06-09 07:28:36,403 [INFO] Logado
2026-06-09 07:29:37,571 [INFO] ✅ Automação finalizada com sucesso
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_data_from_filename():
    assert date_from_filename(Path("log_admissao_unificada_2026-06-09.log")) == "2026-06-09"
    assert date_from_filename(Path("log_Ferias_calculo_2026-06-08.log")) == "2026-06-08"


def test_sessao_sucesso(tmp_path):
    p = _write(tmp_path, "log_admissao_2026-06-09.log", SUCESSO)
    recs = parse_file(p, "admissao")
    assert len(recs) == 1
    r = recs[0]
    assert r.automation == "admissao"
    assert r.status == "sucesso"
    assert r.attempts == 1
    assert r.tasks_generated == 1
    assert r.new_records == 2
    assert r.errors == 0
    assert r.date == "2026-06-09"


def test_sessao_falha_com_retries(tmp_path):
    p = _write(tmp_path, "log_admissao_2026-06-02.log", FALHA)
    recs = parse_file(p, "admissao")
    assert len(recs) == 1
    r = recs[0]
    assert r.status == "falha"
    assert r.attempts == 3
    assert r.criticals == 1
    assert r.errors == 4
    assert r.tasks_generated == 0


def test_multiplas_sessoes_por_arquivo(tmp_path):
    p = _write(tmp_path, "log_admissao_2026-06-09.log", DUAS_SESSOES)
    recs = parse_file(p, "admissao")
    assert len(recs) == 2
    assert all(r.status == "sucesso" for r in recs)


def test_run_id_deterministico(tmp_path):
    p = _write(tmp_path, "log_admissao_2026-06-09.log", SUCESSO)
    a = parse_file(p, "admissao")[0]
    b = parse_file(p, "admissao")[0]
    assert a.run_id == b.run_id  # idempotência da deduplicação


# ----------------------------------------------------------------- tarefas

# Nomes fictícios de propósito (não usar dados reais em testes versionados).
TAREFA_ADMISSAO = """\
2026-06-09 09:20:00,000 [INFO] 🚀 Tentativa 1/3 — Iniciando automação unificada
2026-06-09 09:20:14,000 [INFO] 🛠️ Criando tarefa para Fulano De Tal
2026-06-09 09:21:06,000 [INFO] ⏳ Aguardando geração do número da tarefa...
2026-06-09 09:21:11,000 [INFO] 🔢 Tarefa gerada: 0000015715
2026-06-09 09:21:31,000 [INFO] ✅ Automação finalizada com sucesso
"""

TAREFA_RESCISAO = """\
2026-06-01 08:10:00,000 [INFO] 🚀 Tentativa 1/3 — Iniciando automação unificada
2026-06-01 08:10:54,000 [INFO] 🛠️ Criando tarefa para CICLANO TESTE DA SILVA | Título: DP - RESCISAO POR TERMINO DE CONTRATO
2026-06-01 08:11:46,000 [INFO] 🔢 Tarefa gerada: 0000015569
2026-06-01 08:12:00,000 [INFO] ✅ Automação finalizada com sucesso
"""


def test_tarefa_admissao_sem_titulo(tmp_path):
    p = _write(tmp_path, "log_admissao_2026-06-09.log", TAREFA_ADMISSAO)
    tasks = parse_tasks_file(p, "admissao")
    assert len(tasks) == 1
    t = tasks[0]
    assert t.task_number == "0000015715"
    assert t.person == "Fulano De Tal"
    assert t.title == ""
    assert t.date == "2026-06-09"
    assert t.automation == "admissao"


def test_tarefa_rescisao_com_titulo(tmp_path):
    p = _write(tmp_path, "log_rescisao_2026-06-01.log", TAREFA_RESCISAO)
    tasks = parse_tasks_file(p, "rescisao")
    assert len(tasks) == 1
    t = tasks[0]
    assert t.task_number == "0000015569"
    assert t.person == "CICLANO TESTE DA SILVA"
    assert t.title == "DP - RESCISAO POR TERMINO DE CONTRATO"


def test_tarefa_so_conta_com_numero(tmp_path):
    # "Criando tarefa" sem "Tarefa gerada" não vira registro
    content = TAREFA_ADMISSAO.replace("2026-06-09 09:21:11,000 [INFO] 🔢 Tarefa gerada: 0000015715\n", "")
    p = _write(tmp_path, "log_admissao_2026-06-09.log", content)
    assert parse_tasks_file(p, "admissao") == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
