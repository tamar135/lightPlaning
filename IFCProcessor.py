import ifcopenshell
import ifcopenshell.geom
import json
import tempfile
import logging
import os


from RoomType import RoomType
from MaterialReflection import MaterialReflection

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# הגדרות גיאומטריה גלובליות
GEOMETRY_SETTINGS = ifcopenshell.geom.settings()
GEOMETRY_SETTINGS.set(GEOMETRY_SETTINGS.USE_WORLD_COORDS, True)

#הגדרות קטגוריות אלמנטים
ELEMENT_CATEGORIES = {
    "walls": ["IfcWall", "IfcWallStandardCase"],
    "windows": ["IfcWindow", "IfcWindowStandardCase"],
    "doors": ["IfcDoor", "IfcDoorStandardCase"],
    "slabs": ["IfcSlab"],
    "furniture": ["IfcFurnishingElement"],
    "fixtures": ["IfcFlowTerminal"]
}



def process_ifc_file(file_path: str, room_type: str) -> str:
    """
    מעבד קובץ IFC ומייצר קובץ JSON עם כל המידע הרלוונטי
    """
    logger.debug("מעבד קובץ IFC: %s", file_path)

    try:
        model = ifcopenshell.open(file_path)
        logger.debug("קובץ IFC נטען בהצלחה. סכמה: %s", model.schema)
    except Exception as e:
        logger.error("שגיאה בטעינת קובץ IFC: %s", str(e))
        raise

    # חילוץ מידע בסיסי על החדר
    room_info = extract_room_info(model, room_type)

    # חילוץ אלמנטים
    elements_data = extract_all_elements(model)

    # בניית המבנה הסופי
    results = [
        {"RecommendedLux": room_info["RecommendedLux"]},
        {"RoomType": room_info["RoomType"]},
        {"RoomHeight": room_info["RoomHeight"]},
        {"RoomArea": room_info["RoomArea"]}
    ]

    # הוספת האלמנטים
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


def extract_room_info(model, room_type) -> dict:
    """חילוץ מידע על חדר """
    room_info = {
        "RecommendedLux": None,
        "RoomType": room_type or "unknown",
        "RoomHeight": None,
        "RoomArea": None
    }
    try:
        # חילוץ מידע מ-IfcSpace
        spaces = model.by_type("IfcSpace")

        if spaces:
            logger.debug("נמצאו %d מרחבים, לוקח את הראשון", len(spaces))
            main_space = spaces[0]

            # חילוץ מידות מהמרחב
            space_geometry = extract_space_geometry(main_space)
            room_info["RoomHeight"] = space_geometry.get("Height", 2.5)
            room_info["RoomArea"] = space_geometry.get("Area", 20.0)

        #  נסיון לחשב מהקירות
        else:
            logger.debug("לא נמצאו מרחבים, מחשב מידות מקירות")
            room_bounds = calculate_room_bounds_from_walls(model)
            if room_bounds:
                room_info["RoomArea"] = ((room_bounds['max_x'] - room_bounds['min_x']) *
                                         (room_bounds['max_y'] - room_bounds['min_y']))

    except Exception as e:
        logger.warning("שגיאה בחילוץ מידע")

    # קביעת לוקס מומלץ לפי סוג החדר
    room_type_enum = RoomType.get_by_name(room_info["RoomType"])
    room_info["RecommendedLux"] = room_type_enum.recommended_lux

    logger.debug("מידע חדר סופי", room_info)
    return room_info


def calculate_room_bounds_from_walls(model) -> dict:
    """חישוב גבולות החדר מהקירות"""
    try:
        walls = model.by_type("IfcWall") + model.by_type("IfcWallStandardCase")

        if not walls:
            return None

        all_x_coords = []
        all_y_coords = []

        for wall in walls:
            wall_geometry = extract_geometry_coordinates(wall)
            x = wall_geometry.get("X", 0)
            y = wall_geometry.get("Y", 0)
            width = wall_geometry.get("Width", 0)
            length = wall_geometry.get("Length", 0)

            all_x_coords.extend([x, x + width])
            all_y_coords.extend([y, y + length])

        if all_x_coords and all_y_coords:
            return {
                'min_x': min(all_x_coords),
                'max_x': max(all_x_coords),
                'min_y': min(all_y_coords),
                'max_y': max(all_y_coords)
            }

    except Exception as e:
        logger.debug("שגיאה בחישוב גבולות מקירות: %s", str(e))

    return None


def extract_all_elements(model) -> list:
    """חילוץ כל האלמנטים בחדר"""
    elements_data = []

    for category, ifc_types in ELEMENT_CATEGORIES.items():
        for ifc_type in ifc_types:
            try:
                elements = model.by_type(ifc_type)
                logger.debug(f"מעבד {len(elements)} אלמנטים מסוג {ifc_type}")

                for element in elements:
                    try:
                        element_data = extract_element_data(element, model, category)
                        if element_data:
                            elements_data.append(element_data)
                    except Exception as e:
                        logger.warning(f"שגיאה בחילוץ אלמנט: {str(e)}")

            except Exception as e:
                logger.warning(f"שגיאה בטעינת אלמנטים מסוג {ifc_type}: {str(e)}")

    logger.debug(f"חולצו בסך הכל {len(elements_data)} אלמנטים")
    return elements_data


