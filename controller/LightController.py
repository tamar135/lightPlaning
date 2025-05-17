# LightController.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from MODEL.database import Database
from MODEL.Light import Light

router = APIRouter(
    prefix="/lights",
    tags=["lights"],
)


# סכמות המידע
class LightCreate(BaseModel):
    usage_id: int
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    power: Optional[float] = None


class LightUpdate(BaseModel):
    usage_id: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    power: Optional[float] = None


class LightResponse(BaseModel):
    light_id: int
    usage_id: int
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    power: Optional[float] = None


# נקודות קצה
@router.get("/", response_model=List[LightResponse])
def get_all_lights(db: Database = Depends(lambda: Database())):
    """
    קבלת כל המנורות
    """
    light_dal = Light(db)
    lights = light_dal.get_all() if hasattr(light_dal, 'get_all') else []

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


@router.get("/{light_id}", response_model=LightResponse)
def get_light(light_id: int, db: Database = Depends(lambda: Database())):
    """
    קבלת מנורה לפי ID
    """
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


@router.get("/usage/{usage_id}", response_model=List[LightResponse])
def get_lights_by_usage(usage_id: int, db: Database = Depends(lambda: Database())):
    """
    קבלת מנורות לפי מזהה שימוש
    """
    light_dal = Light(db)
    lights = light_dal.get_by_usage_id(usage_id)

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


@router.post("/", response_model=LightResponse, status_code=201)
def create_light(light: LightCreate, db: Database = Depends(lambda: Database())):
    """
    יצירת מנורה חדשה
    """
    light_dal = Light(db)

    new_light_id = light_dal.create(
        usage_id=light.usage_id,
        x=light.x,
        y=light.y,
        z=light.z,
        power=light.power
    )

    if not new_light_id:
        raise HTTPException(status_code=500, detail="שגיאה ביצירת מנורה")

    return {
        "light_id": new_light_id[0],
        "usage_id": light.usage_id,
        "x": light.x,
        "y": light.y,
        "z": light.z,
        "power": light.power
    }


@router.put("/{light_id}", response_model=LightResponse)
def update_light(light_id: int, light: LightUpdate, db: Database = Depends(lambda: Database())):
    """
    עדכון מנורה
    """
    light_dal = Light(db)

    existing_light = light_dal.get_by_id(light_id)
    if not existing_light:
        raise HTTPException(status_code=404, detail="מנורה לא נמצאה")

    success = light_dal.update(
        light_id=light_id,
        usage_id=light.usage_id,
        x=light.x,
        y=light.y,
        z=light.z,
        power=light.power
    )

    if not success:
        raise HTTPException(status_code=500, detail="שגיאה בעדכון מנורה")

    updated_light = light_dal.get_by_id(light_id)

    return {
        "light_id": updated_light[0],
        "usage_id": updated_light[1],
        "x": updated_light[2],
        "y": updated_light[3],
        "z": updated_light[4],
        "power": updated_light[5]
    }


@router.delete("/{light_id}", status_code=204)
def delete_light(light_id: int, db: Database = Depends(lambda: Database())):
    """
    מחיקת מנורה
    """
    light_dal = Light(db)

    existing_light = light_dal.get_by_id(light_id)
    if not existing_light:
        raise HTTPException(status_code=404, detail="מנורה לא נמצאה")

    success = light_dal.delete(light_id)
    if not success:
        raise HTTPException(status_code=500, detail="שגיאה במחיקת מנורה")

    return None


@router.delete("/usage/{usage_id}", status_code=204)
def delete_lights_by_usage(usage_id: int, db: Database = Depends(lambda: Database())):
    """
    מחיקת כל המנורות של שימוש מסוים
    """
    light_dal = Light(db)

    # בדיקה אם יש מנורות לשימוש זה
    lights = light_dal.get_by_usage_id(usage_id)
    if not lights:
        return None

    # מחיקת כל המנורות
    for light in lights:
        light_dal.delete(light[0])

    return None