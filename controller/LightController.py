# LightController.py

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from MODEL.database import Database
from MODEL.Light import Light

router = APIRouter(
    prefix="/lights",
    tags=["lights"],
    responses={404: {"description": "לא נמצא"}}
)


# מודלים של Pydantic
class LightBase(BaseModel):
    usage_id: int
    x: float
    y: float
    z: float
    power: float


class LightCreate(LightBase):
    pass


class LightUpdate(BaseModel):
    usage_id: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    power: Optional[float] = None


class LightResponse(LightBase):
    light_id: int

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


# קבלת כל המנורות
@router.get("/", response_model=List[LightResponse])
def get_all_lights(db: Database = Depends(get_db)):
    light_dal = Light(db)
    lights = light_dal.get_all()
    if not lights:
        return []

    result = []
    for light in lights:
        result.append({
            "light_id": light[0],
            "usage_id": light[1],
            "x": light[2],
            "y": light[3],
            "z": light[4],
            "power": light[5]
        })
    return result


# קבלת מנורה לפי ID
@router.get("/{light_id}", response_model=LightResponse)
def get_light(light_id: int, db: Database = Depends(get_db)):
    light_dal = Light(db)
    light = light_dal.get_by_id(light_id)
    if not light:
        raise HTTPException(status_code=404, detail="מנורה לא נמצאה")

    return {
        "light_id": light[0],
        "usage_id": light[1],
        "x": light[2],
        "y": light[3],
        "z": light[4],
        "power": light[5]
    }


# קבלת מנורות לפי מזהה שימוש
@router.get("/usage/{usage_id}", response_model=List[LightResponse])
def get_lights_by_usage(usage_id: int, db: Database = Depends(get_db)):
    light_dal = Light(db)
    lights = light_dal.get_by_usage_id(usage_id)
    if not lights:
        return []

    result = []
    for light in lights:
        result.append({
            "light_id": light[0],
            "usage_id": light[1],
            "x": light[2],
            "y": light[3],
            "z": light[4],
            "power": light[5]
        })
    return result


# יצירת מנורה חדשה
@router.post("/", response_model=LightResponse, status_code=201)
def create_light(light: LightCreate, db: Database = Depends(get_db)):
    light_dal = Light(db)

    try:
        new_light = light_dal.create(
            usage_id=light.usage_id,
            x=light.x,
            y=light.y,
            z=light.z,
            power=light.power
        )

        if not new_light:
            raise HTTPException(status_code=500, detail="שגיאה ביצירת המנורה")

        light_id = new_light[0]

        return {
            "light_id": light_id,
            "usage_id": light.usage_id,
            "x": light.x,
            "y": light.y,
            "z": light.z,
            "power": light.power
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה ביצירת המנורה: {str(e)}")


# עדכון מנורה
@router.put("/{light_id}", response_model=LightResponse)
def update_light(light_id: int, light: LightUpdate, db: Database = Depends(get_db)):
    light_dal = Light(db)

    # בדיקה אם המנורה קיימת
    existing_light = light_dal.get_by_id(light_id)
    if not existing_light:
        raise HTTPException(status_code=404, detail="מנורה לא נמצאה")

    try:
        # עדכון המנורה
        success = light_dal.update(
            light_id=light_id,
            usage_id=light.usage_id,
            x=light.x,
            y=light.y,
            z=light.z,
            power=light.power
        )

        if not success:
            raise HTTPException(status_code=500, detail="שגיאה בעדכון המנורה")

        # קבלת המנורה המעודכנת
        updated_light = light_dal.get_by_id(light_id)
        return {
            "light_id": updated_light[0],
            "usage_id": updated_light[1],
            "x": updated_light[2],
            "y": updated_light[3],
            "z": updated_light[4],
            "power": updated_light[5]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה בעדכון המנורה: {str(e)}")


# מחיקת מנורה
@router.delete("/{light_id}", status_code=204)
def delete_light(light_id: int, db: Database = Depends(get_db)):
    light_dal = Light(db)

    # בדיקה אם המנורה קיימת
    existing_light = light_dal.get_by_id(light_id)
    if not existing_light:
        raise HTTPException(status_code=404, detail="מנורה לא נמצאה")

    # מחיקת המנורה
    success = light_dal.delete(light_id)
    if not success:
        raise HTTPException(status_code=500, detail="שגיאה במחיקת המנורה")

    return None


# מחיקת כל המנורות של שימוש מסוים
@router.delete("/usage/{usage_id}", status_code=204)
def delete_lights_by_usage(usage_id: int, db: Database = Depends(get_db)):
    light_dal = Light(db)

    # קבלת כל המנורות של השימוש
    lights = light_dal.get_by_usage_id(usage_id)
    if not lights:
        return None

    # מחיקת כל המנורות
    for light in lights:
        light_dal.delete(light[0])

    return None