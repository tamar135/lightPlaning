import ezdxf
import json
import tempfile
import logging
import os
from math import sqrt

# הגדרת לוגר
from RoomType import RoomType
from MaterialReflection import MaterialReflection

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def process_dxf_file(file_path: str, room_type: str) -> str:
    """
    מעבד קובץ DXF ומייצר קובץ JSON עם כל המידע הרלוונטי
    במבנה זהה לפלט של IFCProcessor

    Args:
        file_path: נתיב לקובץ ה-DXF
        room_type: סוג החדר

    Returns:
        str: נתיב לקובץ ה-JSON המיוצר
    """
    logger.debug("מעבד קובץ DXF: %s", file_path)

    try:
        # טעינת קובץ ה-DXF
        doc = ezdxf.readfile(file_path)
        modelspace = doc.modelspace()
        logger.debug("קובץ DXF נטען בהצלחה. גרסה: %s", doc.dxfversion)
    except Exception as e:
        logger.error("שגיאה בטעינת קובץ DXF: %s", str(e))
        raise

    # חילוץ מידע על החדר
    room_dimensions = extract_room_dimensions(doc, modelspace)

    # אם לא סופק סוג חדר, ננסה לזהות מהקובץ
    if not room_type:
        room_type = identify_room_type_from_dxf(doc, modelspace)

    # קביעת עוצמת תאורה מומלצת לפי סוג החדר
    room_type_enum = RoomType.get_by_name(room_type)
    recommended_lux = room_type_enum.recommended_lux
    logger.debug("זוהה חדר מסוג %s עם תאורה מומלצת %d לוקס",
                 room_type, recommended_lux)

    # יצירת המבנה הבסיסי לתוצאה - זהה למבנה של IFCProcessor
    results = [
        {"RecommendedLux": recommended_lux},
        {"RoomType": room_type},
        {"RoomHeight": room_dimensions.get("height", 2.5)},
        {"RoomArea": room_dimensions.get("area", 20.0)}
    ]

    # חילוץ כל האלמנטים מהקובץ
    elements_data = extract_dxf_elements(doc, modelspace, room_dimensions)

    # הוספת נקודת אמצע החדר - חשוב למערכת התאורה
    center_data = create_center_point(room_dimensions)
    if center_data:
        elements_data.append(center_data)

    # שילוב כל המידע ברשימת התוצאות
    results.extend(elements_data)

    # שמירה לקובץ JSON זמני
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as temp_file:
            json.dump(results, temp_file, ensure_ascii=False, indent=2)
            json_path = temp_file.name
            logger.debug("נשמר קובץ JSON: %s", json_path)
            return json_path
    except Exception as e:
        logger.error("שגיאה בשמירת קובץ JSON: %s", str(e))
        raise


