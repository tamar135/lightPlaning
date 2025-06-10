from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fileProcessor import fileProcessor
import tempfile
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["uploads"],
)

processor = fileProcessor()

# אתחול המודלים
decorative_model = None
room_classifier = None


def initialize_models():
    """אתחול המודלים"""
    global decorative_model, room_classifier

    # מודל תאורת נוי
    try:
        from DecorativeLightingModel import DecorativeLightingModel
        decorative_model = DecorativeLightingModel()
        logger.info(" מודל תאורת נוי נטען")
    except Exception as e:
        logger.warning(f"⚠ מודל תאורת נוי לא נטען: {str(e)}")
        decorative_model = None

    # מודל סיווג חדרים
    try:
        import tensorflow as tf
        model_path = r"C:\Users\user\Desktop\פרויקט גמר\fastApiProject\machineLarning\room_classification\room_classifier.h5"
        room_classifier = tf.keras.models.load_model(model_path)
        logger.info(f" מודל סיווג חדרים נטען")
        model_loaded = True

    except Exception as e:
        logger.error(f" שגיאה בטעינת מודל סיווג: {str(e)}")
        room_classifier = None

# אתחול המודלים בעת טעינת הקובץ
initialize_models()

@router.post("/upload-ifc-with-image/")
async def upload_ifc_with_image(
        ifc_file: UploadFile = File(...),
        image_file: UploadFile = File(...),
        user_id: str = Form(...)
):
    """
    העלאת קובץ IFC ותמונה
    """
    logger.info(f"התחלת תהליך העלאה משולב: IFC={ifc_file.filename}, Image={image_file.filename}")

    # בדיקת קבצים
    is_ifc_valid, ifc_message = await processor.validate_file(ifc_file)
    if not is_ifc_valid:
        raise HTTPException(status_code=400, detail=ifc_message)

    # בדיקת תמונה
    allowed_image_types = [".jpg", ".png"]
    image_ext = Path(image_file.filename).suffix.lower()
    if image_ext not in allowed_image_types:
        raise HTTPException(status_code=400, detail="סוג תמונה לא תקין. מותר JPG, PNG")

    # שמירת תמונה זמנית
    temp_image_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=image_ext) as temp_image:
            image_data = await image_file.read()
            temp_image.write(image_data)
            temp_image_path = temp_image.name

        logger.info(f"תמונה נשמרה זמנית: {temp_image_path}")

        #  זיהוי סוג חדר מהתמונה
        room_type = await classify_room_from_image(temp_image_path)
        logger.info(f"סוג חדר זוהה: {room_type}")

        #  תכנון תאורה רגילה עם IFC + סוג חדר
        lighting_result = await processor.process_and_save_file(ifc_file, user_id, room_type)
        usage_id = lighting_result["usage_id"]

        #  תכנון תאורת נוי עם תמונה + סוג חדר
        decorative_suggestions = await plan_decorative_lighting(temp_image_path, room_type)

        result = {
            "usage_id": usage_id,
            "room_type_detected": room_type,
            "regular_lighting": {
                "message": lighting_result["message"],
                "lights_count": lighting_result.get("lights_count", 0)
            },
            "decorative_lighting": decorative_suggestions,
            "message": f"התהליך הושלם! זוהה חדר מסוג {room_type}"
        }

        logger.info(f"תהליך משולב הושלם בהצלחה: {result}")
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"שגיאה בתהליך משולב: {str(e)}")
        raise HTTPException(status_code=500, detail=f"שגיאהבעיבוד: {str(e)}")

    finally:
        # ניקוי קובץ תמונה זמני
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.remove(temp_image_path)
                logger.info("קובץ תמונה זמני נמחק")
            except:
                pass


async def classify_room_from_image(image_path: str) -> str:
    """זיהוי סוג חדר מתמונה"""
    try:
        if room_classifier is None:
            logger.warning("מודל סיווג לא זמין - משתמש בברירת מחדל")
            return "bedroom"

        import numpy as np
        from tensorflow.keras.preprocessing import image

        # טעינת תמונה ועיבוד
        img = image.load_img(image_path, target_size=(64, 64))
        img_array = image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array /= 255.0

        # חיזוי
        predictions = room_classifier.predict(img_array)
        predicted_class = np.argmax(predictions[0])
        confidence = np.max(predictions[0])

        # מיפוי תוצאות
        room_types = ["bathroom", "bedroom", "dining", "gaming", "kitchen", "laundry", "living", "office", "terrace", "yard"]

        if predicted_class < len(room_types):
            detected_room = room_types[predicted_class]
            logger.info(f"זוהה חדר: {detected_room} עם ביטחון: {confidence:.2f}")
            return detected_room
        else:
            logger.warning("מחלקה לא מוכרת - ברירת מחדל")
            return "bedroom"

    except Exception as e:
        logger.error(f"שגיאה בסיווג חדר: {str(e)}")
        return "bedroom"  # ברירת מחדל


async def plan_decorative_lighting(image_path: str, room_type: str) -> dict:
    """תכנון תאורת נוי"""
    try:
        if decorative_model is None:
            logger.warning("מודל תאורת נוי לא זמין - משתמש בהמלצות בסיסיות")
            basic_suggestions = {
                "bedroom": ["מנורת לילה ליד המיטה", "תאורה ליד מראה"],
                "kitchen": ["תאורה מתחת לארונות", "תאורה מעל האי"],
                "living": ["תאורה ליד ספות", "תאורת הטיה לטלוויזיה"],
                "bathroom": ["תאורה ליד מראה", "תאורת אווירה"],
                "office": ["מנורת שולחן", "תאורת הטיה למסך"],
                "dining": ["נברשת מעל השולחן", "תאורת נוי"]
            }

            suggestions = basic_suggestions.get(room_type.lower(), ["תאורת אווירה כללית"])

            return {
                "suggestions": suggestions,
                "detected_objects": [],
                "room_type": room_type,
                "method": "basic_recommendations"
            }

        # ניתוח עם המודל
        detected_objects, suggestions = decorative_model.analyze_image(image_path, room_type)

        return {
            "suggestions": suggestions,
            "detected_objects": detected_objects,
            "room_type": room_type,
            "method": "yolo_analysis"
        }

    except Exception as e:
        logger.error(f"שגיאה בתכנון תאורת נוי: {str(e)}")
        return {
            "suggestions": [f"שגיאה בתכנון תאורת נוי: {str(e)}"],
            "detected_objects": [],
            "room_type": room_type,
            "method": "error"
        }
