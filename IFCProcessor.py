# IFCProcessor.py
import ifcopenshell
import json
import tempfile
import logging
import os
from math import sqrt

# הגדרת לוגר
from RoomType import RoomType
from MaterialReflection import MaterialReflection  # ייבוא ה-ENUM של החומר

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def process_ifc_file(file_path: str, room_type: str) -> str:
    """
    מעבד קובץ IFC ומייצר קובץ JSON עם כל המידע הרלוונטי

    Args:
        file_path: נתיב לקובץ ה-IFC
        room_type: סוג החדר

    Returns:
        str: נתיב לקובץ ה-JSON המיוצר
    """
    logger.debug("מעבד קובץ IFC: %s", file_path)

    try:
        # טעינת מודל ה-IFC
        model = ifcopenshell.open(file_path)
        logger.debug("קובץ IFC נטען בהצלחה. סכמה: %s", model.schema)
    except Exception as e:
        logger.error("שגיאה בטעינת קובץ IFC: %s", str(e))
        raise

    # מידע כללי על החדר
    room_info = extract_room_info(model)
    if not room_type:
        room_type = room_info.get("RoomType", RoomType.UNKNOWN.room_name)

    # קביעת עוצמת תאורה מומלצת לפי סוג החדר
    room_type_enum = RoomType.get_by_name(room_type)
    recommended_lux = room_type_enum.recommended_lux
    logger.debug("זוהה חדר מסוג %s עם תאורה מומלצת %d לוקס",
                 room_type, recommended_lux)

    # יצירת המבנה הבסיסי לתוצאה
    results = [
        {"RecommendedLux": recommended_lux},
        {"RoomType": room_type},
        {"RoomHeight": room_info.get("RoomHeight", 2.5)},
        {"RoomArea": room_info.get("RoomArea", 20.0)}
    ]

    # חילוץ כל האלמנטים
    elements_by_type = {
        "walls": ["IfcWall", "IfcWallStandardCase"],
        "windows": ["IfcWindow", "IfcWindowStandardCase"],
        "doors": ["IfcDoor", "IfcDoorStandardCase"],
        "slabs": ["IfcSlab"],
        "furniture": ["IfcFurnishingElement"],
        "fixtures": ["IfcFlowTerminal"],
        "space": ["IfcSpace"]
    }

    elements_data = []
    logger.debug("מתחיל לחלץ אלמנטים מהמודל")

    for category, ifc_types in elements_by_type.items():
        logger.debug("מחלץ אלמנטים מסוג %s", category)

        for ifc_type in ifc_types:
            try:
                elements = model.by_type(ifc_type)
                logger.debug("נמצאו %d אלמנטים מסוג %s", len(elements), ifc_type)

                for element in elements:
                    try:
                        element_data = extract_element_data(element, model, category)
                        if element_data:
                            elements_data.append(element_data)
                    except Exception as e:
                        logger.warning("שגיאה בחילוץ נתוני אלמנט: %s", str(e))
            except Exception as e:
                logger.warning("שגיאה בטעינת אלמנטים מסוג %s: %s", ifc_type, str(e))

    # הוספת נקודת אמצע החדר - חשוב למערכת התאורה
    center_data = create_center_point(room_info)
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


def extract_room_info(model):
    """מחלץ מידע בסיסי על החדר מתוך המודל"""
    room_info = {
        "RecommendedLux": 300,  # ערך ברירת מחדל
        "RoomType": "bedroom",  # ערך ברירת מחדל
        "RoomHeight": 2.5,  # ערך ברירת מחדל
        "RoomArea": 20.0  # ערך ברירת מחדל
    }

    # ניסיון לחלץ חדרים/מרחבים
    try:
        spaces = model.by_type("IfcSpace")

        if spaces:
            logger.debug("נמצאו %d מרחבים במודל", len(spaces))
            # נשתמש במרחב הראשון שנמצא (או באוסף המרחבים הגדול ביותר)
            largest_space = spaces[0]
            largest_area = 0

            for space in spaces:
                # חיפוש מידע על סוג החדר
                psets = get_element_properties(space)

                # חילוץ שם/סוג החדר
                space_name = getattr(space, "Name", "").lower() if hasattr(space, "Name") else ""
                space_long_name = getattr(space, "LongName", "").lower() if hasattr(space, "LongName") else ""

                # זיהוי סוג החדר לפי מילות מפתח
                room_types = {
                    "bedroom": ["bedroom", "חדר שינה", "שינה", "bed", "sleeping"],
                    "living": ["living", "סלון", "מגורים", "lounge"],
                    "kitchen": ["kitchen", "מטבח", "cook"],
                    "bathroom": ["bathroom", "שירותים", "אמבטיה", "מקלחת", "bath", "toilet", "shower"],
                    "office": ["office", "משרד", "study", "עבודה"]
                }

                detected_type = room_info["RoomType"]  # ברירת מחדל
                for rtype, keywords in room_types.items():
                    if any(kw in space_name for kw in keywords) or any(kw in space_long_name for kw in keywords):
                        detected_type = rtype
                        break

                # אם מצאנו סוג חדר, נעדכן את המידע
                room_info["RoomType"] = detected_type

                # חיפוש מידע על גודל החדר
                try:
                    # חיפוש שטח וגובה בתוך מאפייני האלמנט
                    for prop_set_name, props in psets.items():
                        if "Area" in props:
                            area_value = float(props["Area"])
                            if area_value > largest_area:
                                largest_area = area_value
                                largest_space = space
                                room_info["RoomArea"] = area_value

                        if "Height" in props:
                            room_info["RoomHeight"] = float(props["Height"])
                except Exception as e:
                    logger.warning("שגיאה בחילוץ מידות החדר: %s", str(e))

    except Exception as e:
        logger.warning("שגיאה בחילוץ מידע על החדר: %s", str(e))

    return room_info