def extract_room_dimensions(doc, modelspace):
    """
    מחלץ את מידות החדר מתוך קובץ ה-DXF
    """
    dimensions = {
        "height": 2.5,  # גובה ברירת מחדל
        "area": 20.0,  # שטח ברירת מחדל
        "length": 5.0,  # אורך ברירת מחדל
        "width": 4.0,  # רוחב ברירת מחדל
        "center_x": 0,  # מרכז החדר X
        "center_y": 0  # מרכז החדר Y
    }

    # חיפוש פוליגונים שמייצגים את גבולות החדר
    room_candidates = []

    # חיפוש בשכבות שבדרך כלל מכילות קווי מתאר של חדרים
    room_layer_keywords = ['ROOM', 'SPACE', 'AREA', 'WALL', 'PARTITION', 'חדר', 'שטח', 'קירות', 'קיר']

    # חיפוש פוליליינים סגורים שיכולים להיות קווי מתאר של חדר
    for polyline in modelspace.query('LWPOLYLINE'):
        try:
            # בדיקה אם הפוליליין סגור
            if hasattr(polyline, 'closed') and polyline.closed:
                layer_name = polyline.dxf.layer.upper() if hasattr(polyline.dxf, 'layer') else ""

                # בדיקה אם השכבה קשורה לחדרים
                is_room_layer = any(keyword in layer_name for keyword in room_layer_keywords)

                # קבל את הנקודות ובדוק אם יש מספיק ליצירת חדר
                points = list(polyline.vertices())
                if len(points) >= 3:  # לפחות משולש
                    # חישוב השטח
                    area = calculate_polygon_area(points)

                    # אם השטח גדול מסף מינימלי והשכבה קשורה לחדרים, זה כנראה חדר
                    min_room_area = 4.0  # חדר מינימלי 2x2 מ'
                    if area > min_room_area or is_room_layer:
                        room_candidates.append({
                            'polyline': polyline,
                            'area': area,
                            'points': points,
                            'is_room_layer': is_room_layer
                        })
        except Exception as e:
            logger.warning(f"שגיאה בבדיקת פוליליין: {str(e)}")

    # גם קווים רגילים יכולים להיות חלק מחדר
    # אנחנו מחפשים קווים שיוצרים מלבן או פוליגון סגור
    try:
        lines = list(modelspace.query('LINE'))
        if lines:
            # אלגוריתם להרכבת קווים לפוליגונים סגורים
            # הפשטה: אם יש 4 קווים שיוצרים מלבן, זה יכול להיות חדר
            # קוד מלא יותר מורכב מדי לכאן
            pass
    except Exception as e:
        logger.warning(f"שגיאה בבדיקת קווים: {str(e)}")

    # בחירת החדר הגדול ביותר או הראשון שמוגדר בשכבת חדר
    if room_candidates:
        # מיון לפי: 1. האם השכבה קשורה לחדרים 2. גודל השטח
        room_candidates.sort(key=lambda x: (-1 if x['is_room_layer'] else 0, -x['area']))

        best_room = room_candidates[0]
        area = best_room['area']
        points = best_room['points']

        # חישוב מימדים מהנקודות
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)

        # עדכון המידות
        dimensions['area'] = area
        dimensions['length'] = max_y - min_y
        dimensions['width'] = max_x - min_x
        dimensions['center_x'] = (min_x + max_x) / 2
        dimensions['center_y'] = (min_y + max_y) / 2

        logger.debug(f"נמצא חדר עם שטח {area:.2f}, אורך {dimensions['length']:.2f}, רוחב {dimensions['width']:.2f}")

    # ניסיון לחלץ גובה
    # חיפוש מידע בטקסטים והערות
    try:
        # חפש תחילה TEXT
        for text_entity in modelspace.query('TEXT'):
            try:
                if hasattr(text_entity, 'dxf') and hasattr(text_entity.dxf, 'text'):
                    text = text_entity.dxf.text.lower()

                    # חיפוש מילות מפתח הקשורות לגובה
                    if any(height_kw in text for height_kw in ['height', 'גובה', 'h=', 'h =', 'גובה=', 'גובה =']):
                        # חילוץ מספרים מהטקסט
                        import re
                        numbers = re.findall(r'\d+\.\d+|\d+', text)

                        # בדיקה אם המספרים הגיוניים לגובה חדר
                        for num_str in numbers:
                            height = float(num_str)
                            if 2.0 <= height <= 5.0:  # טווח גבהים סביר
                                dimensions['height'] = height
                                logger.debug(f"נמצא גובה חדר: {height}מ'")
                                break
            except Exception as e:
                logger.warning(f"שגיאה בחילוץ טקסט: {str(e)}")

        # אחר כך חפש MTEXT
        for text_entity in modelspace.query('MTEXT'):
            try:
                if hasattr(text_entity, 'dxf') and hasattr(text_entity.dxf, 'text'):
                    text = text_entity.dxf.text.lower()

                    # חיפוש מילות מפתח הקשורות לגובה
                    if any(height_kw in text for height_kw in ['height', 'גובה', 'h=', 'h =', 'גובה=', 'גובה =']):
                        # חילוץ מספרים מהטקסט
                        import re
                        numbers = re.findall(r'\d+\.\d+|\d+', text)

                        # בדיקה אם המספרים הגיוניים לגובה חדר
                        for num_str in numbers:
                            height = float(num_str)
                            if 2.0 <= height <= 5.0:  # טווח גבהים סביר
                                dimensions['height'] = height
                                logger.debug(f"נמצא גובה חדר: {height}מ'")
                                break
            except Exception as e:
                logger.warning(f"שגיאה בחילוץ טקסט: {str(e)}")
    except Exception as e:
        logger.warning(f"שגיאה בחיפוש טקסטים: {str(e)}")

    # חיפוש חתכים שיכולים להצביע על גובה
    # בהרבה קבצי DXF, יש שכבה נפרדת לחתכים
    try:
        # חפש תחילה LWPOLYLINE
        for entity in modelspace.query('LWPOLYLINE'):
            try:
                layer_name = entity.dxf.layer.upper() if hasattr(entity.dxf, 'layer') else ""

                # בדיקה אם זה חתך
                if any(section_kw in layer_name for section_kw in ['SECTION', 'חתך', 'ELEVATION', 'חזית']):
                    # לוגיקה לחילוץ גובה מחתך
                    # מורכב מדי לממש כאן בשלמות
                    pass
            except Exception as e:
                logger.warning(f"שגיאה בבדיקת חתך LWPOLYLINE: {str(e)}")

        # חפש אחר כך LINE
        for entity in modelspace.query('LINE'):
            try:
                layer_name = entity.dxf.layer.upper() if hasattr(entity.dxf, 'layer') else ""

                # בדיקה אם זה חתך
                if any(section_kw in layer_name for section_kw in ['SECTION', 'חתך', 'ELEVATION', 'חזית']):
                    # לוגיקה לחילוץ גובה מחתך
                    # מורכב מדי לממש כאן בשלמות
                    pass
            except Exception as e:
                logger.warning(f"שגיאה בבדיקת חתך LINE: {str(e)}")
    except Exception as e:
        logger.warning(f"שגיאה בבדיקת חתכים: {str(e)}")

    return dimensions


