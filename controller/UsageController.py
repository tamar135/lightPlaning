# UsageController.py

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
from MODEL.database import Database
from MODEL.Usage import Usage

router = APIRouter(
    prefix="/usages",
    tags=["usages"],
    responses={404: {"description": "לא נמצא"}}
)


# מודלים של Pydantic
class UsageBase(BaseModel):
    user_id: int


class UsageCreate(UsageBase):
    usage_date: Optional[datetime] = None
    floor_plan: Optional[bytes] = None
    json_file: Optional[str] = None


class UsageUpdate(BaseModel):
    user_id: Optional[int] = None
    usage_date: Optional[datetime] = None
    floor_plan: Optional[bytes] = None
    json_file: Optional[str] = None


class UsageResponse(BaseModel):
    usage_id: int
    user_id: int
    usage_date: datetime
    floor_plan_exists: bool
    json_file_exists: bool

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


# קבלת כל השימושים
@router.get("/", response_model=List[UsageResponse])
def get_all_usages(db: Database = Depends(get_db)):
    usage_dal = Usage(db)
    usages = usage_dal.get_all()
    if not usages:
        return []

    result = []
    for usage in usages:
        result.append({
            "usage_id": usage[0],
            "user_id": usage[1],
            "usage_date": usage[2],
            "floor_plan_exists": usage[3] is not None,
            "json_file_exists": usage[4] is not None
        })
    return result


# קבלת שימוש לפי ID
@router.get("/{usage_id}", response_model=UsageResponse)
def get_usage(usage_id: int, db: Database = Depends(get_db)):
    usage_dal = Usage(db)
    usage = usage_dal.get_by_id(usage_id)
    if not usage:
        raise HTTPException(status_code=404, detail="שימוש לא נמצא")

    return {
        "usage_id": usage[0],
        "user_id": usage[1],
        "usage_date": usage[2],
        "floor_plan_exists": usage[3] is not None,
        "json_file_exists": usage[4] is not None
    }


# קבלת שימושים לפי מזהה משתמש
@router.get("/user/{user_id}", response_model=List[UsageResponse])
def get_usages_by_user(user_id: int, db: Database = Depends(get_db)):
    usage_dal = Usage(db)
    usages = usage_dal.get_by_user_id(user_id)
    if not usages:
        return []

    result = []
    for usage in usages:
        result.append({
            "usage_id": usage[0],
            "user_id": usage[1],
            "usage_date": usage[2],
            "floor_plan_exists": usage[3] is not None,
            "json_file_exists": usage[4] is not None
        })
    return result


# קבלת תוכן ה-JSON של שימוש
@router.get("/{usage_id}/json")
def get_usage_json(usage_id: int, db: Database = Depends(get_db)):
    usage_dal = Usage(db)
    usage = usage_dal.get_by_id(usage_id)
    if not usage:
        raise HTTPException(status_code=404, detail="שימוש לא נמצא")

    if not usage[4]:  # json_file
        raise HTTPException(status_code=404, detail="אין קובץ JSON לשימוש זה")

    try:
        json_data = json.loads(usage[4])
        return json_data
    except json.JSONDecodeError:
        return {"raw_json": usage[4]}


# קבלת קובץ תוכנית הקומה
@router.get("/{usage_id}/floor-plan")
def get_usage_floor_plan(usage_id: int, db: Database = Depends(get_db)):
    from fastapi.responses import Response

    usage_dal = Usage(db)
    usage = usage_dal.get_by_id(usage_id)
    if not usage:
        raise HTTPException(status_code=404, detail="שימוש לא נמצא")

    if not usage[3]:  # floor_plan
        raise HTTPException(status_code=404, detail="אין קובץ תוכנית קומה לשימוש זה")

    return Response(content=usage[3], media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename=floor_plan_{usage_id}.ifc"})


# יצירת שימוש חדש
@router.post("/", response_model=UsageResponse)
async def create_usage(
        user_id: int = Form(...),
        floor_plan: UploadFile = File(None),
        json_file: str = Form(None)
):
    db = Database()
    usage_dal = Usage(db)

    try:
        floor_plan_data = None
        if floor_plan:
            floor_plan_data = await floor_plan.read()

        new_usage = usage_dal.create(
            user_id=user_id,
            usage_date=datetime.now(),
            floor_plan=floor_plan_data,
            json_file=json_file
        )

        if not new_usage:
            raise HTTPException(status_code=500, detail="שגיאה ביצירת השימוש")

        usage_id = new_usage[0]

        # קבלת השימוש החדש
        created_usage = usage_dal.get_by_id(usage_id)
        return {
            "usage_id": created_usage[0],
            "user_id": created_usage[1],
            "usage_date": created_usage[2],
            "floor_plan_exists": created_usage[3] is not None,
            "json_file_exists": created_usage[4] is not None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה ביצירת השימוש: {str(e)}")


# עדכון שימוש
@router.put("/{usage_id}", response_model=UsageResponse)
async def update_usage(
        usage_id: int,
        user_id: int = Form(None),
        floor_plan: UploadFile = File(None),
        json_file: str = Form(None)
):
    db = Database()
    usage_dal = Usage(db)

    # בדיקה אם השימוש קיים
    existing_usage = usage_dal.get_by_id(usage_id)
    if not existing_usage:
        raise HTTPException(status_code=404, detail="שימוש לא נמצא")

    try:
        floor_plan_data = None
        if floor_plan:
            floor_plan_data = await floor_plan.read()

        # עדכון השימוש
        success = usage_dal.update(
            usage_id=usage_id,
            user_id=user_id,
            usage_date=datetime.now() if floor_plan_data or json_file else None,
            floor_plan=floor_plan_data,
            json_file=json_file
        )

        if not success:
            raise HTTPException(status_code=500, detail="שגיאה בעדכון השימוש")

        # קבלת השימוש המעודכן
        updated_usage = usage_dal.get_by_id(usage_id)
        return {
            "usage_id": updated_usage[0],
            "user_id": updated_usage[1],
            "usage_date": updated_usage[2],
            "floor_plan_exists": updated_usage[3] is not None,
            "json_file_exists": updated_usage[4] is not None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה בעדכון השימוש: {str(e)}")


# מחיקת שימוש
@router.delete("/{usage_id}", status_code=204)
def delete_usage(usage_id: int, db: Database = Depends(get_db)):
    usage_dal = Usage(db)

    # בדיקה אם השימוש קיים
    existing_usage = usage_dal.get_by_id(usage_id)
    if not existing_usage:
        raise HTTPException(status_code=404, detail="שימוש לא נמצא")

    # מחיקת השימוש
    success = usage_dal.delete(usage_id)
    if not success:
        raise HTTPException(status_code=500, detail="שגיאה במחיקת השימוש")

    return None