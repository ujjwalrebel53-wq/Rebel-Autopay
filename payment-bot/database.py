import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Payment:
    id: int
    utr: str
    amount: float
    created_at: str


class PaymentDatabase:
    def __init__(self, db_path: str = "payments.db"):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                utr TEXT NOT NULL UNIQUE,
                amount REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def utr_exists(self, utr: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM payments WHERE utr = ?", (utr,)
        ).fetchone()
        return row is not None

    def add_payment(self, utr: str, amount: float) -> Payment:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = self._conn.execute(
            "INSERT INTO payments (utr, amount, created_at) VALUES (?, ?, ?)",
            (utr, amount, created_at),
        )
        self._conn.commit()
        return Payment(
            id=cursor.lastrowid,
            utr=utr,
            amount=amount,
            created_at=created_at,
        )

    def get_total(self) -> float:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM payments"
        ).fetchone()
        return float(row["total"])

    def get_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS count FROM payments").fetchone()
        return int(row["count"])

    def get_recent(self, limit: int = 10) -> List[Payment]:
        rows = self._conn.execute(
            """
            SELECT id, utr, amount, created_at
            FROM payments
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            Payment(
                id=row["id"],
                utr=row["utr"],
                amount=row["amount"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_by_utr(self, utr: str) -> Optional[Payment]:
        row = self._conn.execute(
            "SELECT id, utr, amount, created_at FROM payments WHERE utr = ?",
            (utr,),
        ).fetchone()
        if row is None:
            return None
        return Payment(
            id=row["id"],
            utr=row["utr"],
            amount=row["amount"],
            created_at=row["created_at"],
        )