def identify_room_type_from_dxf(doc, modelspace):
    """
    מזהה את סוג החדר מתוך קובץ ה-DXF
    """
    # מיפוי מילות מפתח לסוגי חדרים
    room_types = {
        "bedroom": ["bedroom", "חדר שינה", "שינה", "bed", "sleeping"],
        "living": ["living", "סלון", "מגורים", "lounge", "family"],
        "kitchen": ["kitchen", "מטבח", "cook", "cooking"],
        "bathroom": ["bathroom", "שירותים", "אמבטיה", "מקלחת", "bath", "toilet", "shower", "wc"],
        "office": ["office", "משרד", "study", "עבודה", "work"],
        "hallway": ["hallway", "מסדרון", "פרוזדור", "מעבר", "corridor", "passage"],
        "dining": ["dining", "אוכל", "פינת אוכל", "dining room"]
    }

    # 1. חיפוש בשמות השכבות
    for layer in doc.layers:
        layer_name = layer.dxf.name.lower()
        for room_type, keywords in room_types.items():
            if any(keyword in layer_name for keyword in keywords):
                logger.debug(f"זוהה סוג חדר '{room_type}' משם שכבה: {layer_name}")
                return room_type

    # 2. חיפוש בטקסטים
    try:
        # חפש תחילה TEXT
        for text_entity in modelspace.query('TEXT'):
            if hasattr(text_entity, 'dxf') and hasattr(text_entity.dxf, 'text'):
                text = text_entity.dxf.text.lower()
                for room_type, keywords in room_types.items():
                    if any(keyword in text for keyword in keywords):
                        logger.debug(f"זוהה סוג חדר '{room_type}' מטקסט: {text}")
                        return room_type

        # חפש אחר כך MTEXT
        for text_entity in modelspace.query('MTEXT'):
            if hasattr(text_entity, 'dxf') and hasattr(text_entity.dxf, 'text'):
                text = text_entity.dxf.text.lower()
                for room_type, keywords in room_types.items():
                    if any(keyword in text for keyword in keywords):
                        logger.debug(f"זוהה סוג חדר '{room_type}' מטקסט: {text}")
                        return room_type
    except Exception as e:
        logger.warning(f"שגיאה בחיפוש טקסטים לזיהוי סוג חדר: {str(e)}")

    # 3. חיפוש בבלוקים (INSERT)
    for insert in modelspace.query('INSERT'):
        if hasattr(insert, 'dxf') and hasattr(insert.dxf, 'name'):
            block_name = insert.dxf.name.lower()
            for room_type, keywords in room_types.items():
                if any(keyword in block_name for keyword in keywords):
                    logger.debug(f"זוהה סוג חדר '{room_type}' משם בלוק: {block_name}")
                    return room_type

    # ברירת מחדל אם לא זוהה
    logger.debug("לא זוהה סוג חדר, משתמש בברירת מחדל: bedroom")
    return "bedroom"