def extract_space_geometry(space):
    """חילוץ גיאומטריה של חדר (IfcSpace) """
    location_data = {}

    try:
        # חילוץ גיאומטריה
        geom = ifcopenshell.geom.create_shape(GEOMETRY_SETTINGS, space)

        if geom and geom.geometry:
            verts = geom.geometry.verts
            if len(verts) >= 3:
                points = [(verts[i], verts[i + 1], verts[i + 2])
                          for i in range(0, len(verts), 3)]

                if points:
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    z_coords = [p[2] for p in points]

                    location_data["CenterX"] = (min(x_coords) + max(x_coords)) / 2
                    location_data["CenterY"] = (min(y_coords) + max(y_coords)) / 2
                    location_data["Height"] = max(z_coords) - min(z_coords)
                    location_data["Area"] = (max(x_coords) - min(x_coords)) * (max(y_coords) - min(y_coords))

                    return location_data

    except Exception as e:
        logger.debug(f"לא ניתן לחלץ גיאומטריה לחדר: {str(e)}")

    # חילוץ מתכונות
    try:
        psets = get_element_properties(space)
        for prop_set_name, props in psets.items():
            if "Area" in props:
                location_data["Area"] = float(props["Area"])
            if "Height" in props:
                location_data["Height"] = float(props["Height"])
    except Exception as e:
        logger.debug(f"לא ניתן לחלץ תכונות חדר: {str(e)}")

    return location_data if location_data else None


def extract_geometry_coordinates(element):
    """
    מחלץ קואורדינטות גיאומטריות אמיתיות של אלמנט
    """
    try:
        geom = ifcopenshell.geom.create_shape(GEOMETRY_SETTINGS, element)

        if geom and geom.geometry:
            verts = geom.geometry.verts

            if len(verts) >= 3:
                points = [(verts[i], verts[i + 1], verts[i + 2])
                          for i in range(0, len(verts), 3)]

                if points:
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    z_coords = [p[2] for p in points]

                    min_x, max_x = min(x_coords), max(x_coords)
                    min_y, max_y = min(y_coords), max(y_coords)
                    min_z, max_z = min(z_coords), max(z_coords)

                    return {
                        "X": min_x,
                        "Y": min_y,
                        "Z": min_z,
                        "Width": max_x - min_x,
                        "Length": max_y - min_y,
                        "Height": max_z - min_z
                    }

    except Exception as e:
        logger.debug("לא ניתן לחלץ גיאומטריה עבור אלמנט %s: %s",
                     getattr(element, 'GlobalId', 'unknown'), str(e))

    fallback = extract_fallback_location_and_dimensions(element)
    if fallback:
        return fallback
    return None


def extract_fallback_location_and_dimensions(element):
    """שיטה חלופית לחילוץ מיקום ומידות"""
    result = {}

    # ניסיון לחילוץ מיקום מתוך ObjectPlacement
    try:
        placement = element.ObjectPlacement
        if placement and hasattr(placement, "RelativePlacement"):
            rel_placement = placement.RelativePlacement
            if hasattr(rel_placement, "Location") and rel_placement.Location:
                coords = rel_placement.Location.Coordinates
                result["X"] = float(coords[0])
                result["Y"] = float(coords[1])
                if len(coords) > 2:
                    result["Z"] = float(coords[2])
    except Exception as e:
        logger.debug("לא ניתן לחלץ מיקום יחסי: %s", str(e))

    # ניסיון לחילוץ מידות מתוך מאפיינים
    try:
        if hasattr(element, "IsDefinedBy"):
            for rel in element.IsDefinedBy:
                if rel.is_a("IfcRelDefinesByProperties") and hasattr(rel, "RelatingPropertyDefinition"):
                    prop_def = rel.RelatingPropertyDefinition
                    if prop_def.is_a("IfcElementQuantity") and hasattr(prop_def, "Quantities"):
                        for quantity in prop_def.Quantities:
                            if quantity.is_a("IfcQuantityLength") and hasattr(quantity, "LengthValue"):
                                name_upper = quantity.Name.upper()
                                value = float(quantity.LengthValue)
                                if "LENGTH" in name_upper:
                                    result["Length"] = value
                                elif "WIDTH" in name_upper:
                                    result["Width"] = value
                                elif "HEIGHT" in name_upper:
                                    result["Height"] = value
    except Exception as e:
        logger.debug("שגיאה בחילוץ מידות מתוך מאפיינים: %s", str(e))

    if not result:
        return None

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


def extract_element_data(element, model, category):
    """מחלץ מידע מפורט על אלמנט"""

    element_name = getattr(element, "Name", "") or ""
    element_type = element.is_a()

    element_subtype = ""

    # חילוץ מיקום ומידות באמצעות הגיאומטריה
    location_data = extract_geometry_coordinates(element)
    if not location_data:
        return None

    # חילוץ חומרים
    materials_str = extract_materials(element, model)

    # מאפייני החזרת אור לפי החומר
    material_reflection = MaterialReflection.get_by_material_name(materials_str)

    element_data = {
        "ElementType": element_type,
        "Name": element_name,
        "X": location_data.get("X"),
        "Y": location_data.get("Y"),
        "Z": location_data.get("Z"),
        "Width": location_data.get("Width"),
        "Length": location_data.get("Length"),
        "Height": location_data.get("Height"),
        "Material": materials_str
    }

    if material_reflection and material_reflection.reflection_factor > 0:
        element_data["ReflectionFactor"] = material_reflection.reflection_factor

    return element_data


def get_element_properties(element):
    """מחלץ מאפיינים של אלמנט"""
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

    return ", ".join(materials) if materials else "unknown"