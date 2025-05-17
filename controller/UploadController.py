from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fileProcessor import fileProcessor

router = APIRouter(
    tags=["uploads"],
)

processor = fileProcessor()

@router.post("/upload-ifc/")
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