def extract_dxf_elements(doc, modelspace, room_dimensions):
    """
    מחלץ את כל האלמנטים מקובץ ה-DXF
    """
    elements = []

    # מיפוי סוגי אלמנטים לפי מילות מפתח בשכבות
    layer_type_mapping = {
        "wall": ["WALL", "קיר", "קירות", "A-WALL", "PARTITION", "מחיצה"],
        "window": ["WINDOW", "חלון", "חלונות", "A-GLAZ", "A-WINDOW", "GLAZING"],
        "door": ["DOOR", "דלת", "דלתות", "A-DOOR", "ENTRANCE"],
        "slab": ["SLAB", "רצפה", "תקרה", "A-FLOR", "A-CEILING", "FLOOR", "CEILING"],
        "table": ["TABLE", "שולחן", "A-FURN-TBL", "FURNITURE-TABLE"],
        "desk": ["DESK", "שולחן עבודה", "A-FURN-DSK", "WORKSTATION"],
        "chair": ["CHAIR", "כיסא", "A-FURN-CHR", "SEAT"],
        "bed": ["BED", "מיטה", "A-FURN-BED"],
        "counter": ["COUNTER", "דלפק", "A-FURN-CNT", "WORKTOP"],
        "sofa": ["SOFA", "ספה", "COUCH", "A-FURN-SOF"]
    }

    # מעבר על הישויות העיקריות בקובץ
    entity_types = ['INSERT', 'LWPOLYLINE', 'POLYLINE', 'LINE', 'CIRCLE', 'ARC', 'SOLID']

    for entity_type in entity_types:
        try:
            entities = modelspace.query(entity_type)
            logger.debug(f"נמצאו {len(entities)} אלמנטים מסוג {entity_type}")

            for entity in entities:
                try:
                    # קביעת סוג האלמנט לפי שכבה או שם בלוק
                    element_type = None

                    # בדיקת שם השכבה
                    if hasattr(entity, 'dxf') and hasattr(entity.dxf, 'layer'):
                        layer_name = entity.dxf.layer.upper()

                        for type_name, keywords in layer_type_mapping.items():
                            if any(keyword.upper() in layer_name for keyword in keywords):
                                element_type = type_name
                                break

                    # בדיקת שם בלוק (רק ל-INSERT)
                    if entity_type == 'INSERT' and not element_type:
                        if hasattr(entity, 'dxf') and hasattr(entity.dxf, 'name'):
                            block_name = entity.dxf.name.upper()

                            for type_name, keywords in layer_type_mapping.items():
                                if any(keyword.upper() in block_name for keyword in keywords):
                                    element_type = type_name
                                    break

                    # אם לא זיהינו סוג, ננסה לקבוע לפי המאפיינים הגיאומטריים
                    if not element_type and entity_type in ['LINE', 'LWPOLYLINE', 'POLYLINE']:
                        # קווים ארוכים יחסית ללא עובי רב יכולים להיות קירות
                        if get_entity_length(entity) > 1.0:  # מעל מטר
                            element_type = "wall"

                    # אם לא זיהינו סוג, נדלג על האלמנט
                    if not element_type:
                        continue

                    # חילוץ מיקום ומידות
                    location_data = extract_entity_dimensions(entity, entity_type, element_type)

                    # זיהוי חומר
                    material = identify_material_for_element_type(element_type,
                                                                  layer_name if hasattr(entity, 'dxf') and hasattr(
                                                                      entity.dxf, 'layer') else "")

                    # מקדם החזרת אור מהחומר
                    material_reflection = MaterialReflection.get_by_material_name(material)

                    # קביעת דרישות תאורה לפי סוג האלמנט
                    required_lux = 0
                    if element_type in ["table", "desk", "counter"]:
                        if element_type == "desk":
                            required_lux = 500  # שולחנות עבודה דורשים יותר תאורה
                        else:
                            required_lux = 300  # שולחנות רגילים

                    # יצירת אלמנט במבנה זהה לפלט של IFCProcessor
                    element_data = {
                        "ElementType": element_type,
                        "X": location_data.get("X", 0),
                        "Y": location_data.get("Y", 0),
                        "Z": location_data.get("Z", 0),
                        "Width": location_data.get("Width", 0),
                        "Length": location_data.get("Length", 0),
                        "Height": location_data.get("Height", 0),
                        "Material": material,
                        "RequiredLuks": required_lux
                    }

                    # הוספת מקדם החזרת אור מהחומר, אם קיים
                    reflection_factor = material_reflection.reflection_factor
                    if reflection_factor > 0:
                        element_data["ReflectionFactor"] = reflection_factor

                    # הוספת האלמנט לרשימה
                    elements.append(element_data)

                except Exception as e:
                    logger.warning(f"שגיאה בעיבוד אלמנט מסוג {entity_type}: {str(e)}")
        except Exception as e:
            logger.warning(f"שגיאה בשליפת אלמנטים מסוג {entity_type}: {str(e)}")

    return elements


