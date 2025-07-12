class FakeResult:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class FakeTable:
    def __init__(self, store):
        self.store = store
        self._reset()

    def _reset(self):
        self._filters = []
        self._order = None
        self._limit = None
        self._update_data = None
        self._contains = None
        self._select = "*"
        self._count = None
        self._insert_data = None

    def insert(self, entry):
        self._insert_data = entry
        return self

    def update(self, fields):
        self._update_data = fields
        return self

    def select(self, columns="*", count=None):
        self._select = columns
        self._count = count
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        return self

    def contains(self, field, values):
        self._contains = (field, values)
        return self

    def order(self, field, desc=False):
        self._order = (field, desc)
        return self

    def limit(self, num):
        self._limit = num
        return self

    def execute(self):
        if self._insert_data is not None:
            self.store.append(self._insert_data)
            data = [self._insert_data]
            self._reset()
            return FakeResult(data)
        if self._update_data is not None:
            for row in self.store:
                if all(row.get(k) == v for k, v in self._filters):
                    row.update(self._update_data)
            self._reset()
            return FakeResult([])
        rows = self.store
        for k, v in self._filters:
            rows = [r for r in rows if r.get(k) == v]
        if self._contains:
            field, values = self._contains
            rows = [r for r in rows if set(values).issubset(set(r.get(field, [])))]
        if self._order:
            field, desc = self._order
            rows = sorted(rows, key=lambda r: r.get(field), reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        count = len(rows) if self._count else None
        self._reset()
        return FakeResult(rows, count=count)


class FakeSupabaseClient:
    def __init__(self):
        self._tables = {}

    def table(self, name):
        table = self._tables.setdefault(name, [])
        return FakeTable(table)
