from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from unstuck.schema import Step


class Store:
    """SQLite persistence for tasks, steps, and completed-step records."""

    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def add_task(self, text: str, *, now: float | None = None) -> int:
        created_at = time.time() if now is None else now
        cursor = self.conn.execute(
            "insert into task (text, created_at) values (?, ?)",
            (text, created_at),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def add_steps(self, task_id: int, steps: list[Step]) -> None:
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
        rows = self.conn.execute(
            """
            select category, est_minutes, actual_minutes
            from record
            order by id
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def export_json(self) -> str:
        payload = {
            "tasks": self._table_rows("task"),
            "steps": self._table_rows("step"),
            "records": self._table_rows("record"),
        }
        return json.dumps(payload, indent=2)

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
