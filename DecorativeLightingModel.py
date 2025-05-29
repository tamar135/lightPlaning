import os
from ultralytics import YOLO

class DecorativeLightingModel:
    def __init__(self, model_path="yolov8n.pt"):
        print("טוען מודל YOLO...")
        self.model = YOLO(model_path)
        print("מודל נטען.")

        # מיפוי אלמנטים למספר המלצות תאורה לפי סוג חדר
        # כל חדר מכיל רשימה של אלמנטים מותרים + המלצות רלוונטיות
        self.room_recommendations = {
            "bathroom": {
                "allowed_elements": ["mirror", "sink", "toilet", "bathtub"],
                "recommendations_map": {
                    "mirror": ["תאורה ליד מראה לאיפור/גילוח"],
                    "sink": ["תאורת עבודה מעל הכיור"],
                    "toilet": ["תאורת אווירה עדינה"],
                    "bathtub": ["תאורת אווירה מרגיעה לאמבטיה"],
                }
            },
            "bedroom": {
                "allowed_elements": ["bed", "mirror", "plant", "door", "nightstand", "wardrobe"],
                "recommendations_map": {
                    "bed": ["מנורת לילה ליד המיטה", "תאורה ב'גב ראש המיטה'"],
                    "mirror": ["תאורה ליד מראה להתארגנות/איפור"],
                    "plant": ["תאורת הדגשה לצמחים"],
                    "door": ["תאורה בכניסה"],
                    "nightstand": ["מנורת שולחן על שידת הלילה"],
                    "wardrobe": ["תאורה פנימית בארון בגדים"],
                }
            },
            "dining": {
                "allowed_elements": ["dining table", "chair", "vase", "plant", "door"],
                "recommendations_map": {
                    "dining table": ["מנורת תלייה מעל שולחן האוכל", "נברשות"],
                    "chair": ["תאורת הדגשה לאזורי ישיבה"],
                    "vase": ["תאורת נוי לפריטי תצוגה"],
                    "plant": ["תאורת הדגשה לצמחים"],
                    "door": ["תאורה בכניסה"],
                }
            },
            "gaming": {
                "allowed_elements": ["desk", "monitor", "chair", "computer", "speakers"],
                "recommendations_map": {
                    "desk": ["לד-סטריפ לתאורת רקע של שולחן", "פס תאורה למסך"],
                    "monitor": ["תאורת הטיה מאחורי המסך"],
                    "chair": ["מנורת עמידה לתאורת אווירה"],
                    "computer": ["תאורת הדגשה למערכת המחשב"],
                    "speakers": ["תאורת הדגשה עדינה למערכת שמע"],
                }
            },
            "kitchen": {
                "allowed_elements": ["counter", "sink", "stove", "refrigerator", "cabinet", "oven", "microwave"],
                "recommendations_map": {
                    "counter": ["תאורה מתחת לארונות מטבח", "מנורות תלייה מעל אי"],
                    "sink": ["תאורת עבודה מעל הכיור"],
                    "stove": ["תאורת קולט אדים"],
                    "refrigerator": ["תאורה משולבת במקרר"],
                    "cabinet": ["תאורה בתוך ארונות", "תאורת בסיס ארונות"],
                    "oven": ["תאורה פנימית בתנור"],
                    "microwave": ["תאורה משולבת במיקרוגל"],
                }
            },
            "laundry": {
                "allowed_elements": ["washer", "dryer", "sink", "shelf"],
                "recommendations_map": {
                    "washer": ["תאורת תקרה בהירה"],
                    "dryer": ["תאורת תקרה בהירה"],
                    "sink": ["תאורת עבודה מעל הכיור"],
                    "shelf": ["תאורה מעל מדפים פתוחים"],
                }
            },
            "living": {
                "allowed_elements": ["sofa", "vase", "bookshelf", "shelf", "stairs", "door", "plant", "fireplace", "tv"],
                "recommendations_map": {
                    "sofa": ["תאורה ליד ספות", "מנורות עמידה"],
                    "vase": ["תאורת נוי על ויטרינות תצוגה"],
                    "bookshelf": ["תאורה מעל מדפים פתוחים"],
                    "shelf": ["תאורה מעל מדפים פתוחים"],
                    "stairs": ["תאורת גרם מדרגות", "תאורה מתחת למדרגות"],
                    "door": ["תאורה בכניסה"],
                    "plant": ["תאורת הדגשה לצמחים"],
                    "fireplace": ["תאורת הדגשה למדף האח"],
                    "tv": ["תאורת הטיה מאחורי הטלוויזיה"],
                }
            },
            "office": {
                "allowed_elements": ["desk", "chair", "bookshelf", "computer", "monitor"],
                "recommendations_map": {
                    "desk": ["מנורת שולחן לתאורת עבודה", "תאורת תקרה כללית"],
                    "chair": ["תאורת אווירה לאזור הישיבה"],
                    "bookshelf": ["תאורה מעל מדפים פתוחים"],
                    "computer": ["תאורת הדגשה למערכת המחשב"],
                    "monitor": ["פס תאורה למסך", "תאורת הטיה"],
                }
            },
            "terrace": {
                "allowed_elements": ["plant", "chair", "table", "grill", "door"],
                "recommendations_map": {
                    "plant": ["תאורת הדגשה חיצונית לצמחים"],
                    "chair": ["מנורות שרשרת חיצוניות", "פנסים"],
                    "table": ["מנורת שולחן חיצונית"],
                    "grill": ["תאורה למנגל"],
                    "door": ["תאורת כניסה חיצונית"],
                }
            },
            "yard": {
                "allowed_elements": ["plant", "tree", "path", "fence", "door"],
                "recommendations_map": {
                    "plant": ["זרקורים לגינה לצמחים ושיחים"],
                    "tree": ["תאורת Up-lighting לעצים"],
                    "path": ["תאורת שבילים"],
                    "fence": ["תאורת גדר"],
                    "door": ["תאורת כניסה חיצונית"],
                }
            }
        }

    def analyze_image(self, image_path, room_type):
        print(f"מבצע ניתוח על התמונה: {image_path} בסוג חדר: {room_type}")
        results = self.model(image_path)

        detected_objects = []
        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = self.model.names[cls_id].lower()
                xyxy = box.xyxy[0].cpu().numpy()
                bbox = [float(coord) for coord in xyxy]

                detected_objects.append({
                    "class_name": class_name,
                    "confidence": conf,
                    "bbox": bbox
                })

        suggestions = self.make_room_based_suggestions(detected_objects, room_type)
        return detected_objects, suggestions

    def make_room_based_suggestions(self, detected_objects, room_type):
        room_type_lower = room_type.lower()
        if room_type_lower not in self.room_recommendations:
            return ["סוג חדר לא מוכר. לא ניתן לספק המלצות מותאמות."]

        allowed_elements = self.room_recommendations[room_type_lower]["allowed_elements"]
        recommendations_map = self.room_recommendations[room_type_lower]["recommendations_map"]

        suggestions = []

        for obj in detected_objects:
            cn = obj["class_name"]
            if cn in allowed_elements and cn in recommendations_map:
                suggestions.extend(recommendations_map[cn])

        unique_suggestions = list(dict.fromkeys(suggestions))

        if not unique_suggestions:
            unique_suggestions.append("לא נמצאו אלמנטים מתאימים לתאורת נוי בסוג החדר הזה.")

        return unique_suggestions