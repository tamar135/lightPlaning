import ifcopenshell
import ifcopenshell.geom
import json
import tempfile
import logging
import os
from math import sqrt
import numpy as np

from RoomType import RoomType
from MaterialReflection import MaterialReflection

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# הגדרות גיאומטריה גלובליות
GEOMETRY_SETTINGS = ifcopenshell.geom.settings()
GEOMETRY_SETTINGS.set(GEOMETRY_SETTINGS.USE_WORLD_COORDS, True)



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
        model = ifcopenshell.open(file_path)
        logger.debug("קובץ IFC נטען בהצלחה. סכמה: %s", model.schema)
    except Exception as e:
        logger.error("שגיאה בטעינת קובץ IFC: %s", str(e))
        raise

    room_info = extract_room_info(model)
    if not room_type:
        room_type = room_info.get("RoomType", RoomType.UNKNOWN.room_name)

    # קביעת עוצמת תאורה מומלצת לפי סוג החדר
    room_type_enum = RoomType.get_by_name(room_type)
    recommended_lux = room_type_enum.recommended_lux
    logger.debug("זוהה חדר מסוג %s עם תאורה מומלצת %d לוקס",
                 room_type, recommended_lux)

    results = [
        {"RecommendedLux": recommended_lux},
        {"RoomType": room_type},
        {"RoomHeight": room_info.get("RoomHeight", 2.5)},
        {"RoomArea": room_info.get("RoomArea", 20.0)}
    ]

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


def extract_geometry_coordinates(element):
    """
    מחלץ קואורדינטות גיאומטריות אמיתיות של אלמנט

    Returns:
        dict: מילון עם X, Y, Z, Width, Length, Height
    """
    result = {
        "X": 0, "Y": 0, "Z": 0,
        "Width": 0, "Length": 0, "Height": 0
    }

    try:
        # יצירת הגיאומטריה באמצעות ifcopenshell.geom
        geom = ifcopenshell.geom.create_shape(GEOMETRY_SETTINGS, element)

        if geom and geom.geometry:
            # חילוץ כל הקודקודים
            verts = geom.geometry.verts

            if len(verts) >= 3:
                # המרה לרשימת נקודות (x, y, z)
                points = [(verts[i], verts[i + 1], verts[i + 2])
                          for i in range(0, len(verts), 3)]

                if points:
                    # חישוב bounding box
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    z_coords = [p[2] for p in points]

                    min_x, max_x = min(x_coords), max(x_coords)
                    min_y, max_y = min(y_coords), max(y_coords)
                    min_z, max_z = min(z_coords), max(z_coords)

                    # עדכון המיקום והמידות
                    result["X"] = min_x
                    result["Y"] = min_y
                    result["Z"] = min_z
                    result["Width"] = max_x - min_x
                    result["Length"] = max_y - min_y
                    result["Height"] = max_z - min_z

                    logger.debug("חולצו קואורדינטות גיאומטריות: X=%.2f, Y=%.2f, Z=%.2f, W=%.2f, L=%.2f, H=%.2f",
                                 result["X"], result["Y"], result["Z"],
                                 result["Width"], result["Length"], result["Height"])

                    return result

    except Exception as e:
        logger.debug("לא ניתן לחלץ גיאומטריה עבור אלמנט %s: %s",
                     getattr(element, 'GlobalId', 'unknown'), str(e))

    # אם נכשל החילוץ הגיאומטרי - נסה שיטות אחרות
    return extract_fallback_location_and_dimensions(element)


