from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime, timedelta
import bcrypt
import jwt as pyjwt
from MODEL.database import Database
from MODEL.User import User

# הגדרת קבועים
SECRET_KEY = "LightPlaningSecretKey2024"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ALGORITHM = "HS256"

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={401: {"description": "לא מורשה"}},
)


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    password_confirm: str

    @validator('password')
    def password_complexity(cls, v):
        if len(v) < 8:
            raise ValueError('הסיסמה חייבת להכיל לפחות 8 תווים')
        return v

    @validator('password_confirm')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('הסיסמאות אינן תואמות')
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int


# הגדרת OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_password_hash(password: str) -> str:
    """יוצר גיבוב מוצפן לסיסמה"""
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    # הדפסת מידע על הסיסמה המוצפנת לצורך דיבאג
    hashed_str = hashed_password.decode('utf-8')
    print(f"סיסמה מוצפנת שנוצרה: {hashed_str}")
    print(f"אורך הסיסמה המוצפנת: {len(hashed_str)}")
    print(f"פורמט תקין? {hashed_str.startswith('$2')}")
    return hashed_str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """מאמת סיסמה מול הגיבוב השמור - עם טיפול בשגיאות"""
    try:
        # מידע דיבאג
        print(f"סיסמה רגילה: {plain_password}")
        print(f"סיסמה מוצפנת לבדיקה: {hashed_password}")
        print(f"אורך סיסמה מוצפנת: {len(hashed_password)}")

        # בדיקה אם הסיסמה בפורמט תקין של bcrypt
        if hashed_password.startswith('$2'):
            # נסה להשתמש בbcrypt לאימות
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        else:
            # אם הסיסמה לא מוצפנת, בצע השוואה פשוטה (לתקופת מעבר זמנית בלבד!)
            print("אזהרה: סיסמה לא מוצפנת במסד הנתונים!")
            return plain_password == hashed_password
    except Exception as e:
        print(f"שגיאה באימות סיסמה: {str(e)}")
        # לצורך דיבאג - ניתן לנסות השוואה פשוטה גם במקרה של שגיאה
        return plain_password == hashed_password


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """יוצר טוקן גישה JWT"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = pyjwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme), db: Database = Depends(lambda: Database())):
    """מקבל את המשתמש הנוכחי מהטוקן"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="פרטי אימות לא תקינים",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except pyjwt.PyJWTError:
        raise credentials_exception

# נקודות קצה
@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: Database = Depends(lambda: Database())):
    """הרשמת משתמש חדש עם סיסמה מוצפנת"""
    user_dal = User(db)

    # בדיקה אם המשתמש כבר קיים
    existing_user = user_dal.get_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="כתובת האימייל כבר קיימת במערכת"
        )

    # יצירת משתמש חדש עם סיסמה מוצפנת
    try:
        # הצפנת הסיסמה
        hashed_password = get_password_hash(user_data.password)

        # בדיקה שההצפנה פעלה כראוי
        if not hashed_password.startswith('$2'):
            print("שגיאה: הסיסמה לא הוצפנה כראוי!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="שגיאה בהצפנת הסיסמה"
            )

        # בדיקה שניתן לאמת את הסיסמה (המוצפנת)
        verify_test = verify_password(user_data.password, hashed_password)
        print(f"בדיקת אימות סיסמה לאחר הצפנה: {verify_test}")

        if not verify_test:
            print("שגיאה: לא ניתן לאמת את הסיסמה לאחר הצפנה!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="שגיאה באימות הסיסמה לאחר הצפנה"
            )

        # שמירת המשתמש עם הסיסמה המוצפנת
        print(f"יוצר משתמש עם אימייל {user_data.email} וסיסמה מוצפנת")
        new_user_id = user_dal.create(user_data.email, hashed_password)

        if not new_user_id:
            print("שגיאה: לא הוחזר מזהה משתמש!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="אירעה שגיאה ביצירת המשתמש"
            )

        print(f"משתמש נוצר בהצלחה עם מזהה {new_user_id[0]}")
    except Exception as e:
        print(f"שגיאה כללית ביצירת משתמש: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"אירעה שגיאה ביצירת המשתמש: {str(e)}"
        )

    # יצירת טוקן גישה למשתמש החדש
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user_id[0]}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer", "user_id": new_user_id[0]}


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Database = Depends(lambda: Database())):
    """התחברות משתמש - רק שם וסיסמה"""
    user_dal = User(db)
    user = user_dal.get_by_email(user_data.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="שם משתמש או סיסמה שגויים"
        )

    # אימות סיסמה עם טיפול בשגיאות
    stored_password = user[2]  # לפי המבנה של get_by_email, הסיסמה היא האיבר השלישי

    print(f"בודק התחברות למשתמש {user_data.username}")

    print(f"סוג הסיסמה השמורה: {type(stored_password)}")

    if not verify_password(user_data.password, stored_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="שם משתמש או סיסמה שגויים"
        )

    # יצירת טוקן גישה
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user[0]},  # user_id הוא האיבר הראשון
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer", "user_id": user[0]}


@router.get("/me")
async def read_users_me(current_user=Depends(get_current_user)):
    """מחזיר את פרטי המשתמש המחובר"""
    return {"user_id": current_user[0], "email": current_user[1]}

