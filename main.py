from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from controller.AuthController import router as auth_router
from controller.UserController import router as user_router
from controller.UploadController import router as upload_router
from controller.UsageController import router as usage_router
from controller.LightController import router as light_router
from controller.IFCVisualController import router as visual_router
from controller.DecorativeLightController import router as decorative_router

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Smart Lighting Design API",
    description="מערכת תכנון תאורה חכמה עם זיהוי סוג חדר ותאורת נוי",
    version="2.0.0"
)

# הגדרת CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# רישום כל ה-Routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(upload_router)
app.include_router(usage_router)
app.include_router(light_router)
app.include_router(visual_router)
app.include_router(decorative_router)

@app.get("/")
def read_root():
    return {
        "message": "Smart Lighting Design API v2.0",
        "features": [
            "Regular lighting design",
            "Room type classification",
            "Decorative lighting suggestions"
        ]
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Smart Lighting Design API v2.0...")
    uvicorn.run(app, host="0.0.0.0", port=8000)