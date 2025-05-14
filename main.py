from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

from fileProcessor import fileProcessor
import controller.UsageController as UsageController
import controller.UserController as UserController
import controller.LightController as LightController
from MODEL.database import Database
from fastapi.responses import HTMLResponse, JSONResponse
from room_visualization import create_visualization
import plotly.graph_objects as go

app = FastAPI(
    title="Light Project API",
    description="API for managing lighting in building projects",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

processor = fileProcessor()


# תלות להזרקת חיבור מסד הנתונים
def get_db():
    db = Database()
    try:
        yield db
    finally:
        if hasattr(db, 'connection') and db.connection:
            db.connection.close()



@app.get("/")
def read_root():
    return {"message": "Welcome to Light Project API"}



@app.post("/upload-ifc/")
async def upload_ifc(
        file: UploadFile = File(...),
        user_id: str = Form(...),
        room_type: str = Form("bedroom")
):
    """
    העלאת קובץ IFC ויצירת פרויקט תאורה חדש.

    - **file**: קובץ IFC
    - **user_id**: מזהה המשתמש
    - **room_type**: סוג החדר (ברירת מחדל: bedroom)
    """
    is_valid, message = await processor.validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    try:
        result = await processor.process_and_save_file(file, user_id, room_type)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/", response_model=List[UserController.UserResponse])
def get_all_users(db: Database = Depends(get_db)):
    """
    קבלת כל המשתמשים
    """
    return UserController.get_all_users(db)


@app.get("/users/{user_id}", response_model=UserController.UserResponse)
def get_user(user_id: int, db: Database = Depends(get_db)):
    """
    קבלת משתמש לפי ID
    """
    return UserController.get_user(user_id, db)


@app.get("/users/email/{email}", response_model=UserController.UserResponse)
def get_user_by_email(email: str, db: Database = Depends(get_db)):
    """
    קבלת משתמש לפי אימייל
    """
    return UserController.get_user_by_email(email, db)


@app.post("/users/", response_model=UserController.UserResponse, status_code=201)
def create_user(user: UserController.UserCreate, db: Database = Depends(get_db)):
    """
    יצירת משתמש חדש
    """
    return UserController.create_user(user, db)


@app.put("/users/{user_id}", response_model=UserController.UserResponse)
def update_user(user_id: int, user: UserController.UserUpdate, db: Database = Depends(get_db)):
    """
    עדכון משתמש
    """
    return UserController.update_user(user_id, user, db)


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Database = Depends(get_db)):
    """
    מחיקת משתמש
    """
    return UserController.delete_user(user_id, db)


# ----- נקודות קצה שימושים -----

@app.get("/usages/", response_model=List[UsageController.UsageResponse])
def get_all_usages(db: Database = Depends(get_db)):
    """
    קבלת כל השימושים
    """
    return UsageController.get_all_usages(db)


@app.get("/usages/{usage_id}", response_model=UsageController.UsageResponse)
def get_usage(usage_id: int, db: Database = Depends(get_db)):
    """
    קבלת שימוש לפי ID
    """
    return UsageController.get_usage(usage_id, db)


@app.get("/usages/user/{user_id}", response_model=List[UsageController.UsageResponse])
def get_usages_by_user(user_id: int, db: Database = Depends(get_db)):
    """
    קבלת שימושים לפי מזהה משתמש
    """
    return UsageController.get_usages_by_user(user_id, db)


@app.get("/usages/{usage_id}/json")
def get_usage_json(usage_id: int, db: Database = Depends(get_db)):
    """
    קבלת תוכן ה-JSON של שימוש
    """
    return UsageController.get_usage_json(usage_id, db)


@app.get("/usages/{usage_id}/floor-plan")
def get_usage_floor_plan(usage_id: int, db: Database = Depends(get_db)):
    """
    קבלת קובץ תוכנית הקומה
    """
    return UsageController.get_usage_floor_plan(usage_id, db)


@app.post("/usages/", response_model=UsageController.UsageResponse)
async def create_usage(
        user_id: int = Form(...),
        floor_plan: UploadFile = File(None),
        json_file: str = Form(None)
):
    """
    יצירת שימוש חדש
    """
    return await UsageController.create_usage(user_id, floor_plan, json_file)


@app.put("/usages/{usage_id}", response_model=UsageController.UsageResponse)
async def update_usage(
        usage_id: int,
        user_id: int = Form(None),
        floor_plan: UploadFile = File(None),
        json_file: str = Form(None)
):
    """
    עדכון שימוש
    """
    return await UsageController.update_usage(usage_id, user_id, floor_plan, json_file)


@app.delete("/usages/{usage_id}", status_code=204)
def delete_usage(usage_id: int, db: Database = Depends(get_db)):
    """
    מחיקת שימוש
    """
    return UsageController.delete_usage(usage_id, db)


# ----- נקודות קצה מנורות -----

@app.get("/lights/", response_model=List[LightController.LightResponse])
def get_all_lights(db: Database = Depends(get_db)):
    """
    קבלת כל המנורות
    """
    return LightController.get_all_lights(db)


@app.get("/lights/{light_id}", response_model=LightController.LightResponse)
def get_light(light_id: int, db: Database = Depends(get_db)):
    """
    קבלת מנורה לפי ID
    """
    return LightController.get_light(light_id, db)


@app.get("/lights/usage/{usage_id}", response_model=List[LightController.LightResponse])
def get_lights_by_usage(usage_id: int, db: Database = Depends(get_db)):
    """
    קבלת מנורות לפי מזהה שימוש
    """
    return LightController.get_lights_by_usage(usage_id, db)


@app.post("/lights/", response_model=LightController.LightResponse, status_code=201)
def create_light(light: LightController.LightCreate, db: Database = Depends(get_db)):
    """
    יצירת מנורה חדשה
    """
    return LightController.create_light(light, db)


@app.put("/lights/{light_id}", response_model=LightController.LightResponse)
def update_light(light_id: int, light: LightController.LightUpdate, db: Database = Depends(get_db)):
    """
    עדכון מנורה
    """
    return LightController.update_light(light_id, light, db)


@app.delete("/lights/{light_id}", status_code=204)
def delete_light(light_id: int, db: Database = Depends(get_db)):
    """
    מחיקת מנורה
    """
    return LightController.delete_light(light_id, db)


@app.delete("/lights/usage/{usage_id}", status_code=204)
def delete_lights_by_usage(usage_id: int, db: Database = Depends(get_db)):
    """
    מחיקת כל המנורות של שימוש מסוים
    """
    return LightController.delete_lights_by_usage(usage_id, db)

@app.get("/api/visualization/{usage_id}")
def get_visualization(usage_id: int, db: Database = Depends(get_db)):
    """
    קבלת סימולציה תלת-מימדית של חדר
    """
    fig = create_visualization(usage_id)
    if fig:
        return JSONResponse(content=fig.to_dict())
    else:
        raise HTTPException(status_code=404, detail="לא נמצאה סימולציה עבור מזהה השימוש")

@app.get("/visualization/{usage_id}")
def serve_visualization(usage_id: int, db: Database = Depends(get_db)):
    """
    הצגת סימולציה תלת-מימדית ישירות בדפדפן
    """
    fig = create_visualization(usage_id)
    if fig:
        html_content = fig.to_html(include_plotlyjs=True, full_html=True)
        return HTMLResponse(content=html_content)
    else:
        raise HTTPException(status_code=404, detail="לא נמצאה סימולציה עבור מזהה השימוש")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)