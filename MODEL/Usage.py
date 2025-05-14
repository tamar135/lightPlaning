class Usage:
    def __init__(self, db):
        self.db = db

    def create(self, user_id, usage_date=None, floor_plan=None, json_file=None):
        query = """
        INSERT INTO `usage` (user_id, usage_date, floor_plan, json_file)
        VALUES (%s, %s, %s, %s)
        """
        # אם usage_date לא סופק, מסד הנתונים ישתמש ב-CURRENT_TIMESTAMP כברירת מחדל
        cursor = self.db.execute_query(query, (user_id, usage_date, floor_plan, json_file))
        if cursor:
            # החזרת מילון במקום טאפל
            return {"usage_id": cursor.lastrowid}
        return None

    def update(self, usage_id, user_id=None, usage_date=None, floor_plan=None, json_file=None):
        updates = []
        params = []

        if user_id is not None:
            updates.append("user_id = %s")
            params.append(user_id)
        if usage_date is not None:
            updates.append("usage_date = %s")
            params.append(usage_date)
        if floor_plan is not None:
            updates.append("floor_plan = %s")
            params.append(floor_plan)
        if json_file is not None:
            updates.append("json_file = %s")
            params.append(json_file)

        if not updates:
            return False

        params.append(usage_id)
        query = f"UPDATE `usage` SET {', '.join(updates)} WHERE usage_id = %s"
        self.db.execute_query(query, tuple(params))
        return True

    def delete(self, usage_id):
        query = "DELETE FROM `usage` WHERE usage_id = %s"
        return bool(self.db.execute_query(query, (usage_id,)))

    def get_by_id(self, usage_id):
        query = """
        SELECT usage_id, user_id, usage_date, floor_plan, json_file
        FROM `usage`
        WHERE usage_id = %s
        """
        result = self.db.fetch_query(query, (usage_id,))
        return result[0] if result else None

    def get_by_user_id(self, user_id):
        query = """
        SELECT usage_id, user_id, usage_date, floor_plan, json_file
        FROM `usage`
        WHERE user_id = %s
        """
        return self.db.fetch_query(query, (user_id,))