def extract_room_dimensions(model):
    """
    מחלץ את מידות החדרים (גובה, שטח, אורך, רוחב) באופן מפורט

    Args:
        model: מודל IFC טעון

    Returns:
        dict: מילון עם מידות החדר: גובה, שטח, אורך, רוחב
    """
    dimensions = {
        "height": 2.5,  # גובה ברירת מחדל
        "area": 20.0,  # שטח ברירת מחדל
        "length": 5.0,  # אורך ברירת מחדל
        "width": 4.0  # רוחב ברירת מחדל
    }

    try:
        # שיטה 1: חיפוש אובייקטים מסוג חדר/מרחב (IfcSpace)
        spaces = model.by_type("IfcSpace")
        if spaces:
            logger.debug("נמצאו %d מרחבים מסוג IfcSpace", len(spaces))

            # נחפש את החדר הגדול ביותר
            largest_space = None
            largest_area = 0

            for space in spaces:
                # ניסיון לחלץ שטח
                space_area = 0

                # ניסיון 1: מתוך מאפיינים
                properties = get_element_properties(space)
                for pset_name, props in properties.items():
                    for prop_name, prop_value in props.items():
                        # חיפוש שטח
                        if "Area" in prop_name:
                            try:
                                space_area = float(prop_value)
                                logger.debug("נמצא שטח %f עבור חדר %s", space_area, getattr(space, "Name", "ללא שם"))
                            except (ValueError, TypeError):
                                pass

                        # חיפוש גובה
                        if "Height" in prop_name:
                            try:
                                dimensions["height"] = float(prop_value)
                                logger.debug("נמצא גובה %f עבור חדר %s", dimensions["height"],
                                             getattr(space, "Name", "ללא שם"))
                            except (ValueError, TypeError):
                                pass

                        # חיפוש אורך ורוחב
                        if "Length" in prop_name:
                            try:
                                dimensions["length"] = float(prop_value)
                                logger.debug("נמצא אורך %f עבור חדר %s", dimensions["length"],
                                             getattr(space, "Name", "ללא שם"))
                            except (ValueError, TypeError):
                                pass

                        if "Width" in prop_name:
                            try:
                                dimensions["width"] = float(prop_value)
                                logger.debug("נמצא רוחב %f עבור חדר %s", dimensions["width"],
                                             getattr(space, "Name", "ללא שם"))
                            except (ValueError, TypeError):
                                pass

                # ניסיון 2: מתוך כמויות
                if hasattr(space, "IsDefinedBy"):
                    for rel in space.IsDefinedBy:
                        if rel.is_a("IfcRelDefinesByProperties"):
                            qset = rel.RelatingPropertyDefinition
                            if qset.is_a("IfcElementQuantity"):
                                for qty in qset.Quantities:
                                    if qty.is_a("IfcQuantityArea"):
                                        space_area = float(qty.AreaValue)
                                        logger.debug("נמצא שטח %f מתוך IsDefinedBy עבור חדר %s",
                                                     space_area, getattr(space, "Name", "ללא שם"))

                                    if qty.is_a("IfcQuantityLength"):
                                        if "Height" in qty.Name:
                                            dimensions["height"] = float(qty.LengthValue)
                                            logger.debug("נמצא גובה %f מתוך IsDefinedBy", dimensions["height"])
                                        elif "Length" in qty.Name:
                                            dimensions["length"] = float(qty.LengthValue)
                                            logger.debug("נמצא אורך %f מתוך IsDefinedBy", dimensions["length"])
                                        elif "Width" in qty.Name:
                                            dimensions["width"] = float(qty.LengthValue)
                                            logger.debug("נמצא רוחב %f מתוך IsDefinedBy", dimensions["width"])

                # אם מצאנו שטח גדול יותר, נעדכן את החדר הגדול ביותר
                if space_area > largest_area:
                    largest_area = space_area
                    largest_space = space
                    dimensions["area"] = space_area

            # אם מצאנו חדר גדול אבל לא היו לו מידות אורך ורוחב, ננסה לחשב
            if largest_area > 0 and (dimensions["length"] == 5.0 or dimensions["width"] == 4.0):
                # הערכה של אורך ורוחב מתוך שטח, בהנחה של יחס 4:5
                dimensions["length"] = sqrt(largest_area * 5 / 4)
                dimensions["width"] = sqrt(largest_area * 4 / 5)
                logger.debug("חושבו אורך ורוחב מתוך שטח: אורך=%f, רוחב=%f",
                             dimensions["length"], dimensions["width"])

        # שיטה 2: אם לא מצאנו מידות, ננסה לחלץ מקירות
        if dimensions["height"] == 2.5:  # אם עדיין ערך ברירת מחדל
            walls = model.by_type("IfcWall") + model.by_type("IfcWallStandardCase")
            logger.debug("מנסה לחלץ גובה מתוך %d קירות", len(walls))

            max_z = 0
            for wall in walls:
                if hasattr(wall, "IsDefinedBy"):
                    for rel in wall.IsDefinedBy:
                        if rel.is_a("IfcRelDefinesByProperties"):
                            qset = rel.RelatingPropertyDefinition
                            if qset.is_a("IfcElementQuantity"):
                                for qty in qset.Quantities:
                                    if qty.is_a("IfcQuantityLength") and "Height" in qty.Name:
                                        wall_height = float(qty.LengthValue)
                                        if wall_height > max_z:
                                            max_z = wall_height
                                            dimensions["height"] = wall_height
                                            logger.debug("נמצא גובה %f מתוך קיר", dimensions["height"])

        # שיטה 3: חישוב מידות מתוך קואורדינטות קירות
        if dimensions["length"] == 5.0 or dimensions["width"] == 4.0:  # אם עדיין ערכי ברירת מחדל
            walls = model.by_type("IfcWall") + model.by_type("IfcWallStandardCase")
            x_coords = []
            y_coords = []

            for wall in walls:
                try:
                    if hasattr(wall, "ObjectPlacement") and wall.ObjectPlacement:
                        if hasattr(wall.ObjectPlacement,
                                   "RelativePlacement") and wall.ObjectPlacement.RelativePlacement:
                            if hasattr(wall.ObjectPlacement.RelativePlacement,
                                       "Location") and wall.ObjectPlacement.RelativePlacement.Location:
                                coords = wall.ObjectPlacement.RelativePlacement.Location.Coordinates
                                x_coords.append(float(coords[0]))
                                y_coords.append(float(coords[1]))
                except Exception as e:
                    logger.debug("שגיאה בחילוץ קואורדינטות קיר: %s", str(e))

            if x_coords and y_coords:
                min_x, max_x = min(x_coords), max(x_coords)
                min_y, max_y = min(y_coords), max(y_coords)

                width = max_x - min_x
                length = max_y - min_y

                # רק אם המידות הגיוניות נעדכן
                if width > 1.0 and length > 1.0:
                    dimensions["width"] = width
                    dimensions["length"] = length
                    dimensions["area"] = width * length
                    logger.debug("חושבו מידות מתוך קואורדינטות קירות: אורך=%f, רוחב=%f, שטח=%f",
                                 length, width, dimensions["area"])

        logger.debug("מידות סופיות: גובה=%.2f, שטח=%.2f, אורך=%.2f, רוחב=%.2f",
                     dimensions["height"], dimensions["area"], dimensions["length"], dimensions["width"])

    except Exception as e:
        logger.error("שגיאה בחילוץ מידות החדר: %s", str(e))

    return dimensions


