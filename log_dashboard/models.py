"""Modelo de dados de uma execução (sessão) de automação."""
from __future__ import annotations

from dataclasses import dataclass, asdict, fields
from datetime import datetime
from typing import Optional


@dataclass
class RunRecord:
    """Uma sessão = uma execução agendada do robô (da 'Tentativa 1/N' até o
    desfecho: sucesso ou tentativas esgotadas). É uma linha na planilha."""

    run_id: str                 # chave determinística p/ deduplicação
    automation: str             # admissao | ferias | rescisao
    date: str                   # YYYY-MM-DD (data do arquivo de log)
    start_time: str             # ISO 8601
    end_time: str               # ISO 8601
    duration_seconds: float
    status: str                 # sucesso | falha | incompleto
    attempts: int               # nº da última tentativa (1..3)
    tasks_generated: int        # 🔢 Tarefa gerada
    new_records: int            # ✅ N novos registros adicionados
    pending_tasks: int          # 📂 Há N tarefa(s) pendente(s)
    warnings: int
    errors: int
    criticals: int
    last_error: str             # última mensagem de erro (contexto)
    log_file: str               # arquivo de origem

    # Ordem das colunas na planilha / CSV
    @classmethod
    def columns(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def to_row(self) -> dict:
        return asdict(self)

    @staticmethod
    def started_at(rec: dict) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(rec["start_time"])
        except (KeyError, ValueError, TypeError):
            return None


@dataclass
class TaskRecord:
    """Uma tarefa efetivamente criada (com número gerado) por uma automação."""

    task_number: str            # número gerado (ex.: 0000015730) — chave única
    automation: str             # admissao | ferias | rescisao
    person: str                 # nome da pessoa
    title: str                  # título da tarefa (quando houver)
    date: str                   # YYYY-MM-DD (dia da criação)
    created_at: str             # ISO 8601 (data/hora exata)
    run_id: str                 # execução que gerou a tarefa
    log_file: str

    @classmethod
    def columns(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def to_row(self) -> dict:
        return asdict(self)
