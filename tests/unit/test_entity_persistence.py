from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from cae_report_server.services import WorkbenchService


class CountingDatabase:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute(
            "CREATE TABLE connections(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, data_json TEXT NOT NULL)"
        )
        self.connection_count = 0

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.connection_count += 1
        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        with self.connect() as connection:
            connection.execute(sql, params)


def test_entity_collection_is_replaced_in_one_transaction(tmp_path: Path) -> None:
    database = CountingDatabase()
    service = WorkbenchService(database, tmp_path)  # type: ignore[arg-type]
    items = [{"id": index, "type": "RBE2", "raw_fields": [index]} for index in range(500)]

    service._replace_entities("connections", "run-large", items, "conn")

    assert database.connection_count == 1
    count = database.connection.execute("SELECT COUNT(*) FROM connections").fetchone()
    assert count == (500,)
