class Light:
    def __init__(self, db):
        self.db = db

    def create(self, usage_id=None, x=None, y=None, z=None, power=None):
        query = """
        INSERT INTO Light (usage_id, x, y, z, power)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor = self.db.execute_query(query, (usage_id, x, y, z, power))
        if cursor:
            return (cursor.lastrowid,)
        return None

    def update(self, light_id, usage_id=None, x=None, y=None, z=None, power=None):
        updates = []
        params = []

        if usage_id is not None:
            updates.append("usage_id = %s")
            params.append(usage_id)
        if x is not None:
            updates.append("x = %s")
            params.append(x)
        if y is not None:
            updates.append("y = %s")
            params.append(y)
        if z is not None:
            updates.append("z = %s")
            params.append(z)
        if power is not None:
            updates.append("power = %s")
            params.append(power)

        if not updates:
            return False

        params.append(light_id)
        query = f"UPDATE Light SET {', '.join(updates)} WHERE light_id = %s"
        self.db.execute_query(query, tuple(params))
        return True

    def delete(self, light_id):
        query = "DELETE FROM Light WHERE light_id = %s"
        return bool(self.db.execute_query(query, (light_id,)))

    def get_by_id(self, light_id):
        query = """
        SELECT light_id, usage_id, x, y, z, power
        FROM Light
        WHERE light_id = %s
        """
        result = self.db.fetch_query(query, (light_id,))
        return result[0] if result else None

    def get_by_usage_id(self, usage_id):
        query = """
        SELECT light_id, usage_id, x, y, z, power
        FROM Light
        WHERE usage_id = %s
        """
        return self.db.fetch_query(query, (usage_id,))

    def get_all(self):
        query = """
        SELECT light_id, usage_id, x, y, z, power
        FROM Light
        """
        return self.db.fetch_query(query)