def extract_element_data(element, model, category):
    """מחלץ מידע מפורט על אלמנט בודד"""
    # חילוץ מידע בסיסי
    element_name = getattr(element, "Name", None) or ""
    element_type = element.is_a()

    # זיהוי סוג האלמנט העברי
    element_type_mapping = {
        "IfcWall": "קיר",
        "IfcWallStandardCase": "קיר",
        "IfcWindow": "חלון",
        "IfcWindowStandardCase": "חלון",
        "IfcDoor": "דלת",
        "IfcDoorStandardCase": "דלת",
        "IfcSlab": "רצפה/תקרה",
        "IfcFurnishingElement": "ריהוט",
        "IfcFlowTerminal": "אביזר",
        "IfcSpace": "חדר"
    }

    element_type_hebrew = element_type_mapping.get(element_type, element_type)

    # זיהוי סוג האלמנט לפי שם
    element_subtype = ""
    name_lower = element_name.lower() if element_name else ""

    furniture_types = {
        "table": ["table", "שולחן"],
        "desk": ["desk", "שולחן עבודה", "שולחן כתיבה"],
        "chair": ["chair", "כיסא"],
        "sofa": ["sofa", "ספה"],
        "bed": ["bed", "מיטה"],
        "cabinet": ["cabinet", "ארון"],
        "counter": ["counter", "דלפק", "משטח עבודה"]
    }

    for ftype, keywords in furniture_types.items():
        if any(kw in name_lower for kw in keywords):
            element_subtype = ftype
            break

    # נסה לחלץ מיקום ומידות
    location_data = extract_location_and_dimensions(element)

    # חלץ חומרים
    materials_str = extract_materials(element, model)

    # קביעת מאפייני החזרת אור לפי החומר בעזרת ה-ENUM
    material_reflection = MaterialReflection.get_by_material_name(materials_str)

    # קביעת דרישות תאורה לאלמנט
    required_lux = 0
    if element_subtype in ["table", "desk", "counter"]:
        if element_subtype == "desk":
            required_lux = 500  # שולחנות עבודה דורשים יותר תאורה
        else:
            required_lux = 300  # שולחנות רגילים

    # יצירת המילון שיוחזר - רק עם מיקום 3D, אורך, רוחב, גובה, חומר וסוג
    element_data = {
        "ElementType": element_subtype or element_type_hebrew,
        "X": location_data.get("X", 0),
        "Y": location_data.get("Y", 0),
        "Z": location_data.get("Z", 0),
        "Width": location_data.get("Width", 0),
        "Length": location_data.get("Length", 0),
        "Height": location_data.get("Height", 0),
        "Material": materials_str,
        "RequiredLuks": required_lux
    }

    # הוספת מקדם החזרת אור מה-ENUM
    if material_reflection.reflection_factor > 0:
        element_data["ReflectionFactor"] = material_reflection.reflection_factor

    return element_data


