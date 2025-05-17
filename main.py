# נתיב מוצע להוספת הקונטרולרים בקובץ main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ייבוא כל הקונטרולרים
from controller import AuthController
from controller import UserController
from controller import UsageController
from controller import LightController
from controller import UploadController
from controller import IFCVisualController

app = FastAPI(
    title="Light Project API",
    description="API for managing lighting in building projects",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# הגדרת CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# הוספת הקונטרולרים לאפליקציה
app.include_router(AuthController.router)
app.include_router(UserController.router)
app.include_router(UsageController.router)
app.include_router(LightController.router)
app.include_router(UploadController.router)
app.include_router(IFCVisualController.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Light Project API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)