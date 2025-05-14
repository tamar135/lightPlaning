# MaterialReflection.py
from enum import Enum


class MaterialReflection(Enum):
    # [שם חומר, מקדם החזרה]
    MIRROR = ("mirror", 0.9)  # מראה - החזרה גבוהה מאוד
    GLASS = ("glass", 0.8)  # זכוכית - החזרה גבוהה
    METAL = ("metal", 0.7)  # מתכת - החזרה די גבוהה
    GLOSSY_PAINT = ("glossy", 0.6)  # צבע מבריק
    CERAMIC = ("ceramic", 0.5)  # קרמיקה
    WOOD_VARNISHED = ("varnished", 0.4)  # עץ מצופה לכה
    LIGHT_COLOR = ("light", 0.3)  # צבע בהיר
    WOOD = ("wood", 0.2)  # עץ רגיל
    CONCRETE = ("concrete", 0.15)  # בטון
    DARK_COLOR = ("dark", 0.1)  # צבע כהה
    FABRIC = ("fabric", 0.05)  # בד
    BLACK = ("black", 0.03)  # שחור
    NONE = ("unknown", 0.0)  # לא ידוע

    def __init__(self, keyword, reflection_factor):
        self.keyword = keyword
        self.reflection_factor = reflection_factor

    @classmethod
    def get_by_material_name(cls, material_name):
        """מחזיר מקדם החזרה לפי שם החומר"""
        if not material_name:
            return cls.NONE

        material_lower = material_name.lower()

        # מיפוי מילות מפתח לסוגי חומרים
        keyword_mapping = {
            cls.MIRROR: ["mirror", "מראה"],
            cls.GLASS: ["glass", "זכוכית"],
            cls.METAL: ["metal", "מתכת", "steel", "פלדה", "aluminium", "aluminum", "אלומיניום"],
            cls.GLOSSY_PAINT: ["glossy", "מבריק", "gloss"],
            cls.CERAMIC: ["ceramic", "קרמיקה", "tile", "אריח", "porcelain", "פורצלן"],
            cls.WOOD_VARNISHED: ["varnish", "לכה", "polish", "מלוטש"],
            cls.LIGHT_COLOR: ["white", "לבן", "light", "בהיר", "cream", "קרם"],
            cls.WOOD: ["wood", "עץ", "timber", "plywood", "סיבית"],
            cls.CONCRETE: ["concrete", "בטון", "cement", "צמנט"],
            cls.DARK_COLOR: ["dark", "כהה", "grey", "gray", "אפור"],
            cls.FABRIC: ["fabric", "בד", "textile", "טקסטיל", "cloth", "cotton", "כותנה"],
            cls.BLACK: ["black", "שחור"]
        }

        # בדיקה לפי מיפוי המילות מפתח
        for material_type, keywords in keyword_mapping.items():
            if any(keyword in material_lower for keyword in keywords):
                return material_type

        # ברירת מחדל - חומר לא ידוע
        return cls.NONE