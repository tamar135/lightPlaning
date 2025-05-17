# IFCVisualController.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import os
import tempfile
import logging
from MODEL.database import Database
from MODEL.Usage import Usage
from MODEL.Light import Light

# הגדרת לוגר
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/visual",
    tags=["visualization"],
)

@router.get("/ifc/{usage_id}")
def get_ifc_visualization(usage_id: int):
    """
    מייצר ויזואליזציה של קובץ IFC ומחזיר קובץ HTML
    """
    try:
        # התחברות למסד הנתונים
        db = Database()
        usage_dal = Usage(db)
        light_dal = Light(db)

        # שליפת השימוש
        usage_data = usage_dal.get_by_id(usage_id)

        if not usage_data:
            logger.error(f"לא נמצא שימוש עם מזהה {usage_id}")
            raise HTTPException(status_code=404, detail="שימוש לא נמצא")

        # בדיקה אם יש קובץ IFC
        if len(usage_data) <= 3 or not usage_data[3]:
            logger.error(f"אין קובץ IFC בשימוש {usage_id}")
            raise HTTPException(status_code=404, detail="לא נמצא קובץ IFC בשימוש זה")

        # קבלת נתוני הנורות
        lights = light_dal.get_by_usage_id(usage_id)
        if not lights:
            logger.warning(f"לא נמצאו נורות לשימוש {usage_id}")

        # טיפול בנתוני נורות
        light_data = []
        for light in lights:
            if isinstance(light, tuple) and len(light) > 5:
                x = float(light[3]) if light[3] is not None else 0
                y = float(light[4]) if light[4] is not None else 0
                z = float(light[5]) if light[5] is not None else 0
                power = float(light[6]) if light[6] is not None else 0
                light_data.append({
                    "id": light[0],
                    "x": x,
                    "y": y,
                    "z": z,
                    "power": power
                })

        # שמירת הקובץ לקובץ זמני
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as temp_file:
            temp_file.write(usage_data[3])
            ifc_path = temp_file.name

        # יצירת פלט HTML עם מודל תלת-ממדי
        output_file = os.path.join(tempfile.gettempdir(), f"ifc_visual_{usage_id}.html")

        # כאן קריאה לקוד הויזואליזציה
        import subprocess
        result = subprocess.run([
            "python", "IFCVisualizer.py",
            "--usage_id", str(usage_id),
            "--output", output_file
        ], capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"שגיאה בהפעלת הויזואליזציה: {result.stderr}")
            raise HTTPException(status_code=500, detail="שגיאה ביצירת הויזואליזציה")

        # ניקוי קובץ IFC זמני
        try:
            os.remove(ifc_path)
        except Exception as e:
            logger.warning(f"שגיאה בניקוי קובץ זמני: {str(e)}")

        # בדיקה שהקובץ נוצר
        if not os.path.exists(output_file):
            logger.error("קובץ הויזואליזציה לא נוצר")
            raise HTTPException(status_code=500, detail="קובץ הויזואליזציה לא נוצר")

        return FileResponse(
            path=output_file,
            filename=f"visualization_{usage_id}.html",
            media_type="text/html"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"שגיאה ביצירת ויזואליזציה: {str(e)}")
        raise HTTPException(status_code=500, detail=f"שגיאה ביצירת ויזואליזציה: {str(e)}")


@router.get("/dxf/{usage_id}")
def get_dxf_visualization(usage_id: int):
    """
    מייצר ויזואליזציה של קובץ DXF ומחזיר קובץ HTML
    """
    try:
        # התחברות למסד הנתונים
        db = Database()
        usage_dal = Usage(db)
        light_dal = Light(db)

        # שליפת השימוש
        usage_data = usage_dal.get_by_id(usage_id)

        if not usage_data:
            logger.error(f"לא נמצא שימוש עם מזהה {usage_id}")
            raise HTTPException(status_code=404, detail="שימוש לא נמצא")

        # בדיקה אם יש קובץ תכנית
        if len(usage_data) <= 3 or not usage_data[3]:
            logger.error(f"אין קובץ תכנית בשימוש {usage_id}")
            raise HTTPException(status_code=404, detail="לא נמצא קובץ תכנית בשימוש זה")

        # קבלת נתוני הנורות
        lights = light_dal.get_by_usage_id(usage_id)
        if not lights:
            logger.warning(f"לא נמצאו נורות לשימוש {usage_id}")

        # טיפול בנתוני נורות - דומה לקוד הקודם
        light_data = []
        for light in lights:
            if isinstance(light, tuple) and len(light) > 5:
                light_data.append({
                    "id": light[0],
                    "x": float(light[3]) if light[3] is not None else 0,
                    "y": float(light[4]) if light[4] is not None else 0,
                    "z": float(light[5]) if light[5] is not None else 0,
                    "power": float(light[6]) if light[6] is not None else 0
                })

        # שמירת הקובץ לקובץ זמני
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as temp_file:
            temp_file.write(usage_data[3])
            dxf_path = temp_file.name

        # יצירת פלט HTML עם מודל תלת-ממדי
        output_file = os.path.join(tempfile.gettempdir(), f"dxf_visual_{usage_id}.html")

        # כאן קריאה לקוד הויזואליזציה - דומה לקוד הקודם
        import subprocess
        result = subprocess.run([
            "python", "DXFVisualizer.py",
            "--usage_id", str(usage_id),
            "--output", output_file
        ], capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"שגיאה בהפעלת הויזואליזציה: {result.stderr}")
            raise HTTPException(status_code=500, detail="שגיאה ביצירת הויזואליזציה")

        # ניקוי קובץ זמני
        try:
            os.remove(dxf_path)
        except Exception as e:
            logger.warning(f"שגיאה בניקוי קובץ זמני: {str(e)}")

        # בדיקה שהקובץ נוצר
        if not os.path.exists(output_file):
            logger.error("קובץ הויזואליזציה לא נוצר")
            raise HTTPException(status_code=500, detail="קובץ הויזואליזציה לא נוצר")

        return FileResponse(
            path=output_file,
            filename=f"visualization_{usage_id}.html",
            media_type="text/html"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"שגיאה ביצירת ויזואליזציה: {str(e)}")
        raise HTTPException(status_code=500, detail=f"שגיאה ביצירת ויזואליזציה: {str(e)}")