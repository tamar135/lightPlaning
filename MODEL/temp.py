from database import Database
from User import User
from Usage import Usage
from Light import Light
from datetime import datetime

# חיבור למסד
db = Database(host="localhost", user="root", password="MySql1234!", database="lightProjectDB")

# יצירת משתמש
user_manager = User(db)
user = user_manager.create("test@example.com", "hashed_password")  # החליפי בסיסמה מוצפנת
print(f"Created user: {user}")

# יצירת Usage
usage_manager = Usage(db)
usage = usage_manager.create(
    user_id=user[0],
    date=datetime.now(),
    ifc_file_path="/path/to/ifc/file.ifc",
    json_file_path="/path/to/json/file.json"
)
print(f"Created usage: {usage}")

# יצירת שתי מנורות
light_manager = Light(db)
light1 = light_manager.create(usage_id=usage[0], x=1.0, y=2.0, z=3.0, power=100)
print(f"Created light1: {light1}")
light2 = light_manager.create(usage_id=usage[0], x=4.0, y=5.0, z=6.0, power=150)
print(f"Created light2: {light2}")