def extract_entity_dimensions(entity, entity_type, element_type):
    """
    מחלץ מיקום ומידות של אלמנט
    """
    result = {
        "X": 0, "Y": 0, "Z": 0,
        "Width": 0, "Length": 0, "Height": 0
    }

    try:
        if entity_type == 'LINE':
            # קו - נשתמש בנקודת התחלה כמיקום
            start = entity.dxf.start
            end = entity.dxf.end
            result["X"] = start[0]
            result["Y"] = start[1]
            result["Z"] = start[2] if len(start) > 2 else 0

            # חישוב אורך הקו
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = sqrt(dx * dx + dy * dy)

            # הגדרת מידות לפי סוג האלמנט
            if element_type == "wall":
                result["Length"] = length
                result["Width"] = 0.15  # עובי טיפוסי לקיר
                result["Height"] = 2.5  # גובה טיפוסי
            else:
                # אורך וגובה לפי כיוון הקו
                if abs(dx) > abs(dy):  # קו אופקי יותר
                    result["Length"] = length
                    result["Width"] = 0.1
                else:  # קו אנכי יותר
                    result["Width"] = length
                    result["Length"] = 0.1
                result["Height"] = get_default_height_for_element(element_type)

        elif entity_type in ['LWPOLYLINE', 'POLYLINE']:
            # פוליליין - חישוב מרכז וממדים
            if hasattr(entity, 'get_points'):
                points = list(entity.get_points()) if callable(entity.get_points) else []
            elif hasattr(entity, 'vertices'):
                points = list(entity.vertices())
            else:
                points = []

            if points:
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                min_x, max_x = min(x_coords), max(x_coords)
                min_y, max_y = min(y_coords), max(y_coords)

                # מיקום = מרכז האלמנט
                result["X"] = (min_x + max_x) / 2
                result["Y"] = (min_y + max_y) / 2
                result["Z"] = 0  # ברירת מחדל

                # ממדים
                result["Width"] = max_x - min_x if max_x > min_x else 0.1
                result["Length"] = max_y - min_y if max_y > min_y else 0.1
                result["Height"] = get_default_height_for_element(element_type)

                # תיקון לאלמנטים מיוחדים
                if entity.closed and element_type == "wall":
                    # אם זה פוליליין סגור שמייצג חדר, נשתמש בעובי קיר
                    result["Width"] = 0.15

        elif entity_type == 'CIRCLE':
            # עיגול - מרכז כמיקום, קוטר כרוחב ואורך
            center = entity.dxf.center
            result["X"] = center[0]
            result["Y"] = center[1]
            result["Z"] = center[2] if len(center) > 2 else 0

            diameter = entity.dxf.radius * 2
            result["Width"] = diameter
            result["Length"] = diameter
            result["Height"] = get_default_height_for_element(element_type)

        elif entity_type == 'INSERT':
            # בלוק - מיקום בנקודת ההכנסה
            insertion = entity.dxf.insert
            result["X"] = insertion[0]
            result["Y"] = insertion[1]
            result["Z"] = insertion[2] if len(insertion) > 2 else 0

            # אם יש מידות סקייל, נשתמש בהן
            scale_x = getattr(entity.dxf, 'xscale', 1)
            scale_y = getattr(entity.dxf, 'yscale', 1)
            scale_z = getattr(entity.dxf, 'zscale', 1)

            # מידות ברירת מחדל לפי סוג האלמנט
            default_dimensions = get_default_dimensions_for_element(element_type)
            result["Width"] = default_dimensions["width"] * scale_x
            result["Length"] = default_dimensions["length"] * scale_y
            result["Height"] = default_dimensions["height"] * scale_z

    except Exception as e:
        logger.warning(f"שגיאה בחילוץ מידות מאלמנט: {str(e)}")

    return result


