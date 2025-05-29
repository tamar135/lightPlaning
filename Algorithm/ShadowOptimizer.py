# ShadowOptimizer.py - תיקון לטיפול בחדרים נפרדים
import math
import logging
from typing import List, Tuple, Dict
from models import Point3D, LightVertex, ObstanceVertex, Graph

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

        # פרמטרי פיזיקה
        self.light_efficiency = 80  # לומן לוואט עבור LED
        self.cos_angle_threshold = 0.1  # זווית מקסימלית לאור ישיר

        # **מידע על חדרים - חדש!**
        self.rooms_info = {}
        self.elements_by_room = {}

    def set_rooms_info(self, rooms_info: Dict, elements_by_room: Dict):
        """הגדרת מידע על החדרים והאלמנטים בכל חדר"""
        self.rooms_info = rooms_info
        self.elements_by_room = elements_by_room
        logger.debug(f"🏠 הוגדר מידע על {len(rooms_info)} חדרים")

    def optimize_lighting_by_rooms(self) -> List[LightVertex]:
        """אופטימיזציה נפרדת לכל חדר - פונקציה חדשה מהותית!"""
        logger.debug("🔬 מתחיל אופטימיזציה מבוססת חדרים נפרדים")

        optimized_lights = []

        # קיבוץ מנורות מרכזיות לפי חדרים
        lights_by_room = self.group_lights_by_room()

        logger.debug(f"🏠 נמצאו מנורות ב-{len(lights_by_room)} חדרים")

        # אופטימיזציה לכל חדר בנפרד
        for room_id, room_lights in lights_by_room.items():
            logger.debug(f"\n🏠 מאפטם חדר {room_id} עם {len(room_lights)} מנורות מרכזיות")

            # מידע על החדר הנוכחי
            room_info = self.rooms_info.get(room_id, {})
            room_type = room_info.get("RoomType", "bedroom")
            recommended_lux = room_info.get("RecommendedLux", self.required_lux)

            # מציאת אלמנטים בחדר הזה
            room_elements = self.get_elements_for_room(room_id)
            room_obstacles = self.get_obstacles_for_room(room_id)

            # אופטימיזציה עבור כל מנורה מרכזית בחדר
            for center_light in room_lights:
                logger.debug(f"   🔍 מאפטם מנורה מרכזית בחדר {room_id}")

                # מציאת נקודות קריטיות בחדר הזה בלבד
                room_critical_points = self.find_room_critical_points_for_room(center_light, room_elements,
                                                                               room_obstacles)

                # הגדרת גבולות החדר
                room_bounds = self.calculate_room_bounds_for_room(room_info, room_elements)

                # אופטימיזציה של המנורה המרכזית
                best_lights_for_room = self.optimize_center_light_with_physics_for_room(
                    center_light, room_critical_points, room_bounds, recommended_lux, room_id
                )

                optimized_lights.extend(best_lights_for_room)
                logger.debug(f"   ✅ חדר {room_id}: {len(best_lights_for_room)} מנורות מאופטמות")

        # הוספת מנורות ריהוט (נשמרות כמות שהן)
        furniture_lights_with_room = self.get_furniture_lights_with_room_id()
        optimized_lights.extend(furniture_lights_with_room)

        logger.debug(f"\n🎯 סיום אופטימיזציה לפי חדרים: {len(optimized_lights)} מנורות כולל ריהוט")
        return optimized_lights

    def group_lights_by_room(self) -> Dict[str, List[LightVertex]]:
        """קיבוץ מנורות מרכזיות לפי חדרים"""
        lights_by_room = {}

        for light in self.center_lights:
            room_id = getattr(light, 'room_id', 'default_room')
            if room_id not in lights_by_room:
                lights_by_room[room_id] = []
            lights_by_room[room_id].append(light)

        return lights_by_room

    def get_elements_for_room(self, room_id: str) -> List[dict]:
        """מציאת אלמנטים השייכים לחדר ספציפי"""
        return self.elements_by_room.get(room_id, [])

    def get_obstacles_for_room(self, room_id: str) -> List[ObstanceVertex]:
        """מציאת מכשולים השייכים לחדר ספציפי"""
        room_obstacles = []
        for obstacle in self.obstacles:
            obstacle_room_id = getattr(obstacle, 'room_id', 'default_room')
            if obstacle_room_id == room_id:
                room_obstacles.append(obstacle)
        return room_obstacles

    def get_furniture_lights_with_room_id(self) -> List[LightVertex]:
        """מציאת מנורות ריהוט עם room_id"""
        furniture_lights = []
        for light in self.furniture_lights:
            # ודא שלמנורת הריהוט יש room_id
            if not hasattr(light, 'room_id'):
                light.room_id = 'default_room'
            furniture_lights.append(light)
        return furniture_lights

    def find_room_critical_points_for_room(self, center_light: LightVertex, room_elements: List[dict],
                                           room_obstacles: List[ObstanceVertex]) -> List[Point3D]:
        """מציאת נקודות קריטיות בחדר ספציפי בלבד"""
        critical_points = []

        # נקודות מריהוט בחדר הזה
        for obstacle in room_obstacles:
            required_lux = getattr(obstacle, 'required_lux', 0)
            if required_lux > 0:
                critical_points.append(obstacle.point)
                critical_points.extend(self.generate_points_around_furniture(obstacle))

        # אם אין ריהוט, צור רשת נקודות קטנה בחדר
        if not critical_points:
            critical_points = self.generate_room_grid_small(center_light.point, 3.0)

        logger.debug(f"     נמצאו {len(critical_points)} נקודות קריטיות בחדר")
        return critical_points

    def calculate_room_bounds_for_room(self, room_info: dict, room_elements: List[dict]) -> dict:
        """חישוב גבולות החדר הספציפי"""
        # אם יש מידע מפורש על החדר
        if room_info:
            center_x = room_info.get("CenterX", 0)
            center_y = room_info.get("CenterY", 0)

            # הערכת גודל החדר מהשטח
            area = room_info.get("RoomArea", 20)
            estimated_side = math.sqrt(area)

            return {
                'min_x': center_x - estimated_side / 2,
                'max_x': center_x + estimated_side / 2,
                'min_y': center_y - estimated_side / 2,
                'max_y': center_y + estimated_side / 2
            }

        # אחרת, חשב מהאלמנטים
        if room_elements:
            all_x = []
            all_y = []

            for element in room_elements:
                x = element.get("X", 0)
                y = element.get("Y", 0)
                width = element.get("Width", 0)
                length = element.get("Length", 0)

                all_x.extend([x, x + width])
                all_y.extend([y, y + length])

            if all_x and all_y:
                margin = 0.3
                return {
                    'min_x': min(all_x) + margin,
                    'max_x': max(all_x) - margin,
                    'min_y': min(all_y) + margin,
                    'max_y': max(all_y) - margin
                }

        # ברירת מחדל
        return {'min_x': -2, 'max_x': 2, 'min_y': -2, 'max_y': 2}

    def optimize_center_light_with_physics_for_room(self, original_light: LightVertex, critical_points: List[Point3D],
                                                    room_bounds: dict, recommended_lux: float, room_id: str) -> List[
        LightVertex]:
        """אופטימיזציה של מנורה מרכזית עבור חדר ספציפי"""
        center = original_light.point
        ceiling_height = center.z + 0.3

        # 4 תצורות למנורות מרכזיות
        configurations = [
            ("מנורה מרכזית אחת", self.config_single_center(center, ceiling_height, room_bounds, room_id)),
            ("2 מנורות מרכזיות", self.config_dual_linear(center, ceiling_height, room_bounds, room_id)),
            ("3 מנורות מרכזיות", self.config_triangle(center, ceiling_height, room_bounds, room_id)),
            ("4 מנורות מרכזיות", self.config_square(center, ceiling_height, room_bounds, room_id))
        ]

        best_lights = None
        best_score = float('inf')
        best_name = ""

        for name, config in configurations:
            lights = config['lights']

            # חישוב ציון פיזיקלי - משלב צל + עוצמת תאורה
            physics_score = self.calculate_combined_physics_score_for_room(lights, critical_points, room_id)
            aesthetic_score = config['aesthetic_score']

            # ציון משולב: פיזיקה (85%) + אסתטיקה (15%)
            total_score = physics_score * 0.85 + aesthetic_score * 0.15

            logger.debug(
                f"     {name} (חדר {room_id}): פיזיקה={physics_score:.2f}, אסתטיקה={aesthetic_score:.2f}, ציון={total_score:.2f}")

            if total_score < best_score:
                best_score = total_score
                best_lights = lights
                best_name = name

        logger.debug(f"   🏆 נבחר לחדר {room_id}: {best_name}")
        return best_lights if best_lights else [original_light]

    def calculate_combined_physics_score_for_room(self, lights: List[LightVertex], critical_points: List[Point3D],
                                                  room_id: str) -> float:
        """חישוב ציון פיזיקלי משולב עבור חדר ספציפי"""
        # ציון תאורה
        illumination_score = self.calculate_illumination_adequacy_score(lights, critical_points)

        # ציון צללים - רק מריהוט בחדר הזה
        room_furniture = self.get_furniture_for_room(room_id)
        shadow_score = self.calculate_shadow_score_for_room(lights, room_furniture)

        # ציון מרחק מנורות - רק ממנורות ריהוט בחדר הזה
        room_furniture_lights = [light for light in self.furniture_lights if
                                 getattr(light, 'room_id', 'default_room') == room_id]
        distance_penalty = self.calculate_light_proximity_penalty_for_room(lights, room_furniture_lights)

        # משקל יחסי
        combined_score = illumination_score * 0.6 + shadow_score * 0.25 + distance_penalty * 0.15

        return combined_score

    def get_furniture_for_room(self, room_id: str) -> List[ObstanceVertex]:
        """מציאת ריהוט עבור חדר ספציפי"""
        room_furniture = []
        for obstacle in self.obstacles:
            obstacle_room_id = getattr(obstacle, 'room_id', 'default_room')
            if obstacle_room_id == room_id and getattr(obstacle, 'required_lux', 0) > 0:
                room_furniture.append(obstacle)
        return room_furniture

    def calculate_shadow_score_for_room(self, lights: List[LightVertex], room_furniture: List[ObstanceVertex]) -> float:
        """חישוב ציון צללים עבור חדר ספציפי"""
        if not room_furniture:
            return 0

        shadow_area = self.calculate_vectorial_shadow_area(lights, room_furniture)
        room_area = 25.0  # הנחה לשטח חדר ממוצע
        normalized_shadow_score = min(shadow_area / room_area, 1.0)

        return normalized_shadow_score

    def calculate_light_proximity_penalty_for_room(self, center_lights: List[LightVertex],
                                                   room_furniture_lights: List[LightVertex]) -> float:
        """חישוב עונש על מנורות מרכזיות קרובות מידי למנורות ריהוט באותו חדר"""
        if not center_lights or not room_furniture_lights:
            return 0

        min_aesthetic_distance = 1.0
        total_penalty = 0
        violations = 0

        for center_light in center_lights:
            if getattr(center_light, 'light_type', 'center') == "center":
                for furniture_light in room_furniture_lights:
                    distance = self.calculate_distance(center_light.point, furniture_light.point)

                    if distance < min_aesthetic_distance:
                        penalty = ((min_aesthetic_distance - distance) / min_aesthetic_distance) ** 2
                        total_penalty += penalty
                        violations += 1

        avg_penalty = total_penalty / max(len(center_lights) * len(room_furniture_lights), 1)
        return avg_penalty

    # **תצורות תאורה מעודכנות עם room_id**
    def config_single_center(self, center: Point3D, ceiling_height: float, room_bounds: dict, room_id: str):
        """מנורה אחת במרכז החדר"""
        safe_x = max(room_bounds['min_x'], min(room_bounds['max_x'], center.x))
        safe_y = max(room_bounds['min_y'], min(room_bounds['max_y'], center.y))

        light = LightVertex(
            Point3D(safe_x, safe_y, ceiling_height - 0.3),
            lux=400,
            lumens=12000,
            target_id=None,
            light_type="center"
        )
        light.room_id = room_id  # **הוספת room_id**

        return {
            'lights': [light],
            'aesthetic_score': 1.0
        }

    def config_dual_linear(self, center: Point3D, ceiling_height: float, room_bounds: dict, room_id: str):
        """2 מנורות בקו"""
        offset = 1.5

        x1 = max(room_bounds['min_x'], min(room_bounds['max_x'], center.x - offset))
        x2 = max(room_bounds['min_x'], min(room_bounds['max_x'], center.x + offset))
        safe_y = max(room_bounds['min_y'], min(room_bounds['max_y'], center.y))

        lights = []
        for x in [x1, x2]:
            light = LightVertex(
                Point3D(x, safe_y, ceiling_height - 0.3),
                lux=250,
                lumens=7000,
                target_id=None,
                light_type="center"
            )
            light.room_id = room_id  # **הוספת room_id**
            lights.append(light)

        return {
            'lights': lights,
            'aesthetic_score': 0.8
        }

    def config_triangle(self, center: Point3D, ceiling_height: float, room_bounds: dict, room_id: str):
        """3 מנורות במשולש"""
        radius = min(1.2,
                     (room_bounds['max_x'] - room_bounds['min_x']) / 3,
                     (room_bounds['max_y'] - room_bounds['min_y']) / 3)
        angles = [0, 2 * math.pi / 3, 4 * math.pi / 3]

        lights = []
        for angle in angles:
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)

            safe_x = max(room_bounds['min_x'], min(room_bounds['max_x'], x))
            safe_y = max(room_bounds['min_y'], min(room_bounds['max_y'], y))

            light = LightVertex(
                Point3D(safe_x, safe_y, ceiling_height - 0.3),
                lux=200,
                lumens=5000,
                target_id=None,
                light_type="center"
            )
            light.room_id = room_id  # **הוספת room_id**
            lights.append(light)

        return {
            'lights': lights,
            'aesthetic_score': 0.9
        }

    def config_square(self, center: Point3D, ceiling_height: float, room_bounds: dict, room_id: str):
        """4 מנורות בריבוע"""
        offset = min(1.0,
                     (room_bounds['max_x'] - room_bounds['min_x']) / 4,
                     (room_bounds['max_y'] - room_bounds['min_y']) / 4)
        positions = [
            (-offset, -offset), (offset, -offset),
            (offset, offset), (-offset, offset)
        ]

        lights = []
        for dx, dy in positions:
            x = center.x + dx
            y = center.y + dy

            safe_x = max(room_bounds['min_x'], min(room_bounds['max_x'], x))
            safe_y = max(room_bounds['min_y'], min(room_bounds['max_y'], y))

            light = LightVertex(
                Point3D(safe_x, safe_y, ceiling_height - 0.3),
                lux=150,
                lumens=4000,
                target_id=None,
                light_type="center"
            )
            light.room_id = room_id  # **הוספת room_id**
            lights.append(light)

        return {
            'lights': lights,
            'aesthetic_score': 0.95
        }

    # **שאר הפונקציות נשארות זהות - רק עודכנו לטיפול בחדרים נפרדים**

    def get_center_lights(self) -> List[LightVertex]:
        """מציאת כל המנורות המרכזיות"""
        center_lights = []
        for vertex in self.graph.vertices:
            if isinstance(vertex, LightVertex):
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
                light_type = getattr(vertex, 'light_type', 'center')
                if light_type == "furniture":
                    furniture_lights.append(vertex)
        logger.debug(f"נמצאו {len(furniture_lights)} מנורות ריהוט (נשמרות)")
        return furniture_lights

    def get_obstacles(self) -> List[ObstanceVertex]:
        """מציאת כל המכשולים"""
        obstacles = [v for v in self.graph.vertices if isinstance(v, ObstanceVertex)]
        logger.debug(f"נמצאו {len(obstacles)} מכשולים")
        return obstacles

    def get_reflection_surfaces(self) -> List[ObstanceVertex]:
        """מציאת משטחים מחזירי אור"""
        surfaces = []
        for vertex in self.graph.vertices:
            if isinstance(vertex, ObstanceVertex):
                reflection_factor = getattr(vertex, 'reflection_factor', 0)
                if reflection_factor > 0.05:
                    surfaces.append(vertex)
        logger.debug(f"נמצאו {len(surfaces)} משטחים מחזירי אור")
        return surfaces

    def generate_points_around_furniture(self, furniture: ObstanceVertex) -> List[Point3D]:
        """יצירת נקודות בדיקה סביב פריט ריהוט"""
        points = []
        base_point = furniture.point

        offsets = [(0.5, 0, 0), (-0.5, 0, 0), (0, 0.5, 0), (0, -0.5, 0)]

        for dx, dy, dz in offsets:
            points.append(Point3D(
                base_point.x + dx,
                base_point.y + dy,
                base_point.z + dz
            ))

        return points

    def generate_room_grid_small(self, center: Point3D, radius: float) -> List[Point3D]:
        """יצירת רשת נקודות קטנה בחדר"""
        points = []
        step = 1.0

        for x in range(int(-radius / 2), int(radius / 2 + 1), int(step)):
            for y in range(int(-radius / 2), int(radius / 2 + 1), int(step)):
                distance = math.sqrt(x * x + y * y)
                if distance <= radius:
                    points.append(Point3D(
                        center.x + x,
                        center.y + y,
                        0.8
                    ))

        return points

    def calculate_illumination_adequacy_score(self, lights: List[LightVertex], critical_points: List[Point3D]) -> float:
        """חישוב ציון התאמת התאורה לדרישות"""
        total_penalty = 0

        for point in critical_points:
            total_lux = self.calculate_total_illumination_at_point(point, lights)

            if total_lux < self.required_lux:
                penalty = (self.required_lux - total_lux) / self.required_lux
                total_penalty += penalty * penalty
            elif total_lux > self.required_lux * 2:
                penalty = (total_lux - self.required_lux * 2) / self.required_lux
                total_penalty += penalty * 0.5

        return total_penalty / len(critical_points) if critical_points else 0

    def calculate_total_illumination_at_point(self, point: Point3D, lights: List[LightVertex]) -> float:
        """חישוב עוצמת התאורה הכוללת בנקודה"""
        total_lux = 0

        for light in lights:
            direct_lux = self.calculate_direct_illumination_inverse_square(light, point)
            total_lux += direct_lux

        for light in lights:
            reflected_lux = self.calculate_reflected_illumination_lambert(light, point)
            total_lux += reflected_lux

        return total_lux

    def calculate_direct_illumination_inverse_square(self, light: LightVertex, point: Point3D) -> float:
        """חישוב אור ישיר - חוק הריבוע ההפוך"""
        distance = self.calculate_distance(light.point, point)

        if distance < 0.1:
            distance = 0.1

        if self.is_light_blocked(light.point, point):
            return 0

        direct_lux = light.lumens / (4 * math.pi * distance * distance)

        cos_angle = self.calculate_cos_angle_lambert(light.point, point)
        if cos_angle > self.cos_angle_threshold:
            direct_lux *= cos_angle
        else:
            direct_lux = 0

        return direct_lux

    def calculate_reflected_illumination_lambert(self, light: LightVertex, point: Point3D) -> float:
        """חישוב אור מוחזר - חוק למברט"""
        total_reflected = 0

        for surface in self.reflection_surfaces:
            light_to_surface = self.calculate_distance(light.point, surface.point)
            surface_to_point = self.calculate_distance(surface.point, point)

            if light_to_surface < 0.1 or surface_to_point < 0.1:
                continue

            if (self.is_light_blocked(light.point, surface.point) or
                    self.is_light_blocked(surface.point, point)):
                continue

            incident_lux = light.lumens / (4 * math.pi * light_to_surface * light_to_surface)

            cos_incident = self.calculate_cos_angle_lambert(light.point, surface.point)
            cos_reflection = self.calculate_cos_angle_lambert(surface.point, point)

            reflection_factor = getattr(surface, 'reflection_factor', 0.1)

            if cos_incident > 0 and cos_reflection > 0:
                reflected_lux = (incident_lux * cos_incident * cos_reflection *
                                 reflection_factor / (math.pi * surface_to_point * surface_to_point))

                total_reflected += reflected_lux

        return total_reflected

    def calculate_cos_angle_lambert(self, from_point: Point3D, to_point: Point3D) -> float:
        """חישוב קוסינוס הזווית לחוק למברט"""
        dx = to_point.x - from_point.x
        dy = to_point.y - from_point.y
        dz = to_point.z - from_point.z

        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        if distance == 0:
            return 0

        cos_angle = abs(dz) / distance
        return cos_angle

    def calculate_vectorial_shadow_area(self, lights: List[LightVertex], furniture: List[ObstanceVertex]) -> float:
        """חישוב שטח צל וקטורי אמיתי"""
        if not lights or not furniture:
            return 0

        total_shadow_area = 0
        floor_z = 0

        for furniture_vertex in furniture:
            shadow_points = []

            for light in lights:
                light_to_furniture = self.create_vector(light.point, furniture_vertex.point)
                shadow_point = self.project_vector_to_floor(light.point, light_to_furniture, floor_z)

                if shadow_point:
                    shadow_points.append((shadow_point.x, shadow_point.y))

            if len(shadow_points) >= 3:
                furniture_shadow_area = self.calculate_polygon_area(shadow_points)
                total_shadow_area += furniture_shadow_area

        return total_shadow_area

    def is_light_blocked(self, light_pos: Point3D, target_pos: Point3D) -> bool:
        """בדיקה אם יש מכשול בין מקור האור לנקודת היעד"""
        light_height = light_pos.z
        target_height = target_pos.z

        if light_height > 2.0 and target_height < 1.5:
            return False

        return False

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

        if dz >= 0:
            return None

        t = (floor_z - light_pos.z) / dz

        if t < 0:
            return None

        shadow_x = light_pos.x + t * dx
        shadow_y = light_pos.y + t * dy

        return Point3D(shadow_x, shadow_y, floor_z)

    def calculate_polygon_area(self, points: List[Tuple[float, float]]) -> float:
        """חישוב שטח פוליגון בשיטת הנעל"""
        if len(points) < 3:
            return 0

        area = 0
        n = len(points)

        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]

        return abs(area) / 2

    def calculate_distance(self, p1: Point3D, p2: Point3D) -> float:
        """חישוב מרחק אוקלידי בין שתי נקודות"""
        return math.sqrt(
            (p1.x - p2.x) ** 2 +
            (p1.y - p2.y) ** 2 +
            (p1.z - p2.z) ** 2
        )