# ShadowOptimizer.py - גרסה מתוקנת עם חישוב צללים וקטוריאלי מדויק
import math
import logging
from typing import List, Tuple, Dict
from models import Point3D, LightVertex, ObstanceVertex, Graph
from MaterialReflection import MaterialReflection
from RoomType import RoomType

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ShadowOptimizer:
    def __init__(self, graph: Graph, required_lux: float = 300):
        self.graph = graph
        self.required_lux = required_lux
        self.center_lights = self.get_center_lights()
        self.furniture_lights = self.get_furniture_lights()
        self.obstacles = self.get_obstacles()
        self.reflection_surfaces = self.get_reflection_surfaces()

        # פרמטרי פיזיקה מדויקים
        self.light_efficiency = 80  # לומן לוואט עבור LED
        self.cos_angle_threshold = 0.1
        self.min_distance = 0.1  # מרחק מינימלי למניעת חלוקה באפס
        self.floor_height = 0.0  # גובה הרצפה

        # מקדמי שבירה לחוק סנל
        self.refractive_indices = {
            'air': 1.0,
            'glass': 1.52,
            'water': 1.33,
            'plastic': 1.4,
            'default': 1.0
        }

        # חישוב תאורה לכל הצמתים מראש
        self.calculate_accurate_illumination_for_all_vertices()

    def calculate_accurate_illumination_for_all_vertices(self):
        """🔬 חישוב מדויק של תאורה לכל צומת בגרף"""
        logger.debug("🔬 מחשב תאורה מדויקת לכל צומת")

        for vertex in self.graph.vertices:
            if isinstance(vertex, ObstanceVertex):
                # חישוב עוצמת תאורה פיזיקלית בפועל
                vertex.actual_lux = self.calculate_physics_based_lux_for_vertex(vertex)

                # קביעת עוצמה נדרשת לפי סוג האלמנט
                vertex.required_lux = self.get_required_lux_by_element_type(vertex)

                # עדכון מקדם החזרה לפי החומר האמיתי מה-enum
                self.update_material_reflection_factor(vertex)

                logger.debug(f"צומת ({vertex.point.x:.1f},{vertex.point.y:.1f}): "
                             f"בפועל={vertex.actual_lux:.1f}, נדרש={vertex.required_lux:.1f}")

    def calculate_physics_based_lux_for_vertex(self, vertex: ObstanceVertex) -> float:
        """💡 חישוב עוצמת תאורה פיזיקלית מדויקת לצומת"""
        total_lux = 0

        # אור ישיר מכל מנורה
        for light in self.center_lights + self.furniture_lights:
            direct_lux = self.calculate_direct_illumination(light, vertex.point)
            total_lux += direct_lux

        # אור מוחזר ממשטחים
        for light in self.center_lights + self.furniture_lights:
            reflected_lux = self.calculate_reflected_illumination(light, vertex.point)
            total_lux += reflected_lux

        return total_lux

    def get_required_lux_by_element_type(self, vertex: ObstanceVertex) -> float:
        """📋 קביעת עוצמת תאורה נדרשת לפי סוג האלמנט"""
        element_type = getattr(vertex, 'element_type', '').lower()

        if 'desk' in element_type or 'workbench' in element_type:
            return 500  # שולחן עבודה
        elif 'counter' in element_type:
            return 400  # דלפק
        elif 'table' in element_type:
            return 300  # שולחן רגיל
        elif 'sofa' in element_type or 'chair' in element_type:
            return 200  # ישיבה
        else:
            return self.required_lux  # ברירת מחדל

    def update_material_reflection_factor(self, vertex: ObstanceVertex):
        """🧱 עדכון מקדם החזרה לפי החומר האמיתי מה-enum"""
        material_name = getattr(vertex, 'material', 'unknown')
        material_reflection = MaterialReflection.get_by_material_name(material_name)
        vertex.reflection_factor = material_reflection.reflection_factor

        logger.debug(f"חומר '{material_name}' -> מקדם החזרה: {vertex.reflection_factor}")

    def optimize_lighting_room(self) -> List[LightVertex]:
        """🏠 אופטימיזציה מדויקת לחדר לפי חוקי הפיזיקה - ללא שינוי!"""
        logger.debug("🔬 מתחיל אופטימיזציה מבוססת פיזיקה לחדר")

        # קבלת מנורות מרכזיות קיימות
        center_lights = self.get_center_lights()
        if not center_lights:
            logger.warning("לא נמצאו מנורות מרכזיות קיימות")
            return []

        current_center = center_lights[0]
        furniture_obstacles = self.get_furniture_obstacles()

        # חילוץ מידע החדר מהגרף
        room_area, ceiling_height = self.extract_room_info_from_graph()

        # 4 תצורות מנורות שונות - עם מיקום בטוח
        configurations = [
            ("2 מנורות", self.config_dual_safe(current_center.point, ceiling_height, room_area, furniture_obstacles)),
            ("משולש 3 מנורות",
             self.config_triangle_safe(current_center.point, ceiling_height, room_area, furniture_obstacles)),
            ("ריבוע 4 מנורות",
             self.config_square_safe(current_center.point, ceiling_height, room_area, furniture_obstacles))
        ]

        best_lights = None
        best_score = float('inf')
        best_name = ""

        for name, config in configurations:
            lights = config['lights']

            # חישוב ציון צללים וקטוריאלי חדש
            shadow_score = self.calculate_vectorial_shadow_area_score(lights, furniture_obstacles)

            # חישוב ציון תאורה פיזיקלי מדויק - כל הצמתים
            illumination_score = self.calculate_physics_illumination_score_all_vertices(lights)
            aesthetic_score = config['aesthetic_score']

            # 60% תאורה פיזיקלית, 25% צללים, 15% אסתטיקה
            total_score = illumination_score * 0.6 + shadow_score * 0.25 + aesthetic_score * 0.15

            logger.debug(f"  {name}: תאורה={illumination_score:.2f}, צללים={shadow_score:.2f}, "
                         f"אסתטיקה={aesthetic_score:.2f} סה\"כ={total_score:.2f}")

            if total_score < best_score:
                best_score = total_score
                best_lights = lights
                best_name = name

        logger.debug(f"🏆 נבחר: {best_name} עם ציון {best_score:.2f}")

        # הוספת מנורות ריהוט + מנורות מרכזיות המאופטמות
        furniture_lights = self.get_furniture_lights()
        result = best_lights + furniture_lights
        return result

    def is_position_above_furniture(self, light_position: Point3D, furniture: ObstanceVertex) -> bool:
        """🪑 בדיקה אם מיקום המנורה מעל הרהיט (לפי כל הצמתים)"""
        # חילוץ מידות הרהיט
        furniture_vertices = self.get_furniture_vertices(furniture)

        if not furniture_vertices:
            # fallback - בדיקה פשוטה
            distance_2d = self.calculate_distance_2d(light_position, furniture.point)
            return distance_2d < 0.8

        # חישוב bounding box של הרהיט
        min_x = min(v.x for v in furniture_vertices)
        max_x = max(v.x for v in furniture_vertices)
        min_y = min(v.y for v in furniture_vertices)
        max_y = max(v.y for v in furniture_vertices)
        max_z = max(v.z for v in furniture_vertices)

        # בדיקה אם המנורה מעל הרהיט במישור XY
        is_above_x = min_x - 0.5 <= light_position.x <= max_x + 0.5  # מרווח בטחון
        is_above_y = min_y - 0.5 <= light_position.y <= max_y + 0.5  # מרווח בטחון
        is_above_z = light_position.z > max_z  # המנורה מעל הרהיט

        if is_above_x and is_above_y and is_above_z:
            logger.debug(f"מנורה ב-({light_position.x:.1f}, {light_position.y:.1f}) מעל רהיט!")
            return True

        return False

    def calculate_distance_2d(self, p1: Point3D, p2: Point3D) -> float:
        """📏 חישוב מרחק דו-ממדי (XY)"""
        return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)

    def calculate_vectorial_shadow_area_score(self, lights: List[LightVertex],
                                              furniture_obstacles: List[ObstanceVertex]) -> float:
        """🌚 חישוב ציון צללים וקטוריאלי - שטח צל לכל רהיט"""
        if not furniture_obstacles:
            return 0.0

        total_shadow_area = 0.0

        for furniture in furniture_obstacles:
            # חישוב שטח צל עבור רהיט זה מכל המנורות
            furniture_shadow_area = self.calculate_furniture_shadow_area(furniture, lights)
            total_shadow_area += furniture_shadow_area

            logger.debug(
                f"רהיט ב-({furniture.point.x:.1f}, {furniture.point.y:.1f}): שטח צל={furniture_shadow_area:.2f}")

        # ציון צללים יחסי לגודל החדר
        room_area = self.extract_room_info_from_graph()[0]
        shadow_ratio = total_shadow_area / max(room_area, 1.0)

        logger.debug(f"שטח צל כולל: {total_shadow_area:.2f}, יחס לחדר: {shadow_ratio:.3f}")
        return min(shadow_ratio * 10, 10.0)  # נרמול וחסימה

    def calculate_furniture_shadow_area(self, furniture: ObstanceVertex, lights: List[LightVertex]) -> float:
        """🪑 חישוב שטח צל של רהיט מכל המנורות"""
        shadow_points_on_floor = []

        # לכל מנורה, חשב וקטורים ונקודות צל
        for light in lights:
            furniture_shadow_points = self.calculate_shadow_vectors_for_furniture(light, furniture)
            shadow_points_on_floor.extend(furniture_shadow_points)

        # חישוב שטח מהנקודות
        if len(shadow_points_on_floor) >= 3:
            return self.calculate_polygon_area(shadow_points_on_floor)
        else:
            return 0.0

    def calculate_shadow_vectors_for_furniture(self, light: LightVertex, furniture: ObstanceVertex) -> List[Point3D]:
        """📐 חישוב וקטורי צל עבור רהיט - מנורה → רהיט → רצפה"""
        shadow_points = []

        # שלב 1: וקטור מהמנורה לצמתי הרהיט (חוק הריבוע ההפוך)
        furniture_vertices = self.get_furniture_vertices(furniture)

        for vertex in furniture_vertices:
            # וקטור מהמנורה לצומת הרהיט
            light_to_furniture_vector = self.calculate_light_vector(light, vertex)

            if light_to_furniture_vector is None:
                continue

            # שלב 2: וקטור מצומת הרהיט לרצפה (למברט + סנל)
            floor_point = self.calculate_shadow_on_floor(vertex, light_to_furniture_vector)

            if floor_point:
                shadow_points.append(floor_point)

        return shadow_points

    def calculate_light_vector(self, light: LightVertex, furniture_vertex: Point3D) -> Tuple[float, float, float]:
        """💡 חישוב וקטור אור עם חוק הריבוע ההפוך"""
        # וקטור כיוון
        dx = furniture_vertex.x - light.point.x
        dy = furniture_vertex.y - light.point.y
        dz = furniture_vertex.z - light.point.z

        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        if distance < self.min_distance:
            return None

        # נרמול הוקטור
        norm_dx = dx / distance
        norm_dy = dy / distance
        norm_dz = dz / distance

        # עוצמת האור לפי חוק הריבוע ההפוך
        light_intensity = light.lumens / (4 * math.pi * distance * distance)

        # בדיקת חסימה
        if self.is_light_blocked(light.point, furniture_vertex):
            light_intensity *= 0.1  # אור חלש דרך חסימה

        return (norm_dx * light_intensity, norm_dy * light_intensity, norm_dz * light_intensity)

    def calculate_shadow_on_floor(self, furniture_vertex: Point3D, light_vector: Tuple[float, float, float]) -> Point3D:
        """🌊 חישוב נקודת צל על הרצפה (למברט + סנל)"""
        vx, vy, vz = light_vector

        if abs(vz) < 0.001:  # וקטור אופקי - לא יוצר צל על הרצפה
            return None

        # חישוב הזמן עד הפגיעה ברצפה
        t = (self.floor_height - furniture_vertex.z) / vz

        if t <= 0:  # הוקטור לא פונה לרצפה
            return None

        # נקודת הפגיעה ברצפה
        floor_x = furniture_vertex.x + vx * t
        floor_y = furniture_vertex.y + vy * t

        # יישום חוק למברט - השפעת זווית
        cos_angle = abs(vz) / math.sqrt(vx * vx + vy * vy + vz * vz)
        lambert_factor = max(0.1, cos_angle)  # מינימום 10%

        # יישום חוק סנל אם יש חומרים שקופים
        transmission_factor = self.calculate_transmission_to_floor(furniture_vertex,
                                                                   Point3D(floor_x, floor_y, self.floor_height))

        # אם האור נחסם מדי, אין צל משמעותי
        if lambert_factor * transmission_factor < 0.05:
            return None

        return Point3D(floor_x, floor_y, self.floor_height)

    def calculate_transmission_to_floor(self, start: Point3D, end: Point3D) -> float:
        """🔬 חישוב העברת אור לרצפה דרך חומרים"""
        # בדיקה פשוטה - אם יש מכשולים בדרך
        for obstacle in self.obstacles:
            if self.line_intersects_obstacle(start, end, obstacle):
                material_name = getattr(obstacle, 'material', 'default').lower()

                # אם זה חומר שקוף, חשב העברה
                if any(mat in material_name for mat in ['glass', 'זכוכית', 'window']):
                    return 0.7  # 70% העברה דרך זכוכית
                else:
                    return 0.1  # 10% העברה דרך חומרים אטומים

        return 1.0  # אין מכשולים

    def get_furniture_vertices(self, furniture: ObstanceVertex) -> List[Point3D]:
        """🪑 קבלת צמתי הרהיט"""
        # ניסיון לחלץ מידות מהאובייקט
        width = getattr(furniture, 'width', 1.0)
        length = getattr(furniture, 'length', 1.0)
        height = getattr(furniture, 'height', 0.8)

        base = furniture.point

        # 8 צמתים של הקובייה
        vertices = [
            Point3D(base.x, base.y, base.z),
            Point3D(base.x + width, base.y, base.z),
            Point3D(base.x, base.y + length, base.z),
            Point3D(base.x + width, base.y + length, base.z),
            Point3D(base.x, base.y, base.z + height),
            Point3D(base.x + width, base.y, base.z + height),
            Point3D(base.x, base.y + length, base.z + height),
            Point3D(base.x + width, base.y + length, base.z + height),
        ]

        return vertices

    def calculate_polygon_area(self, points: List[Point3D]) -> float:
        """📐 חישוב שטח מצולע מנקודות"""
        if len(points) < 3:
            return 0.0

        # שטח מצולע פשוט ב-2D (משולש חיצוני)
        n = len(points)
        area = 0.0

        for i in range(n):
            j = (i + 1) % n
            area += points[i].x * points[j].y
            area -= points[j].x * points[i].y

        return abs(area) / 2.0

    def calculate_physics_illumination_score_all_vertices(self, lights: List[LightVertex]) -> float:
        """🔬 ציון פיזיקלי מבוסס על כל הצמתים בגרף"""
        total_error = 0.0
        point_count = 0

        # בדיקת כל הצמתים במקום רק furniture
        for vertex in self.graph.vertices:
            if isinstance(vertex, ObstanceVertex):
                # עוצמת תאורה בפועל (מחושבת מחדש עם המנורות החדשות)
                actual_lux = self.calculate_total_illumination_at_point(vertex.point, lights)

                # תאורה נדרשת
                required_lux = getattr(vertex, 'required_lux', self.required_lux)

                # חישוב שגיאה
                if actual_lux < required_lux:
                    error = ((required_lux - actual_lux) / required_lux) ** 2
                elif actual_lux > required_lux * 1.5:  # תאורה מוגזמת
                    error = ((actual_lux - required_lux * 1.5) / required_lux) * 0.5
                else:
                    error = 0.0

                total_error += error
                point_count += 1

        return total_error / max(point_count, 1)

    def extract_room_info_from_graph(self) -> Tuple[float, float]:
        """🏠 חילוץ מידע החדר מהגרף"""
        # חישוב שטח החדר לפי הצמתים
        all_x = [v.point.x for v in self.graph.vertices]
        all_y = [v.point.y for v in self.graph.vertices]
        all_z = [v.point.z for v in self.graph.vertices]

        if all_x and all_y:
            room_width = max(all_x) - min(all_x)
            room_length = max(all_y) - min(all_y)
            room_area = max(room_width * room_length, 10.0)  # מינימום 10 מ"ר
        else:
            room_area = 20.0

        if all_z:
            ceiling_height = max(all_z)
            ceiling_height = max(ceiling_height, 2.5)  # מינימום 2.5 מטר
        else:
            ceiling_height = 2.5

        logger.debug(f"מידע חדר: שטח={room_area:.1f}מ\"ר, גובה={ceiling_height:.1f}מ")
        return room_area, ceiling_height

    def calculate_total_illumination_at_point(self, point: Point3D, lights: List[LightVertex]) -> float:
        """💡 חישוב תאורה כוללת בנקודה (ישיר + מוחזר)"""
        total_lux = 0.0

        for light in lights:
            # אור ישיר (חוק הריבוע ההפוך)
            direct_lux = self.calculate_direct_illumination(light, point)

            # אור מוחזר (חוק למברט עם MaterialReflection)
            reflected_lux = self.calculate_reflected_illumination(light, point)

            total_lux += direct_lux + reflected_lux

        return total_lux

    def calculate_direct_illumination(self, light: LightVertex, point: Point3D) -> float:
        """⚡ חישוב אור ישיר לפי חוק הריבוע ההפוך"""
        distance = self.calculate_distance(light.point, point)
        distance = max(distance, self.min_distance)

        # בדיקת חסימה והשפעת חומרים שקופים (חוק סנל)
        transmission_factor = self.calculate_transmission_through_materials(light.point, point)
        if transmission_factor == 0:
            return 0.0

        # חוק הריבוע ההפוך: I = P / (4πr²)
        luminous_intensity = light.lumens / (4 * math.pi)

        # זווית פגיעה (חוק למברט לקליטה)
        cos_angle = self.calculate_cos_incident_angle(light.point, point)
        if cos_angle < self.cos_angle_threshold:
            return 0.0

        # דעיכת אור באוויר
        air_attenuation = self.calculate_air_attenuation(distance)

        # חישוב סופי
        direct_lux = (luminous_intensity * cos_angle * transmission_factor * air_attenuation) / (distance ** 2)
        return max(0.0, direct_lux)

    def calculate_reflected_illumination(self, light: LightVertex, point: Point3D) -> float:
        """🪞 חישוב אור מוחזר ממשטחים (חוק למברט עם MaterialReflection)"""
        total_reflected = 0.0

        for surface in self.reflection_surfaces:
            # מרחקים
            light_to_surface = self.calculate_distance(light.point, surface.point)
            surface_to_point = self.calculate_distance(surface.point, point)

            light_to_surface = max(light_to_surface, self.min_distance)
            surface_to_point = max(surface_to_point, self.min_distance)

            # בדיקת חסימות
            if (self.is_light_blocked(light.point, surface.point) or
                    self.is_light_blocked(surface.point, point)):
                continue

            # עוצמת אור פוגעת במשטח
            incident_intensity = light.lumens / (4 * math.pi * light_to_surface ** 2)

            # זוויות למברט
            cos_incident = self.calculate_cos_incident_angle(light.point, surface.point)
            cos_reflection = self.calculate_cos_incident_angle(surface.point, point)

            if cos_incident > 0 and cos_reflection > 0:
                # מקדם החזרה מ-MaterialReflection enum
                material_name = getattr(surface, 'material', 'unknown')
                material_reflection = MaterialReflection.get_by_material_name(material_name)
                reflection_factor = material_reflection.reflection_factor

                # נוסחת למברט המלאה
                reflected_intensity = (incident_intensity * cos_incident * cos_reflection *
                                       reflection_factor) / (math.pi * surface_to_point ** 2)

                total_reflected += reflected_intensity

        return total_reflected

    def calculate_transmission_through_materials(self, light_pos: Point3D, target_pos: Point3D) -> float:
        """🔬 חישוב העברת אור דרך חומרים שקופים (חוק סנל)"""
        total_transmission = 1.0

        # בדיקה של כל מכשול בדרך
        for obstacle in self.obstacles:
            if self.line_intersects_transparent_obstacle(light_pos, target_pos, obstacle):
                material_name = getattr(obstacle, 'material', 'default').lower()

                # קבלת מקדם שבירה
                n1 = self.refractive_indices['air']
                n2 = self.get_refractive_index(material_name)

                # חישוב זווית פגיעה וזווית שבירה (חוק סנל)
                incident_angle = self.calculate_incident_angle_to_surface(light_pos, target_pos, obstacle.point)
                refracted_angle = self.calculate_snells_refraction(incident_angle, n1, n2)

                if refracted_angle is None:  # השתקפות מלאה
                    return 0.0

                # חישוב מקדם העברה לפי זוויות פרנל
                transmission_coefficient = self.calculate_fresnel_transmission(incident_angle, refracted_angle, n1, n2)

                # דעיכה בחומר (Beer-Lambert)
                material_thickness = self.calculate_material_thickness(obstacle)
                material_absorption = self.calculate_material_absorption(material_name, material_thickness)

                total_transmission *= transmission_coefficient * material_absorption

                # אם השרידות נמוכה מדי, האור לא עובר
                if total_transmission < 0.01:
                    return 0.0

        return total_transmission



    def config_dual_safe(self, center: Point3D, ceiling_height: float, room_area: float,
                         furniture_obstacles: List[ObstanceVertex]):
        """תצורה של 2 מנורות - מיקומים בטוחים"""
        spacing = min(2.0, math.sqrt(room_area) * 0.4)
        lumens_per_light = 1800

        # מיקומים ראשוניים
        pos1 = Point3D(center.x - spacing / 2, center.y, ceiling_height - 0.3)
        pos2 = Point3D(center.x + spacing / 2, center.y, ceiling_height - 0.3)

        lights = [
            LightVertex(pos1, lux=0, lumens=lumens_per_light, target_id=None, light_type="center"),
            LightVertex(pos2, lux=0, lumens=lumens_per_light, target_id=None, light_type="center")
        ]
        return {'lights': lights, 'aesthetic_score': 0.8}

    def config_triangle_safe(self, center: Point3D, ceiling_height: float, room_area: float,
                             furniture_obstacles: List[ObstanceVertex]):
        """תצורה של 3 מנורות במשולש - מיקומים בטוחים"""
        radius = min(1.5, math.sqrt(room_area) * 0.3)
        lumens_per_light = 1200
        angles = [0, 2 * math.pi / 3, 4 * math.pi / 3]

        lights = []
        for angle in angles:
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            initial_pos = Point3D(x, y, ceiling_height - 0.3)
            light = LightVertex(initial_pos, lux=0, lumens=lumens_per_light, target_id=None, light_type="center")
            lights.append(light)

        return {'lights': lights, 'aesthetic_score': 0.9}

    def config_square_safe(self, center: Point3D, ceiling_height: float, room_area: float,
                           furniture_obstacles: List[ObstanceVertex]):
        """תצורה של 4 מנורות בריבוע - מיקומים בטוחים"""
        offset = min(1.2, math.sqrt(room_area) * 0.25)
        lumens_per_light = 900
        positions = [(-offset, -offset), (offset, -offset), (offset, offset), (-offset, offset)]

        lights = []
        for dx, dy in positions:
            initial_pos = Point3D(center.x + dx, center.y + dy, ceiling_height - 0.3)
            light = LightVertex(initial_pos, lux=0, lumens=lumens_per_light, target_id=None, light_type="center")
            lights.append(light)

        return {'lights': lights, 'aesthetic_score': 0.95}

    def calculate_snells_refraction(self, incident_angle: float, n1: float, n2: float) -> float:
        """חוק סנל: n₁×sin(θ₁) = n₂×sin(θ₂)"""
        sin_incident = math.sin(incident_angle)
        sin_ratio = (n1 / n2) * sin_incident
        if sin_ratio > 1.0:
            return None  # השתקפות מלאה
        return math.asin(sin_ratio)

    def calculate_fresnel_transmission(self, incident_angle: float, refracted_angle: float,
                                       n1: float, n2: float) -> float:
        """חישוב מקדם העברה לפי משוואות פרנל"""
        cos_i = math.cos(incident_angle)
        cos_r = math.cos(refracted_angle)
        rs = ((n1 * cos_i - n2 * cos_r) / (n1 * cos_i + n2 * cos_r)) ** 2
        rp = ((n1 * cos_r - n2 * cos_i) / (n1 * cos_r + n2 * cos_i)) ** 2
        reflectance = (rs + rp) / 2
        return max(0.0, 1 - reflectance)

    def calculate_incident_angle_to_surface(self, light_pos: Point3D, target_pos: Point3D,
                                            surface_pos: Point3D) -> float:
        """חישוב זווית פגיעה למשטח"""
        light_dir_x = target_pos.x - light_pos.x
        light_dir_y = target_pos.y - light_pos.y
        light_dir_z = target_pos.z - light_pos.z
        light_length = math.sqrt(light_dir_x ** 2 + light_dir_y ** 2 + light_dir_z ** 2)
        if light_length == 0:
            return 0
        light_dir_z /= light_length
        cos_angle = abs(light_dir_z)
        return math.acos(max(0, min(1, cos_angle)))

    def calculate_cos_incident_angle(self, from_point: Point3D, to_point: Point3D) -> float:
        """📐 חישוב קוסינוס זווית פגיעה"""
        dx = to_point.x - from_point.x
        dy = to_point.y - from_point.y
        dz = to_point.z - from_point.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        if distance == 0:
            return 0.0
        light_dir_z = dz / distance
        return abs(light_dir_z)

    def line_intersects_transparent_obstacle(self, start: Point3D, end: Point3D, obstacle: ObstanceVertex) -> bool:
        """בדיקה אם קו עובר דרך חומר שקוף"""
        material_name = getattr(obstacle, 'material', '').lower()
        transparent_materials = ['glass', 'זכוכית', 'window', 'חלון']
        if not any(material in material_name for material in transparent_materials):
            return False
        return self.line_intersects_obstacle(start, end, obstacle)

    def get_refractive_index(self, material_name: str) -> float:
        """קבלת מקדם שבירה לפי שם החומר"""
        material_name = material_name.lower()
        if 'glass' in material_name or 'זכוכית' in material_name:
            return self.refractive_indices['glass']
        elif 'water' in material_name or 'מים' in material_name:
            return self.refractive_indices['water']
        elif 'plastic' in material_name or 'פלסטיק' in material_name:
            return self.refractive_indices['plastic']
        else:
            return self.refractive_indices['default']

    def calculate_material_thickness(self, obstacle: ObstanceVertex) -> float:
        """חישוב עובי החומר"""
        thickness = getattr(obstacle, 'thickness', None)
        if thickness:
            return float(thickness)
        material_name = getattr(obstacle, 'material', '').lower()
        if 'window' in material_name or 'זכוכית' in material_name:
            return 0.01
        elif 'glass' in material_name:
            return 0.005
        else:
            return 0.02

    def calculate_material_absorption(self, material_name: str, thickness: float) -> float:
        """חישוב בליעה בחומר (Beer-Lambert)"""
        absorption_coefficients = {
            'glass': 0.1, 'water': 0.05, 'plastic': 0.2, 'default': 0.1
        }
        material_name = material_name.lower()
        absorption_coeff = absorption_coefficients.get('default', 0.1)
        for material, coeff in absorption_coefficients.items():
            if material in material_name:
                absorption_coeff = coeff
                break
        return math.exp(-absorption_coeff * thickness)

    def calculate_air_attenuation(self, distance: float) -> float:
        """דעיכת אור באוויר"""
        attenuation_coefficient = 0.05
        return math.exp(-attenuation_coefficient * distance)

    def is_light_blocked(self, light_pos: Point3D, target_pos: Point3D) -> bool:
        """בדיקה אם אור חסום"""
        for obstacle in self.obstacles:
            if self.line_intersects_obstacle(light_pos, target_pos, obstacle):
                return True
        return False

    def line_intersects_obstacle(self, start: Point3D, end: Point3D, obstacle: ObstanceVertex) -> bool:
        """בדיקה אם קו אור חותך מכשול"""
        if (min(start.z, end.z) < obstacle.point.z < max(start.z, end.z)):
            distance_to_line = self.distance_point_to_line_2d(start, end, obstacle.point)
            return distance_to_line < 0.3
        return False

    def distance_point_to_line_2d(self, line_start: Point3D, line_end: Point3D, point: Point3D) -> float:
        """מרחק נקודה מקו במישור XY"""
        x1, y1 = line_start.x, line_start.y
        x2, y2 = line_end.x, line_end.y
        x0, y0 = point.x, point.y
        numerator = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
        denominator = math.sqrt((y2 - y1) ** 2 + (x2 - x1) ** 2)
        if denominator == 0:
            return math.sqrt((x0 - x1) ** 2 + (y0 - y1) ** 2)
        return numerator / denominator

    # פונקציות עזר
    def calculate_distance(self, p1: Point3D, p2: Point3D) -> float:
        """חישוב מרחק תלת מימדי"""
        return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2)

    def get_center_lights(self) -> List[LightVertex]:
        """קבלת מנורות מרכזיות"""
        return [v for v in self.graph.vertices
                if isinstance(v, LightVertex) and getattr(v, 'light_type', 'center') == 'center']

    def get_furniture_lights(self) -> List[LightVertex]:
        """קבלת מנורות ריהוט"""
        return [v for v in self.graph.vertices
                if isinstance(v, LightVertex) and getattr(v, 'light_type', 'center') == 'furniture']

    def get_obstacles(self) -> List[ObstanceVertex]:
        """קבלת כל המכשולים"""
        return [v for v in self.graph.vertices if isinstance(v, ObstanceVertex)]

    def get_furniture_obstacles(self) -> List[ObstanceVertex]:
        """קבלת מכשולי ריהוט בלבד - חישוב חכם מהגרף"""
        furniture_obstacles = []

        # שיטה 1: לפי element_type אם קיים
        for vertex in self.graph.vertices:
            if isinstance(vertex, ObstanceVertex):
                element_type = getattr(vertex, 'element_type', '').lower()
                if any(ftype in element_type for ftype in ['table', 'desk', 'sofa', 'chair', 'counter']):
                    furniture_obstacles.append(vertex)

        # שיטה 2: אם לא מצאנו, חפש לפי קבוצות צמתים (רהיטים = קבוצות של 8 צמתים)
        if len(furniture_obstacles) == 0:
            furniture_obstacles = self.detect_furniture_from_graph_structure()
            logger.debug(f"זיהוי ריהוט לפי מבנה גרף: {len(furniture_obstacles)} פריטים")

        # שיטה 3: אם עדיין לא מצאנו, קח צמתים עם required_lux > 0
        if len(furniture_obstacles) == 0:
            for vertex in self.graph.vertices:
                if isinstance(vertex, ObstanceVertex):
                    required_lux = getattr(vertex, 'required_lux', 0)
                    if required_lux > 0:
                        furniture_obstacles.append(vertex)
            logger.debug(f"זיהוי ריהוט לפי required_lux: {len(furniture_obstacles)} פריטים")

        logger.debug(f"נמצאו {len(furniture_obstacles)} פריטי ריהוט")
        return furniture_obstacles

    def detect_furniture_from_graph_structure(self) -> List[ObstanceVertex]:
        """🔍 זיהוי רהיטים לפי מבנה הגרף (קבוצות של 8 צמתים)"""
        furniture_groups = []
        used_vertices = set()

        for vertex in self.graph.vertices:
            if isinstance(vertex, ObstanceVertex) and vertex not in used_vertices:
                # מצא קבוצת צמתים קרובים (רהיט אחד)
                furniture_group = self.find_connected_furniture_vertices(vertex, used_vertices)

                if len(furniture_group) >= 4:  # לפחות 4 צמתים = רהיט
                    # קח צומת מייצג (בדרך כלל הראשון או המרכזי)
                    representative_vertex = self.get_representative_vertex(furniture_group)
                    furniture_groups.append(representative_vertex)
                    used_vertices.update(furniture_group)

        return furniture_groups

    def find_connected_furniture_vertices(self, start_vertex: ObstanceVertex, used_vertices: set) -> List[
        ObstanceVertex]:
        """🔗 מצא צמתים מחוברים שיוצרים רהיט אחד"""
        group = [start_vertex]
        to_check = [start_vertex]
        checked = {start_vertex}

        while to_check and len(group) < 12:  # הגבלה למניעת אינסוף
            current = to_check.pop(0)
            current_idx = self.graph.vertices.index(current)

            # חפש קשתות לצמתים קרובים
            for edge in self.graph.edges:
                connected_vertex = None

                if edge.start == current_idx and edge.end < len(self.graph.vertices):
                    connected_vertex = self.graph.vertices[edge.end]
                elif edge.end == current_idx and edge.start < len(self.graph.vertices):
                    connected_vertex = self.graph.vertices[edge.start]

                if (connected_vertex and
                        isinstance(connected_vertex, ObstanceVertex) and
                        connected_vertex not in checked and
                        connected_vertex not in used_vertices and
                        edge.length < 2.0):  # קשתות קצרות = אותו רהיט

                    group.append(connected_vertex)
                    to_check.append(connected_vertex)
                    checked.add(connected_vertex)

        return group

    def get_representative_vertex(self, furniture_group: List[ObstanceVertex]) -> ObstanceVertex:
        """📍 קבל צומת מייצג מקבוצת הרהיט"""
        if len(furniture_group) == 1:
            return furniture_group[0]

        # חשב מרכז המסה של הקבוצה
        avg_x = sum(v.point.x for v in furniture_group) / len(furniture_group)
        avg_y = sum(v.point.y for v in furniture_group) / len(furniture_group)
        avg_z = sum(v.point.z for v in furniture_group) / len(furniture_group)

        # מצא את הצומת הקרוב ביותר למרכז
        center_point = Point3D(avg_x, avg_y, avg_z)
        closest_vertex = min(furniture_group,
                             key=lambda v: self.calculate_distance(v.point, center_point))

        # העתק מאפיינים מהקבוצה
        closest_vertex.furniture_group = furniture_group
        return closest_vertex

    def get_reflection_surfaces(self) -> List[ObstanceVertex]:
        """קבלת משטחים מחזירי אור"""
        return [v for v in self.graph.vertices
                if isinstance(v, ObstanceVertex) and getattr(v, 'reflection_factor', 0) > 0.05]