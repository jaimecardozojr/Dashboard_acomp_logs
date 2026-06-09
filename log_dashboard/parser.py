"""Parser dos arquivos de log -> lista de RunRecord (uma linha por execução).

Formato de cada linha:
    2026-06-09 07:06:07,937 [INFO] 🚀 Tentativa 1/3 — Iniciando automação unificada

Uma "sessão" começa em "Tentativa 1/N" (o contador volta a 1) e termina no
desfecho. Retries (Tentativa 2/3, 3/3) pertencem à mesma sessão.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .models import RunRecord, TaskRecord

# 2026-06-09 07:06:07,937 [INFO] mensagem
LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(?P<ms>\d{3})\s+"
    r"\[(?P<level>[A-Z]+)\]\s+(?P<msg>.*)$"
)

DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

# Marcadores de evento
RE_TENTATIVA = re.compile(r"Tentativa\s+(\d+)\s*/\s*(\d+)")
RE_SUCESSO = "finalizada com sucesso"
RE_ESGOTADAS = "tentativas esgotadas"
RE_TAREFA_GERADA = "Tarefa gerada"
RE_TAREFA_NUM = re.compile(r"Tarefa gerada:\s*(\S+)")
RE_NOVOS_REGISTROS = re.compile(r"(\d+)\s+novos?\s+registros?\s+adicionad")
RE_PENDENTES = re.compile(r"Há\s+(\d+)\s+tarefa")

CRIANDO_PREFIX = "Criando tarefa para "
RE_TITULO_SEP = re.compile(r"\|\s*T[íi]tulo:\s*")


class ParsedLine:
    __slots__ = ("ts", "level", "msg")

    def __init__(self, ts: datetime, level: str, msg: str):
        self.ts = ts
        self.level = level
        self.msg = msg


def _parse_line(line: str) -> Optional[ParsedLine]:
    m = LINE_RE.match(line)
    if not m:
        return None
    try:
        ts = datetime.strptime(
            f"{m.group('ts')}.{m.group('ms')}", "%Y-%m-%d %H:%M:%S.%f"
        )
    except ValueError:
        return None
    return ParsedLine(ts, m.group("level"), m.group("msg").strip())


def _iter_lines(path: Path) -> Iterator[ParsedLine]:
    """Itera linhas válidas. Linhas de continuação (tracebacks) são anexadas
    à última mensagem para preservar contexto de erro."""
    last: Optional[ParsedLine] = None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.rstrip("\n")
            if not raw:
                continue
            parsed = _parse_line(raw)
            if parsed is None:
                if last is not None and len(last.msg) < 500:
                    last.msg += " | " + raw.strip()
                continue
            if last is not None:
                yield last
            last = parsed
    if last is not None:
        yield last


def date_from_filename(path: Path) -> str:
    m = DATE_IN_NAME_RE.search(path.name)
    return m.group(1) if m else ""


def _segment_sessions(lines: list[ParsedLine]) -> Iterator[list[ParsedLine]]:
    """Quebra a lista de linhas em sessões. Nova sessão a cada 'Tentativa 1/N'."""
    current: list[ParsedLine] = []
    for ln in lines:
        m = RE_TENTATIVA.search(ln.msg)
        is_start = m is not None and int(m.group(1)) == 1
        if is_start and current:
            yield current
            current = []
        current.append(ln)
    if current:
        yield current


def _build_record(
    session: list[ParsedLine], automation: str, log_date: str, log_file: str, idx: int
) -> RunRecord:
    start = session[0].ts
    end = session[-1].ts

    attempts = 1
    tasks = 0
    new_records = 0
    pending = 0
    warnings = errors = criticals = 0
    status = "incompleto"
    last_error = ""

    for ln in session:
        lvl, msg = ln.level, ln.msg

        if lvl == "WARNING":
            warnings += 1
        elif lvl == "ERROR":
            errors += 1
            last_error = msg
        elif lvl == "CRITICAL":
            criticals += 1
            last_error = msg

        m = RE_TENTATIVA.search(msg)
        if m:
            attempts = max(attempts, int(m.group(1)))

        if RE_SUCESSO in msg:
            status = "sucesso"
        elif RE_ESGOTADAS in msg:
            status = "falha"

        if RE_TAREFA_GERADA in msg:
            tasks += 1

        mr = RE_NOVOS_REGISTROS.search(msg)
        if mr:
            new_records += int(mr.group(1))

        mp = RE_PENDENTES.search(msg)
        if mp:
            pending += int(mp.group(1))

    run_id = f"{automation}_{start.strftime('%Y%m%dT%H%M%S')}_{idx}"

    return RunRecord(
        run_id=run_id,
        automation=automation,
        date=log_date or start.strftime("%Y-%m-%d"),
        start_time=start.isoformat(timespec="seconds"),
        end_time=end.isoformat(timespec="seconds"),
        duration_seconds=round((end - start).total_seconds(), 1),
        status=status,
        attempts=attempts,
        tasks_generated=tasks,
        new_records=new_records,
        pending_tasks=pending,
        warnings=warnings,
        errors=errors,
        criticals=criticals,
        last_error=last_error[:300],
        log_file=log_file,
    )


def parse_file(path: str | Path, automation: str) -> list[RunRecord]:
    """Faz o parse de um arquivo de log -> lista de execuções (sessões)."""
    path = Path(path)
    log_date = date_from_filename(path)
    lines = list(_iter_lines(path))
    records: list[RunRecord] = []
    for i, session in enumerate(_segment_sessions(lines)):
        if not session:
            continue
        records.append(_build_record(session, automation, log_date, path.name, i))
    return records


def _split_nome_titulo(rest: str) -> tuple[str, str]:
    """'NOME | Título: X' -> ('NOME', 'X'); 'NOME' -> ('NOME', '')."""
    parts = RE_TITULO_SEP.split(rest, maxsplit=1)
    nome = parts[0].strip()
    titulo = parts[1].strip() if len(parts) > 1 else ""
    return nome, titulo


def parse_tasks_file(path: str | Path, automation: str) -> list[TaskRecord]:
    """Extrai as tarefas criadas (com número gerado) de um arquivo de log.

    Pareia cada '🔢 Tarefa gerada: <num>' com o '🛠️ Criando tarefa para <nome>'
    mais recente da mesma sessão (mesmo havendo linhas no meio)."""
    path = Path(path)
    log_date = date_from_filename(path)
    lines = list(_iter_lines(path))
    tasks: list[TaskRecord] = []

    for idx, session in enumerate(_segment_sessions(lines)):
        if not session:
            continue
        run_id = f"{automation}_{session[0].ts.strftime('%Y%m%dT%H%M%S')}_{idx}"
        pending_name = ""
        pending_title = ""
        for ln in session:
            if CRIANDO_PREFIX in ln.msg:
                rest = ln.msg.split(CRIANDO_PREFIX, 1)[1]
                pending_name, pending_title = _split_nome_titulo(rest)
                continue
            m = RE_TAREFA_NUM.search(ln.msg)
            if m:
                tasks.append(
                    TaskRecord(
                        task_number=m.group(1),
                        automation=automation,
                        person=pending_name,
                        title=pending_title,
                        date=log_date or ln.ts.strftime("%Y-%m-%d"),
                        created_at=ln.ts.isoformat(timespec="seconds"),
                        run_id=run_id,
                        log_file=path.name,
                    )
                )
                pending_name = ""
                pending_title = ""
    return tasks


def discover_log_files(logs_root: str | Path, automation_keys: Iterable[str]) -> list[tuple[Path, str]]:
    """Encontra (arquivo.log, automation) sob logs_root/<automation>/<mes_ano>/."""
    root = Path(logs_root)
    found: list[tuple[Path, str]] = []
    for key in automation_keys:
        base = root / key
        if not base.exists():
            continue
        for log_path in base.rglob("*.log"):
            found.append((log_path, key))
    return found


def parse_all(logs_root: str | Path, automation_keys: Iterable[str]) -> list[RunRecord]:
    """Faz o parse de todos os logs encontrados (execuções)."""
    records: list[RunRecord] = []
    for log_path, automation in discover_log_files(logs_root, automation_keys):
        records.extend(parse_file(log_path, automation))
    records.sort(key=lambda r: r.start_time)
    return records


def parse_tasks_all(logs_root: str | Path, automation_keys: Iterable[str]) -> list[TaskRecord]:
    """Faz o parse de todos os logs e devolve as tarefas criadas."""
    tasks: list[TaskRecord] = []
    for log_path, automation in discover_log_files(logs_root, automation_keys):
        tasks.extend(parse_tasks_file(log_path, automation))
    tasks.sort(key=lambda t: t.created_at)
    return tasks
