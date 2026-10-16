"""A tiny in-memory stand-in for the parts of supabase-py the backend uses."""

import itertools
import threading
from datetime import datetime, timezone
from types import SimpleNamespace


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, store, table):
        self.store = store
        self.table = table
        self.operation = "select"
        self.payload = None
        self.filters = []
        self.order_by = None
        self.row_limit = None

    def select(self, *columns, **kwargs):
        return self

    def insert(self, row):
        self.operation, self.payload = "insert", row
        return self

    def update(self, values):
        self.operation, self.payload = "update", values
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, column, desc=False):
        self.order_by = (column, desc)
        return self

    def limit(self, count):
        self.row_limit = count
        return self

    def _matches(self, row):
        return all(str(row.get(column)) == str(value) for column, value in self.filters)

    def execute(self):
        with self.store.lock:
            rows = self.store.tables.setdefault(self.table, [])

            if self.operation == "insert":
                row = dict(self.payload)
                row.setdefault("id", next(self.store.ids))
                row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                rows.append(row)
                return FakeResponse([dict(row)])

            matched = [row for row in rows if self._matches(row)]

            if self.operation == "update":
                for row in matched:
                    row.update(self.payload)
                return FakeResponse([dict(row) for row in matched])

            if self.operation == "delete":
                self.store.tables[self.table] = [row for row in rows if not self._matches(row)]
                return FakeResponse([dict(row) for row in matched])

            result = [dict(row) for row in matched]
            if self.order_by:
                column, desc = self.order_by
                result.sort(key=lambda row: row.get(column) or 0, reverse=desc)
            if self.row_limit is not None:
                result = result[: self.row_limit]
            return FakeResponse(result)


class FakeAuth:
    def __init__(self, tokens):
        self.tokens = tokens

    def get_user(self, token):
        user_id = self.tokens.get(token)
        return SimpleNamespace(user=SimpleNamespace(id=user_id) if user_id else None)


class FakeSupabase:
    def __init__(self, tables=None, tokens=None):
        self.tables = {name: [dict(row) for row in rows] for name, rows in (tables or {}).items()}
        self.ids = itertools.count(1000)
        self.lock = threading.RLock()
        self.auth = FakeAuth(tokens or {})
        self.rpc_calls = []

    def table(self, name):
        return FakeQuery(self, name)

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        documents = self.tables.get("knowledge_documents", [])
        return SimpleNamespace(execute=lambda: FakeResponse([dict(doc) for doc in documents]))