def extract_location_and_dimensions(element):
    """מחלץ מיקום ומידות של אלמנט"""
    result = {
        "X": 0, "Y": 0, "Z": 0,
        "Width": 0, "Length": 0, "Height": 0
    }

    # חילוץ מיקום מתוך ObjectPlacement
    try:
        placement = element.ObjectPlacement
        if placement and hasattr(placement, "RelativePlacement"):
            rel_placement = placement.RelativePlacement
            if hasattr(rel_placement, "Location") and rel_placement.Location:
                coords = rel_placement.Location.Coordinates
                result["X"] = float(coords[0])
                result["Y"] = float(coords[1])
                result["Z"] = float(coords[2])
    except Exception as e:
        logger.debug("לא ניתן לחלץ מיקום יחסי: %s", str(e))

    # חילוץ מידות מתוך מאפיינים
    try:
        quantities = {}

        # בדיקה ישירה של קשרים למאפיינים
        if hasattr(element, "IsDefinedBy"):
            for rel in element.IsDefinedBy:
                # חיפוש ב-IfcRelDefinesByProperties
                if rel.is_a("IfcRelDefinesByProperties") and hasattr(rel, "RelatingPropertyDefinition"):
                    prop_def = rel.RelatingPropertyDefinition

                    # בדיקה עבור IfcElementQuantity
                    if prop_def.is_a("IfcElementQuantity") and hasattr(prop_def, "Quantities"):
                        for quantity in prop_def.Quantities:
                            # בדיקת סוגי מידות שונים
                            if quantity.is_a("IfcQuantityLength") and hasattr(quantity, "LengthValue"):
                                if "Length" in quantity.Name or "LENGTH" in quantity.Name.upper():
                                    quantities["Length"] = float(quantity.LengthValue)
                                elif "Width" in quantity.Name or "WIDTH" in quantity.Name.upper():
                                    quantities["Width"] = float(quantity.LengthValue)
                                elif "Height" in quantity.Name or "HEIGHT" in quantity.Name.upper():
                                    quantities["Height"] = float(quantity.LengthValue)
                            elif quantity.is_a("IfcQuantityArea") and hasattr(quantity, "AreaValue"):
                                quantities["Area"] = float(quantity.AreaValue)

        # עדכון התוצאה עם הערכים שנמצאו
        for key in ["Length", "Width", "Height"]:
            if key in quantities and quantities[key] > 0:
                result[key] = quantities[key]

        # אם זה אלמנט קיר וחסרות מידות, הערך אומדנים סבירים
        if element.is_a("IfcWall") or element.is_a("IfcWallStandardCase"):
            if result["Width"] == 0:
                result["Width"] = 0.15  # עובי קיר טיפוסי

            # חישוב אורך הקיר אם לא נמצא
            if result["Length"] == 0 and hasattr(element, "Representation"):
                # תנסה להשתמש בייצוג של הקיר לחישוב אורך
                pass

    except Exception as e:
        logger.debug("שגיאה בחילוץ מידות מתוך מאפיינים: %s", str(e))

    # אם עדיין חסרות מידות, השתמש בערכים ברירת מחדל לפי סוג האלמנט
    if result["Width"] == 0 or result["Length"] == 0 or result["Height"] == 0:
        element_type = element.is_a()

        if "Wall" in element_type:
            if result["Width"] == 0:
                result["Width"] = 0.15  # עובי קיר ממוצע
            if result["Height"] == 0:
                result["Height"] = 2.5  # גובה קיר ממוצע
            if result["Length"] == 0:
                result["Length"] = 3.0  # אורך קיר ממוצע

        elif "Door" in element_type:
            if result["Width"] == 0:
                result["Width"] = 0.9  # רוחב דלת ממוצע
            if result["Height"] == 0:
                result["Height"] = 2.1  # גובה דלת ממוצע
            if result["Length"] == 0:
                result["Length"] = 0.1  # עובי דלת ממוצע

        elif "Window" in element_type:
            if result["Width"] == 0:
                result["Width"] = 1.2  # רוחב חלון ממוצע
            if result["Height"] == 0:
                result["Height"] = 1.0  # גובה חלון ממוצע
            if result["Length"] == 0:
                result["Length"] = 0.05  # עובי חלון ממוצע

        elif "Slab" in element_type:
            if result["Height"] == 0:
                result["Height"] = 0.2  # עובי רצפה/תקרה ממוצע

    return result


