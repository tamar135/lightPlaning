# UserController.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pydantic import BaseModel
from MODEL.database import Database
from MODEL.User import User

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


# סכמות המידע
class UserCreate(BaseModel):
    email: str
    password: str


class UserUpdate(BaseModel):
    email: str = None
    password: str = None


class UserResponse(BaseModel):
    user_id: int
    email: str


# נקודות קצה
@router.get("/", response_model=List[UserResponse])
def get_all_users(db: Database = Depends(lambda: Database())):
    """
    קבלת כל המשתמשים
    """
    user_dal = User(db)
    users = user_dal.get_all()
    return [{"user_id": user[0], "email": user[1]} for user in users]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Database = Depends(lambda: Database())):
    """
    קבלת משתמש לפי ID
    """
    user_dal = User(db)
    user = user_dal.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")
    return {"user_id": user[0], "email": user[1]}


@router.get("/email/{email}", response_model=UserResponse)
def get_user_by_email(email: str, db: Database = Depends(lambda: Database())):
    """
    קבלת משתמש לפי אימייל
    """
    user_dal = User(db)
    user = user_dal.get_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")
    return {"user_id": user[0], "email": user[1]}


@router.post("/", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate, db: Database = Depends(lambda: Database())):
    """
    יצירת משתמש חדש
    """
    user_dal = User(db)

    # בדיקה אם המשתמש כבר קיים
    existing_user = user_dal.get_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="כתובת האימייל כבר קיימת במערכת")

    # יצירת משתמש חדש
    new_user_id = user_dal.create(user.email, user.password)
    if not new_user_id:
        raise HTTPException(status_code=500, detail="שגיאה ביצירת משתמש")

    return {"user_id": new_user_id[0], "email": user.email}


@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user: UserUpdate, db: Database = Depends(lambda: Database())):
    """
    עדכון משתמש
    """
    user_dal = User(db)

    # בדיקה אם המשתמש קיים
    existing_user = user_dal.get_by_id(user_id)
    if not existing_user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")

    # עדכון המשתמש
    success = user_dal.update(user_id, user.email, user.password)
    if not success:
        raise HTTPException(status_code=500, detail="שגיאה בעדכון משתמש")

    # קבלת המשתמש המעודכן
    updated_user = user_dal.get_by_id(user_id)
    return {"user_id": updated_user[0], "email": updated_user[1]}


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Database = Depends(lambda: Database())):
    """
    מחיקת משתמש
    """
    user_dal = User(db)

    # בדיקה אם המשתמש קיים
    existing_user = user_dal.get_by_id(user_id)
    if not existing_user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")

    # מחיקת המשתמש
    success = user_dal.delete(user_id)
    if not success:
        raise HTTPException(status_code=500, detail="שגיאה במחיקת משתמש")

    return None