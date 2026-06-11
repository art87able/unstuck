from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any

from unstuck.schema import Step


class Store:
    """SQLite persistence for tasks, steps, and completed-step records."""

    def __init__(self, path: str = ":memory:") -> None:
        # Gradio calls handlers from worker threads; share one connection
        # across them and serialize access with a lock.
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._create_schema()

    def add_task(self, text: str, *, now: float | None = None) -> int:
        created_at = time.time() if now is None else now
        with self._lock:
            cursor = self.conn.execute(
                "insert into task (text, created_at) values (?, ?)",
                (text, created_at),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    def add_steps(self, task_id: int, steps: list[Step]) -> None:
        with self._lock:
            next_ord = self._next_step_ord(task_id)
            rows = [
                (task_id, step.text, step.category, step.est_minutes, next_ord + index)
                for index, step in enumerate(steps)
            ]
            self.conn.executemany(
                """
                insert into step (task_id, text, category, est_minutes, ord)
                values (?, ?, ?, ?, ?)
                """,
                rows,
            )
            self.conn.commit()

    def first_step_id(self, task_id: int) -> int:
        with self._lock:
            row = self.conn.execute(
                "select id from step where task_id = ? order by ord limit 1",
                (task_id,),
            ).fetchone()
        if row is None:
            raise LookupError(f"task {task_id} has no steps")
        return int(row["id"])

    def record_actual(
        self,
        step_id: int,
        category: str,
        est: int,
        actual: int,
        *,
        now: float | None = None,
    ) -> int:
        completed_at = time.time() if now is None else now
        with self._lock:
            cursor = self.conn.execute(
                """
                insert into record
                    (step_id, category, est_minutes, actual_minutes, completed_at)
                values (?, ?, ?, ?, ?)
                """,
                (step_id, category, est, actual, completed_at),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    def get_records(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                select category, est_minutes, actual_minutes
                from record
                order by id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def save_plan(self, task: str, rows_json: str) -> None:
        """Persist the latest visible plan snapshot as opaque row JSON."""
        saved_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self.conn.execute(
                """
                insert into plan_snapshot (id, task, rows_json, saved_at)
                values (1, ?, ?, ?)
                on conflict(id) do update set
                    task = excluded.task,
                    rows_json = excluded.rows_json,
                    saved_at = excluded.saved_at
                """,
                (task, rows_json, saved_at),
            )
            self.conn.commit()

    def load_plan(self) -> tuple[str, str] | None:
        """Return the last saved visible plan snapshot, if one exists."""
        with self._lock:
            row = self.conn.execute(
                "select task, rows_json from plan_snapshot where id = 1"
            ).fetchone()
        if row is None:
            return None
        return str(row["task"]), str(row["rows_json"])

    def clear_plan(self) -> None:
        """Forget the saved visible plan snapshot, if one exists."""
        with self._lock:
            self.conn.execute("delete from plan_snapshot where id = 1")
            self.conn.commit()

    def export_json(self) -> str:
        with self._lock:
            payload = {
                "tasks": self._table_rows("task"),
                "steps": self._table_rows("step"),
                "records": self._table_rows("record"),
            }
        return json.dumps(payload, indent=2)

    def import_json(self, payload: str) -> dict[str, int]:
        """Import calibration records from an export_json() payload."""
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid json") from exc

        rows = self._validate_import_payload(data)
        imported = 0
        skipped = 0
        with self._lock:
            for row in rows:
                duplicate = self.conn.execute(
                    """
                    select 1 from record
                    where category = ?
                      and est_minutes = ?
                      and actual_minutes = ?
                      and completed_at = ?
                    limit 1
                    """,
                    (
                        row["category"],
                        row["est_minutes"],
                        row["actual_minutes"],
                        row["completed_at"],
                    ),
                ).fetchone()
                if duplicate is not None:
                    skipped += 1
                    continue

                self.conn.execute(
                    """
                    insert into record
                        (step_id, category, est_minutes, actual_minutes, completed_at)
                    values (?, ?, ?, ?, ?)
                    """,
                    (
                        row["step_id"],
                        row["category"],
                        row["est_minutes"],
                        row["actual_minutes"],
                        row["completed_at"],
                    ),
                )
                imported += 1
            self.conn.commit()

        return {"imported": imported, "skipped": skipped}

    def _create_schema(self) -> None:
        self.conn.executescript(
            """
            create table if not exists task (
                id integer primary key,
                text text not null,
                created_at real not null
            );

            create table if not exists step (
                id integer primary key,
                task_id integer not null,
                text text not null,
                category text not null,
                est_minutes integer not null,
                ord integer not null
            );

            create table if not exists record (
                id integer primary key,
                step_id integer not null,
                category text not null,
                est_minutes integer not null,
                actual_minutes integer not null,
                completed_at real not null
            );

            create table if not exists plan_snapshot (
                id integer primary key check (id = 1),
                task text,
                rows_json text,
                saved_at text
            );
            """
        )
        self.conn.commit()

    def _next_step_ord(self, task_id: int) -> int:
        row = self.conn.execute(
            "select coalesce(max(ord) + 1, 0) as next_ord from step where task_id = ?",
            (task_id,),
        ).fetchone()
        return int(row["next_ord"])

    def _table_rows(self, table: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(f"select * from {table} order by id").fetchall()
        return [dict(row) for row in rows]

    def _validate_import_payload(self, data: Any) -> list[dict[str, Any]]:
        if not isinstance(data, dict):
            raise ValueError("payload must be an object")

        for key in ("tasks", "steps", "records"):
            if key not in data:
                raise ValueError(f"missing {key}")
            if not isinstance(data[key], list):
                raise ValueError(f"{key} must be a list")

        rows: list[dict[str, Any]] = []
        for index, row in enumerate(data["records"], start=1):
            if not isinstance(row, dict):
                raise ValueError(f"record {index} must be an object")

            category = row.get("category")
            est_minutes = row.get("est_minutes")
            actual_minutes = row.get("actual_minutes")
            step_id = row.get("step_id")
            completed_at = row.get("completed_at")

            if not isinstance(category, str):
                raise ValueError(f"record {index} category must be a string")
            if type(est_minutes) is not int or est_minutes <= 0:
                raise ValueError(f"record {index} est_minutes must be positive")
            if type(actual_minutes) is not int or actual_minutes <= 0:
                raise ValueError(f"record {index} actual_minutes must be positive")
            if type(step_id) is not int:
                raise ValueError(f"record {index} step_id must be an integer")
            if type(completed_at) not in (int, float):
                raise ValueError(f"record {index} completed_at must be numeric")

            rows.append(
                {
                    "step_id": step_id,
                    "category": category,
                    "est_minutes": est_minutes,
                    "actual_minutes": actual_minutes,
                    "completed_at": float(completed_at),
                }
            )

        return rows
