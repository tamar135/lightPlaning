class User:
    def __init__(self, db):
        self.db = db

    def create(self, email, password):
        query = "INSERT INTO user (email, password) VALUES (%s, %s)"
        cursor = self.db.execute_query(query, (email, password))
        if cursor:
            return (cursor.lastrowid,)
        return None

    def update(self, user_id, email=None, password=None):
        updates = []
        params = []

        if email is not None:
            updates.append("email = %s")
            params.append(email)
        if password is not None:
            updates.append("password = %s")
            params.append(password)

        if not updates:
            return False

        params.append(user_id)
        query = f"UPDATE user SET {', '.join(updates)} WHERE user_id = %s"
        self.db.execute_query(query, tuple(params))
        return True

    def delete(self, user_id):
        query = "DELETE FROM user WHERE user_id = %s"
        return bool(self.db.execute_query(query, (user_id,)))

    def get_by_id(self, user_id):
        query = """
        SELECT user_id, email, password
        FROM user
        WHERE user_id = %s
        """
        result = self.db.fetch_query(query, (user_id,))
        return result[0] if result else None

    def get_by_email(self, email):
        query = """
        SELECT user_id, email, password
        FROM user
        WHERE email = %s
        """
        result = self.db.fetch_query(query, (email,))
        return result[0] if result else None

    def get_all(self):
        query = """
        SELECT user_id, email, password
        FROM user
        """
        return self.db.fetch_query(query)