def identify_material_for_element_type(element_type, layer_name=""):
    """
    זיהוי חומר לפי סוג האלמנט ושם השכבה
    """
    # חומרים ברירת מחדל לפי סוג אלמנט
    default_materials = {
        "wall": "concrete",
        "window": "glass",
        "door": "wood",
        "slab": "concrete",
        "table": "wood",
        "desk": "wood",
        "chair": "fabric",
        "bed": "fabric",
        "counter": "wood",
        "sofa": "fabric"
    }

    # ניסיון לזהות חומר משם השכבה
    layer_lower = layer_name.lower()
    material_keywords = {
        "wood": ["wood", "timber", "עץ"],
        "glass": ["glass", "window", "זכוכית", "חלון"],
        "metal": ["metal", "steel", "מתכת", "פלדה", "iron", "aluminum", "aluminium"],
        "concrete": ["concrete", "cement", "בטון", "plaster", "טיח"],
        "ceramic": ["tile", "ceramic", "אריח", "קרמיקה", "porcelain", "פורצלן"],
        "fabric": ["fabric", "textile", "בד", "cloth", "upholstery"],
        "glossy": ["glossy", "מבריק", "gloss", "polished", "mirror", "reflective"]
    }

    for material, keywords in material_keywords.items():
        if any(keyword in layer_lower for keyword in keywords):
            return material

    # אם לא זוהה, החזר ברירת מחדל לפי סוג האלמנט
    return default_materials.get(element_type, "unknown")


def get_default_height_for_element(element_type):
    """
    מחזיר גובה ברירת מחדל לפי סוג האלמנט
    """
    heights = {
        "wall": 2.5,
        "window": 1.0,
        "door": 2.1,
        "slab": 0.2,
        "table": 0.75,
        "desk": 0.75,
        "chair": 0.8,
        "bed": 0.6,
        "counter": 0.9,
        "sofa": 0.7
    }
    return heights.get(element_type, 0.5)


def get_default_dimensions_for_element(element_type):
    """
    מחזיר מידות ברירת מחדל לפי סוג האלמנט
    """
    dimensions = {
        "wall": {"width": 0.15, "length": 3.0, "height": 2.5},
        "window": {"width": 1.2, "length": 0.1, "height": 1.0},
        "door": {"width": 0.9, "length": 0.1, "height": 2.1},
        "slab": {"width": 4.0, "length": 5.0, "height": 0.2},
        "table": {"width": 1.2, "length": 0.8, "height": 0.75},
        "desk": {"width": 1.6, "length": 0.8, "height": 0.75},
        "chair": {"width": 0.5, "length": 0.5, "height": 0.8},
        "bed": {"width": 1.4, "length": 2.0, "height": 0.6},
        "counter": {"width": 0.6, "length": 1.5, "height": 0.9},
        "sofa": {"width": 0.9, "length": 1.8, "height": 0.7}
    }
    return dimensions.get(element_type, {"width": 1.0, "length": 1.0, "height": 0.5})


def get_entity_length(entity):
    """
    מחשב את האורך של אלמנט
    """
    try:
        if hasattr(entity, 'dxf'):
            if entity.dxftype() == 'LINE':
                # קו רגיל
                start = entity.dxf.start
                end = entity.dxf.end
                return sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)

            elif entity.dxftype() in ['LWPOLYLINE', 'POLYLINE']:
                # פוליליין
                if hasattr(entity, 'get_points'):
                    points = list(entity.get_points()) if callable(entity.get_points) else []
                elif hasattr(entity, 'vertices'):
                    points = list(entity.vertices())
                else:
                    return 0

                if len(points) < 2:
                    return 0

                # חישוב האורך הכולל של הפוליליין
                total_length = 0
                for i in range(len(points) - 1):
                    p1 = points[i]
                    p2 = points[i + 1]
                    segment_length = sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)
                    total_length += segment_length

                # אם הפוליליין סגור, נוסיף את הקטע האחרון שסוגר את הצורה
                if hasattr(entity, 'closed') and entity.closed and len(points) > 2:
                    p1 = points[-1]
                    p2 = points[0]
                    segment_length = sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)
                    total_length += segment_length

                return total_length

        return 0

    except Exception as e:
        logger.warning(f"שגיאה בחישוב אורך אלמנט: {str(e)}")
        return 0


def calculate_polygon_area(points):
    """
    מחשב שטח של פוליגון לפי נוסחת Shoelace (גאוס)
    """
    n = len(points)
    if n < 3:  # פוליגון חייב לפחות 3 נקודות
        return 0

    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]

    return abs(area) / 2.0


def create_center_point(room_dimensions):
    """
    יוצר נקודת מרכז לחדר שתשמש כנקודת ייחוס
    """
    return {
        "ElementType": "center_point",
        "X": room_dimensions.get("center_x", 0),
        "Y": room_dimensions.get("center_y", 0),
        "Z": 0,
        "Width": 0,
        "Length": 0,
        "Height": 0,
        "RequiredLuks": 0,
        "Material": ""
    }