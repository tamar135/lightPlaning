import mysql.connector
from mysql.connector import Error


class Database:
    def __init__(self, host="localhost", user="root", password="MySql123!", database="lightprojectdb"):
        self.connection = None
        try:
            # נסה להתחבר תחילה ללא ציון מסד נתונים כדי לוודא אם הוא קיים
            self.connection = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                auth_plugin='mysql_native_password'
            )

            # בדוק אם מסד הנתונים קיים, אם לא - צור אותו
            cursor = self.connection.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
            cursor.execute(f"USE {database}")
            self.connection.commit()
            cursor.close()

            print("Connected to MySQL database")
        except Error as e:
            print(f"Error: {e}")

    def __del__(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("MySQL connection closed")

    def execute_query(self, query, params=None):
        if not self.connection or not self.connection.is_connected():
            print("No database connection")
            return None

        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params or ())
            self.connection.commit()
            return cursor
        except Error as e:
            print(f"Error: {e}")
            return None
        finally:
            cursor.close()

    def fetch_query(self, query, params=None):
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params or ())
            result = cursor.fetchall()
            return result
        except Error as e:
            print(f"Error: {e}")
            return []
        finally:
            cursor.close()