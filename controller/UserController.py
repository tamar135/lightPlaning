# controller/UserController.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from MODEL.database import Database
from MODEL.User import User

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "לא נמצא"}}
)


# מודלים של Pydantic
class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None


class UserResponse(UserBase):
    user_id: int

    class Config:
        orm_mode = True


# יצירת תלות של DB
def get_db():
    db = Database()
    try:
        yield db
    finally:
        if db.connection and db.connection.is_connected():
            pass


# קבלת כל המשתמשים
@router.get("/", response_model=List[UserResponse])
def get_all_users(db: Database = Depends(get_db)):
    user_dal = User(db)
    users = user_dal.get_all()
    if not users:
        return []
    return [{"user_id": user[0], "email": user[1]} for user in users]


# קבלת משתמש לפי ID
@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Database = Depends(get_db)):
    user_dal = User(db)
    user = user_dal.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")
    return {"user_id": user[0], "email": user[1]}


# קבלת משתמש לפי אימייל
@router.get("/email/{email}", response_model=UserResponse)
def get_user_by_email(email: str, db: Database = Depends(get_db)):
    user_dal = User(db)
    user = user_dal.get_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")
    return {"user_id": user[0], "email": user[1]}


# יצירת משתמש חדש
@router.post("/", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate, db: Database = Depends(get_db)):
    user_dal = User(db)
    # בדיקה אם המשתמש כבר קיים
    existing_user = user_dal.get_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="המייל כבר רשום במערכת")

    new_user = user_dal.create(user.email, user.password)
    if not new_user:
        raise HTTPException(status_code=500, detail="שגיאה ביצירת המשתמש")

    return {"user_id": new_user[0], "email": user.email}


# עדכון משתמש
@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user: UserUpdate, db: Database = Depends(get_db)):
    user_dal = User(db)
    # בדיקה אם המשתמש קיים
    existing_user = user_dal.get_by_id(user_id)
    if not existing_user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")

    # עדכון המשתמש
    success = user_dal.update(user_id, user.email, user.password)
    if not success:
        raise HTTPException(status_code=500, detail="שגיאה בעדכון המשתמש")

    # קבלת המשתמש המעודכן
    updated_user = user_dal.get_by_id(user_id)
    return {"user_id": updated_user[0], "email": updated_user[1]}


# מחיקת משתמש
@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Database = Depends(get_db)):
    user_dal = User(db)
    # בדיקה אם המשתמש קיים
    existing_user = user_dal.get_by_id(user_id)
    if not existing_user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")

    # מחיקת המשתמש
    success = user_dal.delete(user_id)
    if not success:
        raise HTTPException(status_code=500, detail="שגיאה במחיקת המשתמש")

    return None