def extract_fallback_location_and_dimensions(element):
    """
    שיטה חלופית לחילוץ מיקום ומידות כשהגיאומטריה לא עובדת
    """
    result = {
        "X": 0, "Y": 0, "Z": 0,
        "Width": 0, "Length": 0, "Height": 0
    }

    # ניסיון לחילוץ מיקום מתוך ObjectPlacement
    try:
        placement = element.ObjectPlacement
        if placement and hasattr(placement, "RelativePlacement"):
            rel_placement = placement.RelativePlacement
            if hasattr(rel_placement, "Location") and rel_placement.Location:
                coords = rel_placement.Location.Coordinates
                result["X"] = float(coords[0])
                result["Y"] = float(coords[1])
                result["Z"] = float(coords[2]) if len(coords) > 2 else 0
    except Exception as e:
        logger.debug("לא ניתן לחלץ מיקום יחסי: %s", str(e))

    # ניסיון לחילוץ מידות מתוך מאפיינים
    try:
        quantities = {}

        if hasattr(element, "IsDefinedBy"):
            for rel in element.IsDefinedBy:
                if rel.is_a("IfcRelDefinesByProperties") and hasattr(rel, "RelatingPropertyDefinition"):
                    prop_def = rel.RelatingPropertyDefinition

                    if prop_def.is_a("IfcElementQuantity") and hasattr(prop_def, "Quantities"):
                        for quantity in prop_def.Quantities:
                            if quantity.is_a("IfcQuantityLength") and hasattr(quantity, "LengthValue"):
                                name_upper = quantity.Name.upper()
                                if "LENGTH" in name_upper:
                                    quantities["Length"] = float(quantity.LengthValue)
                                elif "WIDTH" in name_upper:
                                    quantities["Width"] = float(quantity.LengthValue)
                                elif "HEIGHT" in name_upper:
                                    quantities["Height"] = float(quantity.LengthValue)

        # עדכון התוצאה עם הערכים שנמצאו
        for key in ["Length", "Width", "Height"]:
            if key in quantities and quantities[key] > 0:
                result[key] = quantities[key]

    except Exception as e:
        logger.debug("שגיאה בחילוץ מידות מתוך מאפיינים: %s", str(e))

    # ברירות מחדל לפי סוג האלמנט אם עדיין אין מידות
    if result["Width"] == 0 or result["Length"] == 0 or result["Height"] == 0:
        element_type = element.is_a()
        apply_default_dimensions(result, element_type)

    return result


def apply_default_dimensions(result, element_type):
    """מחיל מידות ברירת מחדל לפי סוג האלמנט"""
    defaults = {
        "IfcWall": {"Width": 0.15, "Height": 2.5, "Length": 3.0},
        "IfcWallStandardCase": {"Width": 0.15, "Height": 2.5, "Length": 3.0},
        "IfcDoor": {"Width": 0.9, "Height": 2.1, "Length": 0.1},
        "IfcDoorStandardCase": {"Width": 0.9, "Height": 2.1, "Length": 0.1},
        "IfcWindow": {"Width": 1.2, "Height": 1.0, "Length": 0.05},
        "IfcWindowStandardCase": {"Width": 1.2, "Height": 1.0, "Length": 0.05},
        "IfcSlab": {"Height": 0.2}
    }

    if element_type in defaults:
        for key, value in defaults[element_type].items():
            if result[key] == 0:
                result[key] = value


def extract_room_info(model):
    """מחלץ מידע בסיסי על החדר מתוך המודל"""
    room_info = {
        "RecommendedLux": 300,
        "RoomType": "bedroom",
        "RoomHeight": 2.5,
        "RoomArea": 20.0
    }

    try:
        spaces = model.by_type("IfcSpace")

        if spaces:
            logger.debug("נמצאו %d מרחבים במודל", len(spaces))
            largest_space = spaces[0]
            largest_area = 0

            for space in spaces:
                psets = get_element_properties(space)

                # זיהוי סוג החדר
                space_name = getattr(space, "Name", "").lower() if hasattr(space, "Name") else ""
                space_long_name = getattr(space, "LongName", "").lower() if hasattr(space, "LongName") else ""

                room_types = {
                    "bedroom": ["bedroom", "חדר שינה", "שינה", "bed", "sleeping"],
                    "living": ["living", "סלון", "מגורים", "lounge"],
                    "kitchen": ["kitchen", "מטבח", "cook"],
                    "bathroom": ["bathroom", "שירותים", "אמבטיה", "מקלחת", "bath", "toilet", "shower"],
                    "office": ["office", "משרד", "study", "עבודה"]
                }

                detected_type = room_info["RoomType"]
                for rtype, keywords in room_types.items():
                    if any(kw in space_name for kw in keywords) or any(kw in space_long_name for kw in keywords):
                        detected_type = rtype
                        break

                room_info["RoomType"] = detected_type

                # חילוץ מידות החדר
                try:
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


def extract_element_data(element, model, category):
    """מחלץ מידע מפורט על אלמנט בודד"""
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

    # חילוץ מיקום ומידות באמצעות הגיאומטריה המתוקנת
    location_data = extract_geometry_coordinates(element)

    # חלץ חומרים
    materials_str = extract_materials(element, model)

    # קביעת מאפייני החזרת אור לפי החומר
    material_reflection = MaterialReflection.get_by_material_name(materials_str)

    # קביעת דרישות תאורה לאלמנט
    required_lux = 0
    if element_subtype in ["table", "desk", "counter"]:
        if element_subtype == "desk":
            required_lux = 500
        else:
            required_lux = 300

    # יצירת המילון שיוחזר
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

    # הוספת מקדם החזרת אור
    if material_reflection.reflection_factor > 0:
        element_data["ReflectionFactor"] = material_reflection.reflection_factor

    return element_data


def get_element_properties(element):
    """מחלץ את כל המאפיינים של אלמנט"""
    properties = {}

    try:
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