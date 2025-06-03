# ShadowOptimizer.py - גרסה מלאה עם חוקי פיזיקה מדויקים ובדיקת כל הצמתים
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

        # מקדמי שבירה לחוק סנל
        self.refractive_indices = {
            'air': 1.0,
            'glass': 1.52,
            'water': 1.33,
            'plastic': 1.4,
            'default': 1.0
        }

        #  חישוב תאורה לכל הצמתים מראש
        self.calculate_accurate_illumination_for_all_vertices()

    def calculate_accurate_illumination_for_all_vertices(self):
        """ חישוב מדויק של תאורה לכל צומת בגרף"""
        logger.debug(" מחשב תאורה מדויקת לכל צומת")

        for vertex in self.graph.vertices:
            if isinstance(vertex, ObstanceVertex):
                # חישוב עוצמת תאורה פיזיקלית בפועל
                vertex.actual_lux = self.calculate_physics_based_lux_for_vertex(vertex)

                # קביעת עוצמה נדרשת לפי סוג האלמנט
                vertex.required_lux = self.get_required_lux_by_element_type(vertex)

                # עדכון מקדם החזרה לפי החומר
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
        """ קביעת עוצמת תאורה נדרשת לפי סוג האלמנט"""
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
        """🧱 עדכון מקדם החזרה לפי החומר האמיתי"""
        material_name = getattr(vertex, 'material', 'unknown')
        material_reflection = MaterialReflection.get_by_material_name(material_name)
        vertex.reflection_factor = material_reflection.reflection_factor

        logger.debug(f"חומר '{material_name}' -> מקדם החזרה: {vertex.reflection_factor}")

    def optimize_lighting_room(self) -> List[LightVertex]:
        """אופטימיזציה מדויקת לחדר לפי חוקי הפיזיקה"""
        logger.debug("מתחיל אופטימיזציה מבוססת פיזיקה לחדר")

        # קבלת מנורות מרכזיות קיימות
        center_lights = self.get_center_lights()
        if not center_lights:
            logger.warning("לא נמצאו מנורות מרכזיות קיימות")
            return []

        current_center = center_lights[0]
        furniture_obstacles = self.get_furniture_obstacles()

        # חילוץ מידע החדר מהגרף
        room_area, ceiling_height = self.extract_room_info_from_graph()

        # 4 תצורות מנורות שונות
        configurations = [
            ("מנורה מרכזית אחת", self.config_single_simple(current_center.point, ceiling_height)),
            ("2 מנורות", self.config_dual_simple(current_center.point, ceiling_height, room_area)),
            ("משולש 3 מנורות", self.config_triangle_simple(current_center.point, ceiling_height, room_area)),
            ("ריבוע 4 מנורות", self.config_square_simple(current_center.point, ceiling_height, room_area))
        ]

        best_lights = None
        best_score = float('inf')
        best_name = ""

        for name, config in configurations:
            lights = config['lights']

            # חישוב ציון צללים ווקטוריאלי
            shadow_score = self.calculate_vectorial_shadow_score(lights, furniture_obstacles, room_area)

            # חישוב ציון תאורה פיזיקלי מדויק - כל הצמתים
            illumination_score = self.calculate_physics_illumination_score_all_vertices(lights)
            aesthetic_score = config['aesthetic_score']

            # 70% תאורה פיזיקלית, 20% צללים, 10% אסתטיקה
            total_score = illumination_score * 0.7 + shadow_score * 0.2 + aesthetic_score * 0.1

            logger.debug(f"        {name}: תאורה={illumination_score:.2f}, צללים={shadow_score:.2f}, "
                         f"אסתטיקה={aesthetic_score:.2f} סה\"כ={total_score:.2f}")

            if total_score < best_score:
                best_score = total_score
                best_lights = lights
                best_name = name

        logger.debug(f" נבחר: {best_name} עם ציון {best_score:.2f}")

        # הוספת מנורות ריהוט + מנורות מרכזיות המאופטמות
        furniture_lights = self.get_furniture_lights()
        result = best_lights + furniture_lights
        return result

    def calculate_physics_illumination_score_all_vertices(self, lights: List[LightVertex]) -> float:
        """🔬 ציון פיזיקלי מבוסס על כל הצמתים בגרף"""
        total_error = 0.0
        point_count = 0

        # 🆕 בדוק את כל הצמתים במקום רק furniture
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
        """חילוץ מידע החדר מהגרף"""
        # חישוב שטח החדר לפי הצמתים
        all_x = [v.point.x for v in self.graph.vertices]
        all_y = [v.point.y for v in self.graph.vertices]
        all_z = [v.point.z for v in self.graph.vertices]

        if all_x and all_y:
            room_width = max(all_x) - min(all_x)
            room_length = max(all_y) - min(all_y)
            room_area = max(room_width * room_length, 10.0)  # מינימום 10 מ"ר
        else:
            room_area = 20.0  # ברירת מחדל

        if all_z:
            ceiling_height = max(all_z)
            ceiling_height = max(ceiling_height, 2.5)  # מינימום 2.5 מטר
        else:
            ceiling_height = 2.5  # ברירת מחדל

        logger.debug(f"מידע חדר: שטח={room_area:.1f}מ\"ר, גובה={ceiling_height:.1f}מ")
        return room_area, ceiling_height

    def calculate_vectorial_shadow_score(self, lights: List[LightVertex],
                                         furniture_obstacles: List[ObstanceVertex],
                                         room_area: float) -> float:
        """חישוב ציון צללים וקטוריאלי מדויק"""
        if not furniture_obstacles:
            return 0.0

        total_shadow_area = 0.0
        grid_points = self.generate_room_grid_points(room_area)

        for obstacle in furniture_obstacles:
            obstacle_shadow_area = 0.0

            for grid_point in grid_points:
                shadow_intensity = 0.0

                for light in lights:
                    # בדיקה אם המכשול חוסם את האור לנקודה זו
                    if self.is_point_in_shadow(light.point, grid_point, obstacle):
                        # חישוב עוצמת הצל לפי מרחק מהמכשול
                        distance_to_obstacle = self.calculate_distance(grid_point, obstacle.point)
                        shadow_factor = max(0, 1 - (distance_to_obstacle / 2.0))
                        shadow_intensity += shadow_factor

                # נקודה בצל אם יש צל מלפחות מנורה אחת
                if shadow_intensity > 0:
                    obstacle_shadow_area += shadow_intensity

            total_shadow_area += obstacle_shadow_area

        # ציון צללים - ככל שיש יותר צל, הציון גבוה יותר (רע יותר)
        shadow_score = total_shadow_area / max(len(grid_points), 1)
        return min(shadow_score, 10.0)  # הגבלת הציון

    def calculate_total_illumination_at_point(self, point: Point3D, lights: List[LightVertex]) -> float:
        """חישוב תאורה כוללת בנקודה (ישיר + מוחזר)"""
        total_lux = 0.0

        for light in lights:
            # אור ישיר (חוק הריבוע ההפוך)
            direct_lux = self.calculate_direct_illumination(light, point)

            # אור מוחזר (חוק למברט)
            reflected_lux = self.calculate_reflected_illumination(light, point)

            total_lux += direct_lux + reflected_lux

        return total_lux

    def calculate_direct_illumination(self, light: LightVertex, point: Point3D) -> float:
        """חישוב אור ישיר לפי חוק הריבוע ההפוך"""
        distance = self.calculate_distance(light.point, point)
        distance = max(distance, self.min_distance)

        # בדיקת חסימה והשפעת חומרים שקופים
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
        """חישוב אור מוחזר ממשטחים (חוק למברט עם MaterialReflection)"""
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
        """חישוב העברת אור דרך חומרים שקופים (חוק סנל)"""
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

    def calculate_snells_refraction(self, incident_angle: float, n1: float, n2: float) -> float:
        """חוק סנל: n₁×sin(θ₁) = n₂×sin(θ₂)"""
        sin_incident = math.sin(incident_angle)
        sin_ratio = (n1 / n2) * sin_incident

        # בדיקת השתקפות מלאה
        if sin_ratio > 1.0:
            return None  # השתקפות מלאה

        # זווית השבירה
        refracted_angle = math.asin(sin_ratio)
        return refracted_angle

    def calculate_fresnel_transmission(self, incident_angle: float, refracted_angle: float,
                                       n1: float, n2: float) -> float:
        """חישוב מקדם העברה לפי משוואות פרנל"""
        cos_i = math.cos(incident_angle)
        cos_r = math.cos(refracted_angle)

        # משוואות פרנל
        rs = ((n1 * cos_i - n2 * cos_r) / (n1 * cos_i + n2 * cos_r)) ** 2
        rp = ((n1 * cos_r - n2 * cos_i) / (n1 * cos_r + n2 * cos_i)) ** 2

        # מקדם השתקפות ממוצע
        reflectance = (rs + rp) / 2

        # מקדם העברה
        transmittance = 1 - reflectance
        return max(0.0, transmittance)

    def calculate_incident_angle_to_surface(self, light_pos: Point3D, target_pos: Point3D,
                                            surface_pos: Point3D) -> float:
        """חישוב זווית פגיעה למשטח"""
        # וקטור האור
        light_dir_x = target_pos.x - light_pos.x
        light_dir_y = target_pos.y - light_pos.y
        light_dir_z = target_pos.z - light_pos.z

        light_length = math.sqrt(light_dir_x ** 2 + light_dir_y ** 2 + light_dir_z ** 2)
        if light_length == 0:
            return 0

        # נרמול וקטור האור
        light_dir_x /= light_length
        light_dir_y /= light_length
        light_dir_z /= light_length

        # נורמל המשטח (בהנחה שהמשטח אופקי)
        normal_x, normal_y, normal_z = 0, 0, 1

        # זווית פגיעה
        cos_angle = abs(light_dir_x * normal_x + light_dir_y * normal_y + light_dir_z * normal_z)
        return math.acos(max(0, min(1, cos_angle)))

    def calculate_cos_incident_angle(self, from_point: Point3D, to_point: Point3D) -> float:
        """חישוב קוסינוס זווית פגיעה"""
        dx = to_point.x - from_point.x
        dy = to_point.y - from_point.y
        dz = to_point.z - from_point.z

        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        if distance == 0:
            return 0.0

        # נורמל משטח (בהנחה שהמשטח אופקי)
        normal_z = 1.0
        light_dir_z = dz / distance

        # קוסינוס הזווית
        cos_angle = abs(light_dir_z * normal_z)
        return cos_angle

    def line_intersects_transparent_obstacle(self, start: Point3D, end: Point3D, obstacle: ObstanceVertex) -> bool:
        """בדיקה אם קו עובר דרך חומר שקוף (חלון, זכוכית)"""
        material_name = getattr(obstacle, 'material', '').lower()

        # רק חומרים שקופים
        transparent_materials = ['glass', 'זכוכית', 'window', 'חלון']
        if not any(material in material_name for material in transparent_materials):
            return False

        # בדיקה גיאומטרית אם הקו עובר דרך המכשול
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
        # ניסיון לחלץ מהמאפיינים
        thickness = getattr(obstacle, 'thickness', None)
        if thickness:
            return float(thickness)

        # ברירת מחדל לפי סוג
        material_name = getattr(obstacle, 'material', '').lower()
        if 'window' in material_name or 'זכוכית' in material_name:
            return 0.01  # 1 ס"מ זכוכית
        elif 'glass' in material_name:
            return 0.005  # 0.5 ס"מ זכוכית דקה
        else:
            return 0.02  # 2 ס"מ ברירת מחדל

    def calculate_material_absorption(self, material_name: str, thickness: float) -> float:
        """חישוב בליעה בחומר (Beer-Lambert)"""
        # מקדמי בליעה (באורך גל נראה)
        absorption_coefficients = {
            'glass': 0.1,  # זכוכית שקופה
            'water': 0.05,  # מים
            'plastic': 0.2,  # פלסטיק
            'default': 0.1
        }

        material_name = material_name.lower()
        absorption_coeff = absorption_coefficients.get('default', 0.1)

        for material, coeff in absorption_coefficients.items():
            if material in material_name:
                absorption_coeff = coeff
                break

        # חוק Beer-Lambert: I = I₀ × e^(-αt)
        transmission = math.exp(-absorption_coeff * thickness)
        return transmission

    def calculate_air_attenuation(self, distance: float) -> float:
        """דעיכת אור באוויר"""
        # דעיכה קלה באוויר נקי
        attenuation_coefficient = 0.05  # לק"מ - מתוקן
        return math.exp(-attenuation_coefficient * distance)

    def is_light_blocked(self, light_pos: Point3D, target_pos: Point3D) -> bool:
        """בדיקה אם אור חסום על ידי מכשול"""
        for obstacle in self.obstacles:
            if self.line_intersects_obstacle(light_pos, target_pos, obstacle):
                return True
        return False

    def line_intersects_obstacle(self, start: Point3D, end: Point3D, obstacle: ObstanceVertex) -> bool:
        """בדיקה אם קו אור חותך מכשול"""
        # בדיקה פשוטה - אם המכשול בין המנורה לנקודה בגובה
        if (min(start.z, end.z) < obstacle.point.z < max(start.z, end.z)):
            # מרחק מהמכשול לקו במישור XY
            distance_to_line = self.distance_point_to_line_2d(start, end, obstacle.point)
            return distance_to_line < 0.3  # רדיוס מכשול
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

    def is_point_in_shadow(self, light_pos: Point3D, check_point: Point3D, obstacle: ObstanceVertex) -> bool:
        """בדיקה אם נקודה בצל של מכשול"""
        return self.line_intersects_obstacle(light_pos, check_point, obstacle)

    def generate_room_grid_points(self, room_area: float, density: float = 0.5) -> List[Point3D]:
        """יצירת רשת נקודות בחדר לבדיקת צללים"""
        grid_points = []

        # חישוב גודל החדר משטח
        room_size = math.sqrt(room_area)

        # יצירת רשת
        steps = max(int(room_size / density), 3)
        for i in range(steps):
            for j in range(steps):
                x = (i / (steps - 1)) * room_size - room_size / 2
                y = (j / (steps - 1)) * room_size - room_size / 2
                z = 0.8  # גובה עבודה
                grid_points.append(Point3D(x, y, z))

        return grid_points

    def generate_furniture_check_points(self, obstacle: ObstanceVertex) -> List[Point3D]:
        """יצירת נקודות בדיקה סביב פריט ריהוט"""
        base_point = obstacle.point
        check_points = []

        # נקודות בפינות ובמרכז
        offsets = [(-0.3, -0.3), (0.3, -0.3), (0.3, 0.3), (-0.3, 0.3), (0, 0)]

        for dx, dy in offsets:
            point = Point3D(base_point.x + dx, base_point.y + dy, base_point.z + 0.1)
            check_points.append(point)

        return check_points

    def get_required_lux_for_obstacle(self, obstacle: ObstanceVertex) -> float:
        """קביעת לוקס נדרש לפי סוג המכשול"""
        element_type = getattr(obstacle, 'element_type', '').lower()

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

    # תצורות מנורות
    def config_single_simple(self, center: Point3D, ceiling_height: float):
        """תצורה של מנורה אחת"""
        lumens = 3000  # לומן בסיסי
        light = LightVertex(
            Point3D(center.x, center.y, ceiling_height - 0.3),
            lux=0, lumens=lumens, target_id=None, light_type="center"
        )
        return {'lights': [light], 'aesthetic_score': 1.0}

    def config_dual_simple(self, center: Point3D, ceiling_height: float, room_area: float):
        """תצורה של 2 מנורות"""
        spacing = min(2.0, math.sqrt(room_area) * 0.4)
        lumens_per_light = 1800

        lights = [
            LightVertex(Point3D(center.x - spacing / 2, center.y, ceiling_height - 0.3),
                        lux=0, lumens=lumens_per_light, target_id=None, light_type="center"),
            LightVertex(Point3D(center.x + spacing / 2, center.y, ceiling_height - 0.3),
                        lux=0, lumens=lumens_per_light, target_id=None, light_type="center")
        ]
        return {'lights': lights, 'aesthetic_score': 0.8}

    def config_triangle_simple(self, center: Point3D, ceiling_height: float, room_area: float):
        """תצורה של 3 מנורות במשולש"""
        radius = min(1.5, math.sqrt(room_area) * 0.3)
        lumens_per_light = 1200
        angles = [0, 2 * math.pi / 3, 4 * math.pi / 3]

        lights = []
        for angle in angles:
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            light = LightVertex(Point3D(x, y, ceiling_height - 0.3),
                                lux=0, lumens=lumens_per_light, target_id=None, light_type="center")
            lights.append(light)

        return {'lights': lights, 'aesthetic_score': 0.9}

    def config_square_simple(self, center: Point3D, ceiling_height: float, room_area: float):
        """תצורה של 4 מנורות בריבוע"""
        offset = min(1.2, math.sqrt(room_area) * 0.25)
        lumens_per_light = 900
        positions = [(-offset, -offset), (offset, -offset), (offset, offset), (-offset, offset)]

        lights = []
        for dx, dy in positions:
            light = LightVertex(Point3D(center.x + dx, center.y + dy, ceiling_height - 0.3),
                                lux=0, lumens=lumens_per_light, target_id=None, light_type="center")
            lights.append(light)

        return {'lights': lights, 'aesthetic_score': 0.95}

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
        """קבלת מכשולי ריהוט בלבד"""
        furniture_obstacles = []
        for vertex in self.graph.vertices:
            if isinstance(vertex, ObstanceVertex):
                element_type = getattr(vertex, 'element_type', '').lower()
                if any(ftype in element_type for ftype in ['table', 'desk', 'sofa', 'chair', 'counter']):
                    furniture_obstacles.append(vertex)
        return furniture_obstacles

    def get_reflection_surfaces(self) -> List[ObstanceVertex]:
        """קבלת משטחים מחזירי אור"""
        return [v for v in self.graph.vertices
                if isinstance(v, ObstanceVertex) and getattr(v, 'reflection_factor', 0) > 0.05]