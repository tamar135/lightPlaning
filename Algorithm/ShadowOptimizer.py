import math
import logging
from typing import List, Tuple, Optional
from models import Point3D, LightVertex, ObstanceVertex, Graph
from MaterialReflection import MaterialReflection
import statistics
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

        self.MIN_DISTANCE = 0.01  # למניעת חלוקה באפס

        self.calculate_physics_based_illumination()

    def calculate_physics_based_illumination(self):
        """חישוב תאורה מבוסס חוקי פיזיקה"""
        logger.debug("מתחיל חישוב תאורה פיזיקלי")

        for vertex in self.graph.vertices:
            if isinstance(vertex, ObstanceVertex):
                vertex.actual_lux = self.calculate_full_ray_traced_illumination(vertex)
                vertex.required_lux = self.get_required_lux_by_element_type(vertex)
                self.update_material_reflection_factor(vertex)

    def calculate_full_ray_traced_illumination(self, vertex: ObstanceVertex) -> float:
        """חישוב תאורה מלא עם Ray Tracing"""
        total_illumination = 0.0

        for light in self.center_lights + self.furniture_lights:
            # חוק הריבוע ההפוך
            direct_illumination = self.calculate_inverse_square_law_illumination(light, vertex.point)

            # חוק למברט להחזרות
            reflected_illumination = self.calculate_lambert_reflected_illumination(light, vertex.point)

            # חוק סנל לשבירות
            refracted_illumination = self.calculate_snell_refracted_illumination(light, vertex.point)

            total_illumination += direct_illumination + reflected_illumination + refracted_illumination

        return total_illumination

    def calculate_inverse_square_law_illumination(self, light: LightVertex, target_point: Point3D) -> float:
        """חוק הריבוע ההפוך: I = P / (4π × r²)"""
        distance = max(self.calculate_3d_distance(light.point, target_point), self.MIN_DISTANCE)

        if self.is_direct_path_blocked(light.point, target_point):
            return 0.0

        # חוק הריבוע ההפוך
        luminous_intensity = light.lumens / (4 * math.pi)
        illumination = luminous_intensity / (distance ** 2)

        # חוק למברט לזווית פגיעה
        cos_incident_angle = self.calculate_lambert_cosine_angle(light.point, target_point)

        return illumination * cos_incident_angle

    def calculate_lambert_reflected_illumination(self, light: LightVertex, target_point: Point3D) -> float:
        """חוק למברט להחזרות: L = (ρ/π) × E × cos(θ)"""
        total_reflected = 0.0

        for surface in self.reflection_surfaces:
            light_to_surface = max(self.calculate_3d_distance(light.point, surface.point), self.MIN_DISTANCE)
            surface_to_target = max(self.calculate_3d_distance(surface.point, target_point), self.MIN_DISTANCE)

            if (self.is_direct_path_blocked(light.point, surface.point) or
                    self.is_direct_path_blocked(surface.point, target_point)):
                continue

            # עוצמת אור פוגעת במשטח
            incident_intensity = light.lumens / (4 * math.pi * light_to_surface ** 2)

            # זוויות למברט
            cos_incident = self.calculate_lambert_cosine_angle(light.point, surface.point)
            cos_reflected = self.calculate_lambert_cosine_angle(surface.point, target_point)

            if cos_incident > 0 and cos_reflected > 0:
                # מקדם החזרה
                material_enum = self.get_material_enum_from_vertex(surface)
                reflection_coefficient = material_enum.reflection_factor

                # נוסחת למברט
                reflected_radiance = (reflection_coefficient / math.pi) * incident_intensity * cos_incident
                reflected_illumination = reflected_radiance * cos_reflected / (surface_to_target ** 2)

                total_reflected += reflected_illumination

        return total_reflected

    def calculate_snell_refracted_illumination(self, light: LightVertex, target_point: Point3D) -> float:
        """חוק סנל: n₁sin(θ₁) = n₂sin(θ₂)"""
        total_refracted = 0.0

        transparent_obstacles = self.find_transparent_obstacles_in_path(light.point, target_point)

        for obstacle in transparent_obstacles:
            refracted_intensity = self.calculate_snell_transmission(light, target_point, obstacle)
            total_refracted += refracted_intensity

        return total_refracted

    def calculate_snell_transmission(self, light: LightVertex, target_point: Point3D,
                                     obstacle: ObstanceVertex) -> float:
        """חישוב שבירה דרך חומר"""
        material_enum = self.get_material_enum_from_vertex(obstacle)

        # מקדמי שבירה
        n1 = 1.0  # אוויר
        n2 = self.get_refractive_index_from_enum(material_enum)

        incident_angle = self.calculate_incident_angle(light.point, target_point, obstacle.point)

        # חוק סנל
        sin_incident = math.sin(incident_angle)
        sin_ratio = (n1 / n2) * sin_incident

        if sin_ratio > 1.0:
            return 0.0  # השתקפות מלאה

        refraction_angle = math.asin(sin_ratio)

        # מקדמי פרנל
        transmission_coefficient = self.calculate_fresnel_transmission_coefficient(
            incident_angle, refraction_angle, n1, n2)

        # דעיכה בחומר
        absorption_coefficient = self.get_absorption_coefficient_from_enum(material_enum)
        attenuation = math.exp(-absorption_coefficient)

        # חישוב סופי
        distance_to_obstacle = max(self.calculate_3d_distance(light.point, obstacle.point), self.MIN_DISTANCE)
        initial_intensity = light.lumens / (4 * math.pi * distance_to_obstacle ** 2)
        transmitted_intensity = initial_intensity * transmission_coefficient * attenuation

        obstacle_to_target = max(self.calculate_3d_distance(obstacle.point, target_point), self.MIN_DISTANCE)
        final_illumination = transmitted_intensity / (obstacle_to_target ** 2)

        return final_illumination

    def get_material_enum_from_vertex(self, vertex: ObstanceVertex) -> MaterialReflection:
        """קבלת MaterialReflection ENUM """
        material_name = getattr(vertex, 'material', 'unknown')
        return MaterialReflection.get_by_material_name(material_name)

    def get_refractive_index_from_enum(self, material_enum: MaterialReflection) -> float:
        """מקדם שבירה לפי ENUM """
        if material_enum == MaterialReflection.GLASS:
            return 1.52
        elif material_enum == MaterialReflection.MIRROR:
            return 1.52
        elif material_enum == MaterialReflection.CERAMIC:
            return 1.3
        elif material_enum == MaterialReflection.WOOD_VARNISHED:
            return 1.4
        else:
            return 1.0  # אטום או אוויר

    def get_absorption_coefficient_from_enum(self, material_enum: MaterialReflection) -> float:
        """מקדם בליעה לפי ENUM"""
        if material_enum == MaterialReflection.GLASS:
            return 0.05
        elif material_enum == MaterialReflection.MIRROR:
            return 0.02
        elif material_enum == MaterialReflection.CERAMIC:
            return 0.15
        else:
            return 0.1

    def calculate_fresnel_transmission_coefficient(self, incident_angle: float, refraction_angle: float,
                                                   n1: float, n2: float) -> float:
        """מקדמי פרנל"""
        cos_i = math.cos(incident_angle)
        cos_t = math.cos(refraction_angle)

        if cos_i == 0 or cos_t == 0:
            return 0.0

        rs = ((n1 * cos_i - n2 * cos_t) / (n1 * cos_i + n2 * cos_t)) ** 2
        rp = ((n1 * cos_t - n2 * cos_i) / (n1 * cos_t + n2 * cos_i)) ** 2

        reflectance = (rs + rp) / 2
        transmittance = 1 - reflectance

        return max(0.0, transmittance)

    def calculate_lambert_cosine_angle(self, from_point: Point3D, to_point: Point3D) -> float:
        """קוסינוס זווית לחוק למברט"""
        dx = to_point.x - from_point.x
        dy = to_point.y - from_point.y
        dz = to_point.z - from_point.z

        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        if distance == 0:
            return 0.0

        # נורמל אופקי
        cos_angle = abs(dz / distance)
        return cos_angle

    def is_direct_path_blocked(self, start_point: Point3D, end_point: Point3D) -> bool:
        """בדיקת חסימה"""
        for obstacle in self.obstacles:
            if self.line_intersects_opaque_obstacle(start_point, end_point, obstacle):
                return True
        return False

    def line_intersects_opaque_obstacle(self, start: Point3D, end: Point3D,
                                        obstacle: ObstanceVertex) -> bool:
        """בדיקת חיתוך עם מכשול אטום"""
        material_enum = self.get_material_enum_from_vertex(obstacle)

        opaque_materials = [
            MaterialReflection.WOOD,
            MaterialReflection.METAL,
            MaterialReflection.CONCRETE,
            MaterialReflection.FABRIC,
            MaterialReflection.DARK_COLOR,
            MaterialReflection.BLACK
        ]

        if material_enum not in opaque_materials:
            return False

        return self.geometric_line_obstacle_intersection(start, end, obstacle)

    def geometric_line_obstacle_intersection(self, start: Point3D, end: Point3D,
                                             obstacle: ObstanceVertex) -> bool:
        """בדיקה גיאומטרית"""
        obstacle_distance = self.point_to_line_distance_3d(start, end, obstacle.point)
        obstacle_radius = self.estimate_obstacle_radius(obstacle)
        return obstacle_distance < obstacle_radius

    def point_to_line_distance_3d(self, line_start: Point3D, line_end: Point3D,
                                  point: Point3D) -> float:
        """מרחק נקודה מקו במרחב תלת ממדי"""
        line_vec = Point3D(line_end.x - line_start.x,
                           line_end.y - line_start.y,
                           line_end.z - line_start.z)

        point_vec = Point3D(point.x - line_start.x,
                            point.y - line_start.y,
                            point.z - line_start.z)

        #  מכפלה וקטורית- מחזירה וקטור מאונך ל2 הוקטורים, אורך של וקטור המכפלה- אורך הקו* אורך הוקטור מהנקודה לקו- שטח ה"מקבילית"
        cross_x = line_vec.y * point_vec.z - line_vec.z * point_vec.y
        cross_y = line_vec.z * point_vec.x - line_vec.x * point_vec.z
        cross_z = line_vec.x * point_vec.y - line_vec.y * point_vec.x
        #המגניטודה- פיתגורס תלת מימדי
        #שטח המקבילית
        cross_magnitude = math.sqrt(cross_x * cross_x + cross_y * cross_y + cross_z * cross_z)
        #אורך הקו
        line_magnitude = math.sqrt(line_vec.x * line_vec.x + line_vec.y * line_vec.y + line_vec.z * line_vec.z)

        if line_magnitude == 0:
            return self.calculate_3d_distance(line_start, point)

        #המרחק= שטח/ אורך הקו
        return cross_magnitude / line_magnitude

    def find_transparent_obstacles_in_path(self, start: Point3D, end: Point3D) -> List[ObstanceVertex]:
        """מציאת מכשולים שקופים"""
        transparent_obstacles = []

        for obstacle in self.obstacles:
            material_enum = self.get_material_enum_from_vertex(obstacle)

            # חומרים שקופים לפי ENUM
            transparent_materials = [
                MaterialReflection.GLASS,
                MaterialReflection.MIRROR,
                MaterialReflection.CERAMIC,
                MaterialReflection.WOOD_VARNISHED,
                MaterialReflection.GLOSSY_PAINT
            ]

            if (material_enum in transparent_materials and
                    self.geometric_line_obstacle_intersection(start, end, obstacle)):
                transparent_obstacles.append(obstacle)

        return transparent_obstacles

    def calculate_incident_angle(self, light_pos: Point3D, target_pos: Point3D,
                                 surface_pos: Point3D) -> float:
        """זווית פגיעה"""
        light_direction = Point3D(target_pos.x - light_pos.x,
                                  target_pos.y - light_pos.y,
                                  target_pos.z - light_pos.z)

        light_length = math.sqrt(light_direction.x ** 2 + light_direction.y ** 2 + light_direction.z ** 2)
        if light_length == 0:
            return 0.0

        # נרמול
        light_direction.x /= light_length
        light_direction.y /= light_length
        light_direction.z /= light_length

        # זווית למשטח אופקי
        cos_angle = abs(light_direction.z)
        return math.acos(max(0, min(1, cos_angle)))

    def estimate_obstacle_radius(self, obstacle: ObstanceVertex) -> float:
        """רדיוס מכשול"""
        width = getattr(obstacle, 'width', 0.5)
        length = getattr(obstacle, 'length', 0.5)
        height = getattr(obstacle, 'height', 0.5)
        return (width + length + height) / 6

    def calculate_3d_distance(self, p1: Point3D, p2: Point3D) -> float:
        """מרחק תלת ממדי"""
        return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2)

    def get_required_lux_by_element_type(self, vertex: ObstanceVertex) -> float:
        """לוקס נדרש לפי סוג אלמנט"""
        element_type = getattr(vertex, 'element_type', '').lower()

        if 'desk' in element_type or 'workbench' in element_type:
            return 500
        elif 'counter' in element_type:
            return 400
        elif 'table' in element_type:
            return 300
        elif 'sofa' in element_type or 'chair' in element_type:
            return 200
        else:
            return self.required_lux

    def update_material_reflection_factor(self, vertex: ObstanceVertex):
        """עדכון מקדם החזרה מה-ENUM"""
        material_enum = self.get_material_enum_from_vertex(vertex)
        vertex.reflection_factor = material_enum.reflection_factor

    def optimize_lighting_room(self) -> List[LightVertex]:
        """האלגוריתם הראשי"""
        logger.debug("מתחיל אופטימיזציה עם Ray Tracing")

        center_lights = self.get_center_lights()
        if not center_lights:
            return []

        current_center = center_lights[0]
        safe_center = self.find_safe_center_position(current_center.point)
        room_area, ceiling_height = self.extract_room_info_from_graph()

        # 4 תצורות קבועות
        configurations = [
            ("מנורה אחת", self.config_single_center(safe_center, ceiling_height)),
            ("2 מנורות קו", self.config_dual_line(safe_center, ceiling_height, room_area)),
            ("3 מנורות משולש", self.config_triangle_equal(safe_center, ceiling_height, room_area)),
            ("4 מנורות ריבוע", self.config_square_grid(safe_center, ceiling_height, room_area))
        ]

        best_lights = None
        best_score = float('inf')
        best_name = ""

        for name, config in configurations:
            lights = config['lights']
            physics_score = self.calculate_physics_score(lights)
            aesthetic_score = self.calculate_aesthetic_score(lights)*-0.7*len(lights)
            total_score = physics_score * 0.85 + aesthetic_score * 0.15

            if total_score < best_score:
                best_score = total_score
                best_lights = lights
                best_name = name

        furniture_lights = self.get_furniture_lights()
        return best_lights + furniture_lights

    def find_safe_center_position(self, original_center: Point3D) -> Point3D:
        """מרכז בטוח לא מעל ריהוט"""
        furniture_obstacles = self.get_furniture_obstacles()

        for obstacle in furniture_obstacles:
            distance = self.calculate_distance_2d(original_center, obstacle.point)
            if distance < 1.0:
                offset_x = 1.5 if obstacle.point.x < original_center.x else -1.5
                offset_y = 1.5 if obstacle.point.y < original_center.y else -1.5
                return Point3D(original_center.x + offset_x, original_center.y + offset_y, original_center.z)

        return original_center

    def calculate_distance_2d(self, p1: Point3D, p2: Point3D) -> float:
        """מרחק במישור XY"""
        return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)

    def calculate_physics_score(self, lights: List[LightVertex]) -> float:
        """ציון פיזיקלי"""
        total_error = 0.0
        point_count = 0

        for vertex in self.graph.vertices:
            if isinstance(vertex, ObstanceVertex):
                actual_lux = self.calculate_physics_illumination_at_point(vertex.point, lights)
                required_lux = getattr(vertex, 'required_lux', self.required_lux)

                if actual_lux < required_lux:
                    error = ((required_lux - actual_lux) / required_lux) ** 2
                elif actual_lux > required_lux * 1.5:
                    error = ((actual_lux - required_lux * 1.5) / required_lux) * 0.5
                else:
                    error = 0.0

                total_error += error
                point_count += 1

        return total_error / max(point_count, 1)

    def calculate_physics_illumination_at_point(self, point: Point3D, lights: List[LightVertex]) -> float:
        """תאורה בנקודה עם כל החוקים"""
        total_illumination = 0.0

        for light in lights:
            direct = self.calculate_inverse_square_law_illumination(light, point)
            reflected = self.calculate_lambert_reflected_illumination(light, point)
            refracted = self.calculate_snell_refracted_illumination(light, point)

            total_illumination += direct + reflected + refracted

        return total_illumination

    # 4 תצורות המנורות
    def config_single_center(self, center: Point3D, ceiling_height: float):
        light = LightVertex(Point3D(center.x, center.y, ceiling_height - 0.3),
                            lux=0, lumens=3000, target_id=None, light_type="center")
        return {'lights': [light], 'aesthetic_score': 1.0}

    def config_dual_line(self, center: Point3D, ceiling_height: float, room_area: float):
        spacing = min(2.5, math.sqrt(room_area) * 0.4)
        lumens_per_light = 1800
        lights = [
            LightVertex(Point3D(center.x - spacing / 2, center.y, ceiling_height - 0.3),
                        lux=0, lumens=lumens_per_light, target_id=None, light_type="center"),
            LightVertex(Point3D(center.x + spacing / 2, center.y, ceiling_height - 0.3),
                        lux=0, lumens=lumens_per_light, target_id=None, light_type="center")
        ]
        return {'lights': lights, 'aesthetic_score': 0.8}

    def config_triangle_equal(self, center: Point3D, ceiling_height: float, room_area: float):
        radius = min(1.8, math.sqrt(room_area) * 0.35)
        lumens_per_light = 1200
        angles = [math.radians(90), math.radians(210), math.radians(330)]
        lights = []
        for angle in angles:
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            light = LightVertex(Point3D(x, y, ceiling_height - 0.3),
                                lux=0, lumens=lumens_per_light, target_id=None, light_type="center")
            lights.append(light)
        return {'lights': lights, 'aesthetic_score': 0.9}

    def config_square_grid(self, center: Point3D, ceiling_height: float, room_area: float):
        offset = min(1.5, math.sqrt(room_area) * 0.3)
        lumens_per_light = 900
        positions = [(-offset, -offset), (offset, -offset), (offset, offset), (-offset, offset)]
        lights = []
        for dx, dy in positions:
            light = LightVertex(Point3D(center.x + dx, center.y + dy, ceiling_height - 0.3),
                                lux=0, lumens=lumens_per_light, target_id=None, light_type="center")
            lights.append(light)
        return {'lights': lights, 'aesthetic_score': 0.95}

    def extract_room_info_from_graph(self) -> Tuple[float, float]:
        all_x = [v.point.x for v in self.graph.vertices]
        all_y = [v.point.y for v in self.graph.vertices]
        all_z = [v.point.z for v in self.graph.vertices]
        if all_x and all_y:
            room_width = max(all_x) - min(all_x)
            room_length = max(all_y) - min(all_y)
            room_area = max(room_width * room_length, 10.0)
        else:
            room_area = 20.0
        if all_z:
            ceiling_height = max(all_z, default=2.5)
            ceiling_height = max(ceiling_height, 2.5)
        else:
            ceiling_height = 2.5
        return room_area, ceiling_height

    def get_center_lights(self) -> List[LightVertex]:
        return [v for v in self.graph.vertices if
                isinstance(v, LightVertex) and getattr(v, 'light_type', 'center') == 'center']

    def get_furniture_lights(self) -> List[LightVertex]:
        return [v for v in self.graph.vertices if
                isinstance(v, LightVertex) and getattr(v, 'light_type', 'center') == 'furniture']

    def get_obstacles(self) -> List[ObstanceVertex]:
        return [v for v in self.graph.vertices if isinstance(v, ObstanceVertex)]

    def get_furniture_obstacles(self) -> List[ObstanceVertex]:
        furniture_obstacles = []
        for vertex in self.graph.vertices:
            if isinstance(vertex, ObstanceVertex):
                element_type = getattr(vertex, 'element_type', '').lower()
                if any(ftype in element_type for ftype in ['table', 'desk', 'sofa', 'chair', 'counter']):
                    furniture_obstacles.append(vertex)
        return furniture_obstacles

    def get_reflection_surfaces(self) -> List[ObstanceVertex]:
        return [v for v in self.graph.vertices if
                isinstance(v, ObstanceVertex) and getattr(v, 'reflection_factor', 0) > 0.05]

    def calculate_aesthetic_score(self, lights: List[LightVertex]) -> float:
        """בדיקה רק של מרחק מנורות מרכז מול ריהוט"""

        center_lights = lights  # המנורות שנבדקות (מרכזיות)
        furniture_lights = self.furniture_lights

        if not furniture_lights:
            return 1.0

        # ב מרחקים: מנורת מרכז ← → מנורת ריהוט
        min_center_to_furniture = float('inf')

        for center_light in center_lights:
            for furniture_light in furniture_lights:
                distance = self.calculate_distance_2d(center_light.point, furniture_light.point)
                min_center_to_furniture = min(min_center_to_furniture, distance)

        # עונש  על קרבה מרכז-ריהוט
        if min_center_to_furniture < 0.8:
            return 0.1
        elif min_center_to_furniture < 1.2:
            return 0.5
        elif min_center_to_furniture < 1.5:
            return 0.8
        else:
            return 1.0