def get_element_properties(element):
    """מחלץ את כל המאפיינים של אלמנט"""
    properties = {}

    try:
        # גישה ישירה למאפיינים
        if hasattr(element, "IsDefinedBy"):
            for definition in element.IsDefinedBy:
                if definition.is_a("IfcRelDefinesByProperties"):
                    property_set = definition.RelatingPropertyDefinition
                    if property_set.is_a("IfcPropertySet"):
                        pset_name = property_set.Name
                        properties[pset_name] = {}
                        for prop in property_set.HasProperties:
                            if prop.is_a("IfcPropertySingleValue"):
                                prop_name = prop.Name
                                if hasattr(prop, "NominalValue") and prop.NominalValue:
                                    prop_value = prop.NominalValue.wrappedValue
                                    properties[pset_name][prop_name] = prop_value
    except Exception as e:
        logger.debug("שגיאה בחילוץ מאפיינים: %s", str(e))

    return properties


def extract_materials(element, model):
    """מחלץ מידע על חומרים של אלמנט"""
    materials = []

    try:
        # גישה ישירה לחומרים
        if hasattr(element, "HasAssociations"):
            for association in element.HasAssociations:
                if association.is_a("IfcRelAssociatesMaterial"):
                    material = association.RelatingMaterial
                    if hasattr(material, "Name"):
                        materials.append(material.Name)
                    elif hasattr(material, "ForLayerSet") and material.ForLayerSet:
                        layer_set = material.ForLayerSet
                        if hasattr(layer_set, "MaterialLayers"):
                            for layer in layer_set.MaterialLayers:
                                if hasattr(layer, "Material") and hasattr(layer.Material, "Name"):
                                    materials.append(layer.Material.Name)
    except Exception as e:
        logger.debug("שגיאה בחילוץ חומרים: %s", str(e))

    return ", ".join(materials) if materials else "לא ידוע"


def create_center_point(room_info):
    """יוצר נקודת מרכז לחדר שתשמש כנקודת ייחוס"""
    return {
        "ElementType": "center_point",
        "X": 0,
        "Y": 0,
        "Z": 0,
        "Width": 0,
        "Length": 0,
        "Height": 0,
        "RequiredLuks": 0,
        "Material": ""
    }
