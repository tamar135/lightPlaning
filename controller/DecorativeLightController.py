from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import shutil
import tempfile
import os

router = APIRouter(
    tags=["image-upload"]
)


@router.post("/upload-image/")
async def upload_image(
        image: UploadFile = File(...),
        room_type: str = Form(...)
):
    """
    העלאת תמונת חדר וסוג החדר לבחירה (קומבובוקס).

    - **image**: קובץ תמונה מהמחשב
    - **room_type**: סוג החדר (למשל: kitchen, bedroom, office)
    """
    # בדוק סיומת תקינה
    allowed_extensions = [".jpg", ".jpeg", ".png"]
    ext = os.path.splitext(image.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid image type. Only JPG, JPEG, PNG allowed.")

    try:
        # שמירה לקובץ זמני
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            shutil.copyfileobj(image.file, tmp)
            temp_path = tmp.name

        # כאן את יכולה לעבד את התמונה או להעביר אותה למודל שלך
        return JSONResponse(content={
            "message": "Image uploaded successfully",
            "room_type": room_type,
            "saved_path": temp_path
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
