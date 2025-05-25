# UsageController.py
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from MODEL.database import Database
from MODEL.Usage import Usage

router = APIRouter(
    prefix="/usages",
    tags=["usages"],
)


class UsageResponse(BaseModel):
    usage_id: int
    user_id: int
    usage_date: Optional[datetime] = None
    floor_plan: Optional[bytes] = None
    json_file: Optional[str] = None


@router.get("/", response_model=List[UsageResponse])
def get_all_usages(db: Database = Depends(lambda: Database())):
    """
    קבלת כל השימושים
    """
    usage_dal = Usage(db)
    usages = usage_dal.get_all() if hasattr(usage_dal, 'get_all') else []

    result = []
    for usage in usages:
        result.append({
            "usage_id": usage[0],
            "user_id": usage[1],
            "usage_date": usage[2],
            "floor_plan": None,  # לא מחזירים את הקובץ המלא
            "json_file": None  # לא מחזירים את ה-JSON המלא
        })

    return result


@router.get("/{usage_id}", response_model=UsageResponse)
def get_usage(usage_id: int, db: Database = Depends(lambda: Database())):
    """
    קבלת שימוש לפי ID
    """
    usage_dal = Usage(db)
    usage = usage_dal.get_by_id(usage_id)

    if not usage:
        raise HTTPException(status_code=404, detail="שימוש לא נמצא")

    return {
        "usage_id": usage[0],
        "user_id": usage[1],
        "usage_date": usage[2],
        "floor_plan": None,  # לא מחזירים את הקובץ המלא
        "json_file": None  # לא מחזירים את ה-JSON המלא
    }


@router.get("/user/{user_id}", response_model=List[UsageResponse])
def get_usages_by_user(user_id: int, db: Database = Depends(lambda: Database())):
    """
    קבלת שימושים לפי מזהה משתמש
    """
    usage_dal = Usage(db)
    usages = usage_dal.get_by_user_id(user_id)

    result = []
    for usage in usages:
        result.append({
            "usage_id": usage[0],
            "user_id": usage[1],
            "usage_date": usage[2],
            "floor_plan": None,  # לא מחזירים את הקובץ המלא
            "json_file": None  # לא מחזירים את ה-JSON המלא
        })

    return result


@router.get("/{usage_id}/json")
def get_usage_json(usage_id: int, db: Database = Depends(lambda: Database())):
    """
    קבלת תוכן ה-JSON של שימוש
    """
    usage_dal = Usage(db)
    usage = usage_dal.get_by_id(usage_id)

    if not usage or len(usage) <= 4 or not usage[4]:
        raise HTTPException(status_code=404, detail="JSON לא נמצא")

    return usage[4]  # מחזירים את ה-JSON


@router.get("/{usage_id}/floor-plan")
def get_usage_floor_plan(usage_id: int, db: Database = Depends(lambda: Database())):
    """
    קבלת קובץ תוכנית הקומה
    """
    from fastapi.responses import Response

    usage_dal = Usage(db)
    usage = usage_dal.get_by_id(usage_id)

    if not usage or len(usage) <= 3 or not usage[3]:
        raise HTTPException(status_code=404, detail="תוכנית קומה לא נמצאה")

    return Response(content=usage[3], media_type="application/octet-stream")


@router.post("/", response_model=UsageResponse)
async def create_usage(
        user_id: int = Form(...),
        floor_plan: UploadFile = File(None),
        json_file: str = Form(None)
):
    """
    יצירת שימוש חדש
    """
    db = Database()
    usage_dal = Usage(db)

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
        raise HTTPException(status_code=500, detail="שגיאה ביצירת שימוש")

    return {
        "usage_id": new_usage[0],
        "user_id": user_id,
        "usage_date": datetime.now(),
        "floor_plan": None,  # לא מחזירים את הקובץ המלא
        "json_file": json_file
    }


@router.put("/{usage_id}", response_model=UsageResponse)
async def update_usage(
        usage_id: int,
        user_id: int = Form(None),
        floor_plan: UploadFile = File(None),
        json_file: str = Form(None)
):
    """
    עדכון שימוש
    """
    db = Database()
    usage_dal = Usage(db)

    existing_usage = usage_dal.get_by_id(usage_id)
    if not existing_usage:
        raise HTTPException(status_code=404, detail="שימוש לא נמצא")

    floor_plan_data = None
    if floor_plan:
        floor_plan_data = await floor_plan.read()

    success = usage_dal.update(
        usage_id=usage_id,
        user_id=user_id,
        floor_plan=floor_plan_data,
        json_file=json_file
    )

    if not success:
        raise HTTPException(status_code=500, detail="שגיאה בעדכון שימוש")

    updated_usage = usage_dal.get_by_id(usage_id)

    return {
        "usage_id": updated_usage[0],
        "user_id": updated_usage[1],
        "usage_date": updated_usage[2],
        "floor_plan": None,
        "json_file": None
    }


@router.delete("/{usage_id}", status_code=204)
def delete_usage(usage_id: int, db: Database = Depends(lambda: Database())):
    """
    מחיקת שימוש
    """
    usage_dal = Usage(db)

    existing_usage = usage_dal.get_by_id(usage_id)
    if not existing_usage:
        raise HTTPException(status_code=404, detail="שימוש לא נמצא")

    success = usage_dal.delete(usage_id)
    if not success:
        raise HTTPException(status_code=500, detail="שגיאה במחיקת שימוש")

    return None