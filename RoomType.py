from enum import Enum


class RoomType(Enum):
    BEDROOM = ("bedroom", 200)
    LIVING = ("living", 300)
    KITCHEN = ("kitchen", 500)
    BATHROOM = ("bathroom", 300)
    OFFICE = ("office", 500)
    HALLWAY = ("hallway", 150)
    DINING = ("dining", 300)
    UNKNOWN = ("unknown", 300)

    def __init__(self, name, recommended_lux):
        self.room_name = name
        self.recommended_lux = recommended_lux

    @classmethod
    def get_by_name(cls, name):
        """מחזיר סוג חדר לפי שם"""
        name_lower = name.lower() if name else ""
        for room_type in cls:
            if room_type.room_name in name_lower:
                return room_type
        return cls.UNKNOWN

    @classmethod
    def get_by_keywords(cls, keywords):
        """מחזיר סוג חדר לפי מילות מפתח"""
        keywords_lower = keywords.lower() if keywords else ""

        # מיפוי מילות מפתח לסוגי חדרים
        keywords_mapping = {
            cls.BEDROOM: ["bedroom", "חדר שינה", "שינה", "bed", "sleeping"],
            cls.LIVING: ["living", "סלון", "מגורים", "lounge", "family"],
            cls.KITCHEN: ["kitchen", "מטבח", "cook", "cooking"],
            cls.BATHROOM: ["bathroom", "שירותים", "אמבטיה", "מקלחת", "bath", "toilet", "shower", "wc"],
            cls.OFFICE: ["office", "משרד", "study", "עבודה", "work"],
            cls.HALLWAY: ["hallway", "מסדרון", "פרוזדור", "מעבר", "corridor", "passage"],
            cls.DINING: ["dining", "אוכל", "פינת אוכל", "dining room"]
        }

        for room_type, keyword_list in keywords_mapping.items():
            if any(kw in keywords_lower for kw in keyword_list):
                return room_type

        return cls.UNKNOWN