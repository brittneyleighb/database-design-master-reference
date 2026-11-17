#!/usr/bin/env python3
"""Demonstrate SQLite atomicity and its limits across external services.

Requires only Python 3's standard library. No network requests or real payments.
"""
import sqlite3


def balances(connection):
    return dict(connection.execute("SELECT name, balance FROM accounts"))


def main():
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE TABLE accounts (name TEXT PRIMARY KEY, balance INTEGER NOT NULL)")
        db.executemany("INSERT INTO accounts VALUES (?, ?)", [("Ada", 100), ("Grace", 50)])
        db.commit()
        initial = {"Ada": 100, "Grace": 50}
        assert balances(db) == initial

        # A local transfer can be rolled back atomically.
        db.execute("BEGIN")
        db.execute("UPDATE accounts SET balance = balance - 20 WHERE name = 'Ada'")
        db.execute("UPDATE accounts SET balance = balance + 20 WHERE name = 'Grace'")
        db.rollback()
        assert balances(db) == initial
        print("PASS: local SQLite rollback restored both balances")

        # A committed transfer changes both accounts as a unit.
        db.execute("BEGIN")
        db.execute("UPDATE accounts SET balance = balance - 20 WHERE name = 'Ada'")
        db.execute("UPDATE accounts SET balance = balance + 20 WHERE name = 'Grace'")
        db.commit()
        assert balances(db) == {"Ada": 80, "Grace": 70}
        print("PASS: local SQLite commit persisted both updates")

        # This list represents an *independent* payment service, not real billing.
        external_payments = []
        try:
            db.execute("BEGIN")
            db.execute("UPDATE accounts SET balance = balance - 10 WHERE name = 'Ada'")
            external_payments.append({"kind": "charge", "amount": 10})
            raise RuntimeError("Simulated failure after external charge")
        except RuntimeError:
            db.rollback()

        assert balances(db) == {"Ada": 80, "Grace": 70}
        assert external_payments == [{"kind": "charge", "amount": 10}]
        print("PASS: database rolled back; simulated external charge remained")

        # Compensation is a NEW action, not part of the rolled-back transaction.
        external_payments.append({"kind": "refund", "amount": 10})
        assert external_payments[-1]["kind"] == "refund"
        print("PASS: simulated refund was a separate compensating action")
    finally:
        db.close()


if __name__ == "__main__":
    main()
