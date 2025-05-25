# ShadowOptimizer.py
import math
import logging
from typing import List, Tuple
from models import Point3D, LightVertex, ObstanceVertex, Graph

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ShadowOptimizer:
    def __init__(self, graph: Graph):
        self.graph = graph
        self.center_lights = self.get_center_lights()
        self.furniture_lights = self.get_furniture_lights()

    def get_center_lights(self) -> List[LightVertex]:
        """מציאת כל המנורות המרכזיות"""
        center_lights = []
        for vertex in self.graph.vertices:
            if isinstance(vertex, LightVertex):
                # בדיקה בטוחה של light_type
                light_type = getattr(vertex, 'light_type', 'center')
                if light_type == "center":
                    center_lights.append(vertex)

        logger.debug(f"נמצאו {len(center_lights)} מנורות מרכזיות")
        return center_lights

    def get_furniture_lights(self) -> List[LightVertex]:
        """מציאת כל מנורות הריהוט"""
        furniture_lights = []
        for vertex in self.graph.vertices:
            if isinstance(vertex, LightVertex):
                # בדיקה בטוחה של light_type
                light_type = getattr(vertex, 'light_type', 'center')
                if light_type == "furniture":
                    furniture_lights.append(vertex)

        logger.debug(f"נמצאו {len(furniture_lights)} מנורות ריהוט (נשמרות)")
        return furniture_lights

    def optimize_lighting_by_shadow_analysis(self) -> List[LightVertex]:
        """אופטימיזציה של המנורות המרכזיות בלבד - מחזיר רק רשימה"""
        logger.debug("מתחיל אופטימיזציה של מנורות מרכזיות")

        optimized_center_lights = []

        # אופטימיזציה לכל מנורה מרכזית (= חדר)
        for i, center_light in enumerate(self.center_lights):
            logger.debug(f"\n🏠 מאפטם חדר {i + 1} (מנורה מרכזית)")

            # מצא ריהוט בחדר הזה
            room_furniture = self.find_furniture_near_light(center_light, radius=5.0)

            # אופטימיזציה של המנורה המרכזית
            best_lights_for_room = self.optimize_center_light(center_light, room_furniture)
            optimized_center_lights.extend(best_lights_for_room)

            logger.debug(f"   ✅ חדר {i + 1}: {len(best_lights_for_room)} מנורות מרכזיות")

        # **רק מחזיר רשימה - לא נוגע בגרף!**
        all_lights = optimized_center_lights + self.furniture_lights

        logger.debug(f"\n🎯 סיום אופטימיזציה: {len(all_lights)} מנורות כולל ריהוט")
        return all_lights

    def find_furniture_near_light(self, center_light: LightVertex, radius: float) -> List[ObstanceVertex]:
        """מצא ריהוט השייך לחדר של המנורה המרכזית"""
        furniture = []
        for vertex in self.graph.vertices:
            if isinstance(vertex, ObstanceVertex):
                distance = self.calculate_distance(center_light.point, vertex.point)
                if distance <= radius:
                    furniture.append(vertex)

        logger.debug(f"     נמצאו {len(furniture)} פריטי ריהוט ברדיוס {radius}m")
        return furniture

    def optimize_center_light(self, original_light: LightVertex, furniture: List[ObstanceVertex]) -> List[LightVertex]:
        """אופטימיזציה של מנורה מרכזית אחת"""
        center = original_light.point
        ceiling_height = center.z + 0.3

        # 4 תצורות למנורות מרכזיות
        configurations = [
            ("מנורה מרכזית אחת", self.config_single_center(center, ceiling_height)),
            ("2 מנורות מרכזיות", self.config_dual_linear(center, ceiling_height)),
            ("3 מנורות מרכזיות", self.config_triangle(center, ceiling_height)),
            ("4 מנורות מרכזיות", self.config_square(center, ceiling_height))
        ]

        best_lights = None
        best_score = float('inf')
        best_name = ""

        for name, config in configurations:
            lights = config['lights']

            # חישוב צל וקטורי עבור הריהוט בחדר הזה בלבד
            shadow_area = self.calculate_vectorial_shadow_area(lights, furniture)
            aesthetic_score = config['aesthetic_score']

            # ציון משולב: פחות צל = טוב יותר
            total_score = shadow_area * 1.0 + aesthetic_score * 0.3

            logger.debug(f"     {name}: צל={shadow_area:.2f}m², אסתטיקה={aesthetic_score:.2f}, ציון={total_score:.2f}")

            if total_score < best_score:
                best_score = total_score
                best_lights = lights
                best_name = name

        logger.debug(f"   🏆 נבחר: {best_name}")
        return best_lights if best_lights else [original_light]

    def calculate_vectorial_shadow_area(self, lights: List[LightVertex], furniture: List[ObstanceVertex]) -> float:
        """חישוב שטח צל וקטורי אמיתי עבור חדר ספציפי"""
        if not lights or not furniture:
            return 0

        total_shadow_area = 0
        floor_z = 0  # גובה הרצפה

        # עבור כל פריט ריהוט בחדר
        for furniture_vertex in furniture:
            shadow_points = []

            # עבור כל מנורה בחדר - חשב איך היא יוצרת צל של הריהוט הזה
            for light in lights:
                # וקטור מהמנורה לצומת הריהוט
                light_to_furniture = self.create_vector(light.point, furniture_vertex.point)

                # הקרנת הוקטור על הרצפה = נקודת הצל
                shadow_point = self.project_vector_to_floor(light.point, light_to_furniture, floor_z)

                if shadow_point:
                    shadow_points.append((shadow_point.x, shadow_point.y))

            # חישוב שטח הצל של פריט הריהוט הזה
            if len(shadow_points) >= 3:
                furniture_shadow_area = self.calculate_polygon_area(shadow_points)
                total_shadow_area += furniture_shadow_area

        return total_shadow_area

    def create_vector(self, from_point: Point3D, to_point: Point3D) -> Tuple[float, float, float]:
        """יצירת וקטור כיוון מנקודה לנקודה"""
        return (
            to_point.x - from_point.x,
            to_point.y - from_point.y,
            to_point.z - from_point.z
        )

    def project_vector_to_floor(self, light_pos: Point3D, direction: Tuple[float, float, float],
                                floor_z: float) -> Point3D:
        """הקרנת וקטור מהמנורה דרך הריהוט אל הרצפה"""
        dx, dy, dz = direction

        if dz >= 0:  # הוקטור לא מכוון כלפי מטה - אין צל
            return None

        # מציאת נקודת החיתוך עם הרצפה
        # משוואה: light_pos + t * direction = floor_z (בציר Z)
        t = (floor_z - light_pos.z) / dz

        if t < 0:  # הנקודה מאחורי המנורה - לא אמור לקרות
            return None

        # נקודת הצל על הרצפה
        shadow_x = light_pos.x + t * dx
        shadow_y = light_pos.y + t * dy

        return Point3D(shadow_x, shadow_y, floor_z)

    def calculate_polygon_area(self, points: List[Tuple[float, float]]) -> float:
        """חישוב שטח פוליגון בשיטת הנעל (Shoelace formula)"""
        if len(points) < 3:
            return 0

        area = 0
        n = len(points)

        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]

        return abs(area) / 2

    # תצורות תאורה אפשריות לחדר
    def config_single_center(self, center: Point3D, ceiling_height: float):
        """מנורה אחת במרכז החדר"""
        light = LightVertex(
            Point3D(center.x, center.y, ceiling_height - 0.3),
            400, 8000, target_id=None, light_type="center"
        )
        return {
            'lights': [light],
            'aesthetic_score': 1.0  # פשטות = יופי
        }

    def config_dual_linear(self, center: Point3D, ceiling_height: float):
        """2 מנורות בקו"""
        offset = 1.5
        lights = [
            LightVertex(
                Point3D(center.x - offset, center.y, ceiling_height - 0.3),
                250, 4500, target_id=None, light_type="center"
            ),
            LightVertex(
                Point3D(center.x + offset, center.y, ceiling_height - 0.3),
                250, 4500, target_id=None, light_type="center"
            )
        ]
        return {
            'lights': lights,
            'aesthetic_score': 0.8
        }

    def config_triangle(self, center: Point3D, ceiling_height: float):
        """3 מנורות במשולש"""
        radius = 1.2
        angles = [0, 2 * math.pi / 3, 4 * math.pi / 3]

        lights = []
        for angle in angles:
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            lights.append(LightVertex(
                Point3D(x, y, ceiling_height - 0.3),
                200, 3500, target_id=None, light_type="center"
            ))

        return {
            'lights': lights,
            'aesthetic_score': 0.9
        }

    def config_square(self, center: Point3D, ceiling_height: float):
        """4 מנורות בריבוע"""
        offset = 1.0
        positions = [
            (-offset, -offset), (offset, -offset),
            (offset, offset), (-offset, offset)
        ]

        lights = []
        for dx, dy in positions:
            lights.append(LightVertex(
                Point3D(center.x + dx, center.y + dy, ceiling_height - 0.3),
                150, 2800, target_id=None, light_type="center"
            ))

        return {
            'lights': lights,
            'aesthetic_score': 0.95
        }

    def calculate_distance(self, p1: Point3D, p2: Point3D) -> float:
        """חישוב מרחק אוקלידי בין שתי נקודות"""
        return math.sqrt(
            (p1.x - p2.x) ** 2 +
            (p1.y - p2.y) ** 2 +
            (p1.z - p2.z) ** 2
        )