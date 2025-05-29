# BuildGraph.py - גרסה מתוקנת עם זיהוי חדרים אמיתי
import json
import os
import logging
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from models import Graph, Point3D, LightVertex, ObstanceVertex, Edge, Vertex
import math

# ייבוא האופטימיזר
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
algorithm_dir = os.path.join(current_dir, 'Algorithm')
if algorithm_dir not in sys.path:
    sys.path.append(algorithm_dir)

from ShadowOptimizer import ShadowOptimizer

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class BuildGraph:
    def __init__(self, config=None):
        """
        אתחול מחלקת BuildGraph
        """
        logger.debug("BuildGraph initialized")

    def build_graph_from_json(self, json_path: str) -> Graph:
        logger.debug("Starting build_graph_from_json with path: %s", json_path)

        if not os.path.exists(json_path):
            logger.error("JSON file does not exist: %s", json_path)
            return Graph()

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_content = f.read()
                logger.debug("JSON file content length: %d", len(json_content))
                json_array = json.loads(json_content)
                logger.debug("JSON parsed successfully, array length: %d", len(json_array))
        except Exception as e:
            logger.error("Error reading/parsing JSON file: %s", str(e))
            return Graph()

        if not json_array or len(json_array) < 4:
            logger.error("JSON data is not valid or too short: %d elements", len(json_array) if json_array else 0)
            return Graph()

        try:
            recommended_lux = float(json_array[0].get("RecommendedLux", 300)) if len(json_array) > 0 and isinstance(
                json_array[0], dict) else 300
            room_type = json_array[1].get("RoomType", "bedroom") if len(json_array) > 1 and isinstance(json_array[1],
                                                                                                       dict) else "bedroom"
            ceiling_height_value = json_array[2].get("RoomHeight", 2.5) if len(json_array) > 2 and isinstance(
                json_array[2], dict) else 2.5
            ceiling_height = float(ceiling_height_value) if ceiling_height_value else 2.5
            room_area_value = json_array[3].get("RoomArea", 20.0) if len(json_array) > 3 and isinstance(json_array[3],
                                                                                                        dict) else 20.0
            room_area = float(room_area_value) if room_area_value else 20.0
        except Exception as e:
            logger.error("Error extracting basic room properties: %s", str(e))
            recommended_lux = 300
            room_type = "bedroom"
            ceiling_height = 2.5
            room_area = 20.0

        elements = json_array[4:] if len(json_array) > 4 else []
        logger.debug("Extracted %d elements", len(elements))

        graph = Graph()
        logger.debug("Created empty graph")

        # **זיהוי חדרים נפרדים - תיקון מרכזי!**
        try:
            rooms = self.identify_separate_rooms(elements, room_area, ceiling_height)
            logger.debug("🏠 Identified %d separate rooms", len(rooms))

            # יצירת מנורות מרכזיות לכל חדר
            for i, room in enumerate(rooms):
                room_center = room['center']
                room_lumens = self.calculate_lumens(room['area'], recommended_lux)

                center_light = LightVertex(
                    room_center,
                    recommended_lux,
                    room_lumens,
                    target_id=None,
                    light_type="center"
                )
                center_light.room_id = f"room_{i}"
                graph.add_vertex(center_light)

                logger.debug("✅ Added CENTER light for room %d at (%f, %f, %f)",
                             i, room_center.x, room_center.y, room_center.z)

                if i == 0:
                    graph.set_center(room_center)

        except Exception as e:
            logger.error("Error identifying rooms: %s", str(e))
            # חדר ברירת מחדל
            default_center = Point3D(0, 0, ceiling_height - 0.5)
            default_light = LightVertex(default_center, recommended_lux,
                                        self.calculate_lumens(room_area, recommended_lux),
                                        None, "center")
            default_light.room_id = "room_0"
            graph.add_vertex(default_light)
            graph.set_center(default_center)

            rooms = [{'center': default_center, 'area': room_area, 'elements': [], 'bounds': None}]

        # הוספת כל האלמנטים לגרף עם room_id
        furniture_elements = []
        try:
            for i, element in enumerate(elements):
                try:
                    logger.debug("Processing element %d: %s", i, element)
                    self.add_element(graph, element)

                    if self.is_require_light_fixed(element):
                        logger.debug("Element %d requires light", i)

                        # **הקצאת החדר הקרוב ביותר לריהוט**
                        element_room_id = self.assign_element_to_room(element, rooms)

                        furniture_light = self.add_light_above_element(graph, element, room_type, ceiling_height,
                                                                       recommended_lux)
                        if furniture_light:
                            furniture_light.room_id = element_room_id
                            furniture_elements.append((element, element_room_id))
                            logger.debug("🪑 Assigned furniture light to %s", element_room_id)

                except Exception as e:
                    logger.error("Error processing element %d: %s", i, str(e))
        except Exception as e:
            logger.error("Error iterating through elements: %s", str(e))

        logger.debug("Graph building completed with %d vertices and %d edges",
                     len(graph.vertices), len(graph.edges))

        # הצגת הגרף לפני האופטימיזציה
        try:
            self.visualize_graph(graph, f"תכנית תאורה לפני אופטימיזציה - {room_type}")
        except Exception as e:
            logger.warning("Could not display graph visualization: %s", str(e))

        # **אופטימיזציה מתוקנת עם שמירה על הגרף**
        try:
            logger.debug("🔬 מתחיל אופטימיזציה מתוקנת...")

            # הכנת המידע לאופטימיזר
            rooms_info, elements_by_room = self.prepare_rooms_data_for_optimizer(rooms, elements, room_type,
                                                                                 recommended_lux)

            logger.debug(f"🏠 הוכן מידע על {len(rooms_info)} חדרים לאופטימיזר")

            # יצירת האופטימיזר ואופטימיזציה
            optimizer = ShadowOptimizer(graph, recommended_lux)
            optimizer.set_rooms_info(rooms_info, elements_by_room)
            optimized_lights = optimizer.optimize_lighting_by_rooms()

            logger.debug(f"🔬 האופטימיזציה החזירה: {len(optimized_lights)} מנורות")

            # **תיקון: עדכון המנורות המרכזיות במקום במקום מחיקה**
            if optimized_lights:
                self.update_center_lights_in_graph(graph, optimized_lights)
                logger.debug("✅ עדכון מנורות מרכזיות הושלם בלי לפגוע בקשתות")

            # הצגת תוצאות האופטימיזציה
            try:
                self.visualize_graph(graph, f"תכנית תאורה אחרי אופטימיזציה מלאה - {room_type}")
            except Exception as e:
                logger.warning("Could not display optimized graph: %s", str(e))

        except Exception as e:
            logger.error(f"❌ שגיאה באופטימיזציה: {str(e)}")

        logger.debug(f"מחזיר גרף עם {len(graph.vertices)} צמתים ו-{len(graph.edges)} קשתות")
        return graph

    def identify_separate_rooms(self, elements, default_area=20.0, ceiling_height=2.5):
        """🏠 זיהוי חדרים נפרדים על פי קירות - תיקון מרכזי!"""
        rooms = []

        try:
            # איסוף כל הקירות
            walls = []
            for element in elements:
                if isinstance(element, dict):
                    element_type = element.get('ElementType', '').lower()
                    if 'קיר' in element_type or 'wall' in element_type:
                        walls.append(element)

            logger.debug(f"🧱 נמצאו {len(walls)} קירות")

            if len(walls) == 0:
                logger.debug("⚠️ אין קירות - יוצר חדר ברירת מחדל")
                return [{
                    'center': Point3D(0, 0, ceiling_height - 0.5),
                    'area': default_area,
                    'elements': [],
                    'bounds': {'min_x': -2, 'max_x': 2, 'min_y': -2, 'max_y': 2}
                }]

            # **חלוקת קירות לחדרים נפרדים לפי מיקום**
            room_groups = self.group_walls_into_rooms(walls)
            logger.debug(f"🏠 חולקו הקירות ל-{len(room_groups)} קבוצות חדרים")

            # יצירת חדר לכל קבוצה
            for i, wall_group in enumerate(room_groups):
                logger.debug(f"   📐 מעבד חדר {i} עם {len(wall_group)} קירות")

                room_bounds = self.calculate_room_bounds_from_walls_improved(wall_group)

                room_center = Point3D(
                    (room_bounds['min_x'] + room_bounds['max_x']) / 2,
                    (room_bounds['min_y'] + room_bounds['max_y']) / 2,
                    ceiling_height - 0.5
                )

                room_area = ((room_bounds['max_x'] - room_bounds['min_x']) *
                             (room_bounds['max_y'] - room_bounds['min_y']))

                rooms.append({
                    'center': room_center,
                    'area': max(room_area, default_area),
                    'elements': wall_group,
                    'bounds': room_bounds
                })

                logger.debug(f"   ✅ חדר {i}: מרכז=({room_center.x:.1f},{room_center.y:.1f}), שטח={room_area:.1f}")

        except Exception as e:
            logger.error("Error in identify_separate_rooms: %s", str(e))
            rooms = [{
                'center': Point3D(0, 0, ceiling_height - 0.5),
                'area': default_area,
                'elements': [],
                'bounds': {'min_x': -2, 'max_x': 2, 'min_y': -2, 'max_y': 2}
            }]

        return rooms if rooms else [{
            'center': Point3D(0, 0, ceiling_height - 0.5),
            'area': default_area,
            'elements': [],
            'bounds': {'min_x': -2, 'max_x': 2, 'min_y': -2, 'max_y': 2}
        }]

    def group_walls_into_rooms(self, walls):
        """🏠 חלוקת קירות לקבוצות חדרים לפי מיקום גיאוגרפי"""
        if not walls:
            return []

        # אם יש רק כמה קירות - הם כולם חדר אחד
        if len(walls) <= 4:
            logger.debug("🏠 מעט קירות - חדר אחד")
            return [walls]

        try:
            # חישוב מרכזי הקירות
            wall_centers = []
            for wall in walls:
                x = float(wall.get('X', 0) or 0)
                y = float(wall.get('Y', 0) or 0)
                width = float(wall.get('Width', wall.get('width', 0)) or 0)
                length = float(wall.get('Length', wall.get('length', 0)) or 0)

                center_x = x + width / 2
                center_y = y + length / 2
                wall_centers.append((center_x, center_y, wall))

            # **קיבוץ קירות לפי מרחק - אלגוריתם פשוט**
            room_groups = []
            used_walls = set()

            for i, (cx, cy, wall) in enumerate(wall_centers):
                if i in used_walls:
                    continue

                # התחל קבוצה חדשה
                current_group = [wall]
                used_walls.add(i)

                # מצא קירות קרובים (עד 5 מטר)
                max_distance = 5.0

                for j, (cx2, cy2, wall2) in enumerate(wall_centers):
                    if j in used_walls:
                        continue

                    distance = math.sqrt((cx - cx2) ** 2 + (cy - cy2) ** 2)
                    if distance <= max_distance:
                        current_group.append(wall2)
                        used_walls.add(j)

                if len(current_group) >= 2:  # רק קבוצות עם לפחות 2 קירות
                    room_groups.append(current_group)
                    logger.debug(f"   🏠 קבוצת חדר: {len(current_group)} קירות במרכז ({cx:.1f},{cy:.1f})")

            # אם לא נוצרו קבוצות טובות - כל הקירות חדר אחד
            if not room_groups:
                logger.debug("🏠 לא נמצאו קבוצות ברורות - כל הקירות חדר אחד")
                return [walls]

            return room_groups

        except Exception as e:
            logger.error("Error grouping walls into rooms: %s", str(e))
            return [walls]  # ברירת מחדל

    def assign_element_to_room(self, element, rooms):
        """🪑 הקצאת אלמנט ריהוט לחדר הקרוב ביותר"""
        if not rooms or len(rooms) == 1:
            return "room_0"

        try:
            # מיקום האלמנט
            element_x = float(element.get('X', 0) or 0)
            element_y = float(element.get('Y', 0) or 0)
            element_width = float(element.get('Width', element.get('width', 0)) or 0)
            element_length = float(element.get('Length', element.get('length', 0)) or 0)

            element_center_x = element_x + element_width / 2
            element_center_y = element_y + element_length / 2

            # מצא החדר הקרוב ביותר
            closest_room_id = "room_0"
            min_distance = float('inf')

            for i, room in enumerate(rooms):
                room_center = room['center']
                distance = math.sqrt(
                    (element_center_x - room_center.x) ** 2 +
                    (element_center_y - room_center.y) ** 2
                )

                if distance < min_distance:
                    min_distance = distance
                    closest_room_id = f"room_{i}"

            logger.debug(f"🪑 אלמנט ב-({element_center_x:.1f},{element_center_y:.1f}) הוקצה ל-{closest_room_id}")
            return closest_room_id

        except Exception as e:
            logger.error("Error assigning element to room: %s", str(e))
            return "room_0"

    def prepare_rooms_data_for_optimizer(self, rooms, elements, room_type, recommended_lux):
        """הכנת נתונים מובנים לאופטימיזר"""
        rooms_info = {}
        elements_by_room = {}

        for i, room in enumerate(rooms):
            room_id = f"room_{i}"

            rooms_info[room_id] = {
                "RoomType": room_type,
                "RecommendedLux": recommended_lux,
                "RoomArea": room['area'],
                "CenterX": room['center'].x,
                "CenterY": room['center'].y
            }

            elements_by_room[room_id] = room['elements']

        return rooms_info, elements_by_room

    def update_center_lights_in_graph(self, graph, optimized_lights):
        """🔧 עדכון מנורות מרכזיות בגרף בלי לפגוע בקשתות"""
        try:
            # מצא את האינדקסים של המנורות המרכזיות הישנות
            center_light_indices = []
            for i, vertex in enumerate(graph.vertices):
                if isinstance(vertex, LightVertex) and getattr(vertex, 'light_type', 'center') == 'center':
                    center_light_indices.append(i)

            logger.debug(f"🔧 נמצאו {len(center_light_indices)} מנורות מרכזיות ישנות לעדכון")

            # עדכן את המנורות הישנות במקום
            optimized_center_lights = [light for light in optimized_lights
                                       if isinstance(light, LightVertex) and getattr(light, 'light_type',
                                                                                     'center') == 'center']

            for i, old_index in enumerate(center_light_indices):
                if i < len(optimized_center_lights):
                    # החלף את המנורה הישנה בחדשה
                    graph.vertices[old_index] = optimized_center_lights[i]
                    logger.debug(f"🔧 עודכנה מנורה מרכזית באינדקס {old_index}")

            # אם יש יותר מנורות מאופטמות מאשר ישנות - הוסף את הנוספות
            if len(optimized_center_lights) > len(center_light_indices):
                for j in range(len(center_light_indices), len(optimized_center_lights)):
                    graph.add_vertex(optimized_center_lights[j])
                    logger.debug(f"🔧 נוספה מנורה מרכזית חדשה")

            logger.debug("✅ עדכון מנורות מרכזיות הושלם בהצלחה")

        except Exception as e:
            logger.error(f"❌ שגיאה בעדכון מנורות מרכזיות: {str(e)}")

    def calculate_room_bounds_from_walls_improved(self, walls):
        """חישוב גבולות החדר מקירות"""
        if not walls:
            return {'min_x': -2, 'max_x': 2, 'min_y': -2, 'max_y': 2}

        try:
            all_x_coords = []
            all_y_coords = []

            for wall in walls:
                if isinstance(wall, dict):
                    x = float(wall.get('X', 0) or 0)
                    y = float(wall.get('Y', 0) or 0)
                    width = float(wall.get('Width', wall.get('width', 0)) or 0)
                    length = float(wall.get('Length', wall.get('length', 0)) or 0)

                    all_x_coords.extend([x, x + width])
                    all_y_coords.extend([y, y + length])

            if all_x_coords and all_y_coords:
                min_x, max_x = min(all_x_coords), max(all_x_coords)
                min_y, max_y = min(all_y_coords), max(all_y_coords)

                margin = 0.3
                bounds = {
                    'min_x': min_x + margin,
                    'max_x': max_x - margin,
                    'min_y': min_y + margin,
                    'max_y': max_y - margin
                }

                return bounds

        except Exception as e:
            logger.error("Error calculating room bounds from walls: %s", str(e))

        return {'min_x': -2, 'max_x': 2, 'min_y': -2, 'max_y': 2}

    def is_require_light_fixed(self, element: dict) -> bool:
        """בדיקה מתוקנת - רק פריטים ספציפיים דורשים תאורה"""
        if not isinstance(element, dict):
            return False

        furniture_requiring_light = [
            "table", "שולחן",
            "desk", "שולחן עבודה",
            "counter", "דלפק",
            "workbench",
            "kitchen counter",
            "sofa", "ספה", "ספת",
            "couch"
        ]

        element_type = element.get("ElementType", "").lower()
        element_name = element.get("Name", "").lower()

        requires_light = (
                any(furniture_type in element_type for furniture_type in furniture_requiring_light) or
                any(furniture_type in element_name for furniture_type in furniture_requiring_light)
        )

        return requires_light

    def add_element(self, g: Graph, e: dict):
        """הוספת אלמנט לגרף"""
        if not isinstance(e, dict):
            logger.warning("Element is not a dictionary, skipping: %s", e)
            return

        try:
            x = float(e.get("X", 0) or 0)
            y = float(e.get("Y", 0) or 0)
            z = float(e.get("Z", 0) or 0)

            width = float(e.get("Width", e.get("width", 0)) or 0)
            length = float(e.get("Length", e.get("length", 0)) or 0)
            height = float(e.get("Height", e.get("height", 0)) or 0)

            dummy_id = 0
            if "ElementId" in e:
                try:
                    dummy_id = int(e.get("ElementId"))
                except (ValueError, TypeError):
                    pass

            points = [
                Point3D(x, y, z),
                Point3D(x + width, y, z),
                Point3D(x, y + length, z),
                Point3D(x + width, y + length, z),
                Point3D(x, y, z + height),
                Point3D(x + width, y, z + height),
                Point3D(x, y + length, z + height),
                Point3D(x + width, y + length, z + height),
            ]

            vertex_ids = []
            for pt in points:
                vertex_id = g.add_vertex(ObstanceVertex(dummy_id, pt, 0, 0))
                vertex_ids.append(vertex_id)

            edges = [
                (0, 1, width), (1, 3, length), (3, 2, width), (2, 0, length),
                (4, 5, width), (5, 7, length), (7, 6, width), (6, 4, length),
                (0, 4, height), (1, 5, height), (2, 6, height), (3, 7, height)
            ]

            for i, j, l in edges:
                if i < len(vertex_ids) and j < len(vertex_ids):
                    g.add_edge(Edge(vertex_ids[i], vertex_ids[j], 0, l))

            reflection_factor = float(e.get("ReflectionFactor", 0) or 0)
            if reflection_factor > 0:
                normal_x, normal_y, normal_z = 0, -1, 0
                d = float(e.get("ReflectionRange", 1.0) or 1.0)
                face_center = Point3D(x + width / 2, y, z + height / 2)

                for dist in [i * 0.5 for i in range(1, int(d / 0.5) + 1)]:
                    p = Point3D(face_center.x + normal_x * dist,
                                face_center.y + normal_y * dist,
                                face_center.z + normal_z * dist)
                    infl_v = g.add_vertex(Vertex(p))
                    g.add_edge(Edge(vertex_ids[0], infl_v, reflection_factor, dist))
        except Exception as e:
            logger.error("Error in add_element: %s", str(e))

    def add_light_above_element(self, graph: Graph, element: dict, room_type: str, ceiling_height: float,
                                recommended_lux: float):
        """הוספת מנורה מעל אלמנט ריהוט - מחזירה את המנורה"""
        if not isinstance(element, dict):
            logger.warning("Cannot add light above non-dict element: %s", element)
            return None

        try:
            width = float(element.get("Width", element.get("width", 0)) or 0)
            length = float(element.get("Length", element.get("length", 0)) or 0)

            center_x = float(element.get("X", 0) or 0) + width / 2
            center_y = float(element.get("Y", 0) or 0) + length / 2

            element_type = element.get("ElementType", "unknown").lower()

            light_height_offset = 0.5
            element_z = float(element.get("Z", 0) or 0)
            element_height = float(element.get("Height", element.get("height", 0)) or 0)

            light_height = min(element_z + element_height + light_height_offset, ceiling_height)
            point = Point3D(center_x, center_y, light_height)

            if any(desk_type in element_type for desk_type in ["desk", "שולחן עבודה", "workbench"]):
                light_lux = recommended_lux * 1.5
            elif any(counter_type in element_type for counter_type in ["counter", "דלפק"]):
                light_lux = recommended_lux * 1.3
            elif any(sofa_type in element_type for sofa_type in ["sofa", "ספה", "couch"]):
                light_lux = recommended_lux * 0.8
            else:
                light_lux = recommended_lux

            element_area = width * length if width > 0 and length > 0 else 2.0
            lumens = self.calculate_lumens(element_area, light_lux)
            element_id = element.get("ID", element.get("ElementId", 0))

            furniture_light = LightVertex(
                point,
                light_lux,
                lumens,
                element_id,
                light_type="furniture"
            )

            graph.add_vertex(furniture_light)
            return furniture_light

        except Exception as e:
            logger.error("Error adding light above element: %s", str(e))
            return None

    def calculate_lumens(self, area, lux=300, safety=1.2):
        """חישוב לומן נדרש לפי שטח ועוצמת תאורה"""
        try:
            area = float(area) if area else 0
            return area * lux * safety
        except Exception as e:
            logger.error("Error calculating lumens: %s", str(e))
            return 0

    def visualize_graph(self, graph: Graph, title="תכנית קומה"):
        """הצגת הגרף - מבט עליון ותלת-ממדי"""
        if not graph.vertices:
            logger.warning("Graph is empty, nothing to visualize")
            return

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

        self.plot_2d_view(graph, ax1, f"{title} - מבט עליון")

        ax2.remove()
        ax2 = fig.add_subplot(122, projection='3d')
        self.plot_3d_view(graph, ax2, f"{title} - תלת-ממד")

        plt.tight_layout()
        plt.show()

    def plot_2d_view(self, graph: Graph, ax, title):
        """הצגה דו-ממדית (מבט עליון)"""
        walls_x, walls_y = [], []
        center_lights_x, center_lights_y = [], []
        furniture_lights_x, furniture_lights_y = [], []
        furniture_x, furniture_y = [], []
        other_x, other_y = [], []

        for vertex in graph.vertices:
            x, y = vertex.point.x, vertex.point.y

            if isinstance(vertex, LightVertex):
                if getattr(vertex, 'light_type', 'center') == "center":
                    center_lights_x.append(x)
                    center_lights_y.append(y)
                else:
                    furniture_lights_x.append(x)
                    furniture_lights_y.append(y)
            elif hasattr(vertex, 'required_lux') and vertex.required_lux > 0:
                furniture_x.append(x)
                furniture_y.append(y)
            elif hasattr(vertex, 'reflection_factor') and vertex.reflection_factor > 0.05:
                walls_x.append(x)
                walls_y.append(y)
            else:
                other_x.append(x)
                other_y.append(y)

        if walls_x:
            ax.scatter(walls_x, walls_y, c='blue', s=100, marker='s', label='קירות', alpha=0.7)
        if center_lights_x:
            ax.scatter(center_lights_x, center_lights_y, c='red', s=200, marker='*', label='תאורה מרכזית', alpha=0.9)
        if furniture_lights_x:
            ax.scatter(furniture_lights_x, furniture_lights_y, c='orange', s=120, marker='*', label='תאורת ריהוט',
                       alpha=0.8)
        if furniture_x:
            ax.scatter(furniture_x, furniture_y, c='green', s=120, marker='o', label='ריהוט', alpha=0.7)
        if other_x:
            ax.scatter(other_x, other_y, c='gray', s=80, marker='.', label='אחר', alpha=0.5)

        # הצגת קשתות
        for edge in graph.edges:
            if edge.start < len(graph.vertices) and edge.end < len(graph.vertices):
                start_vertex = graph.vertices[edge.start]
                end_vertex = graph.vertices[edge.end]

                if not isinstance(start_vertex, LightVertex) and not isinstance(end_vertex, LightVertex):
                    ax.plot([start_vertex.point.x, end_vertex.point.x],
                            [start_vertex.point.y, end_vertex.point.y],
                            'b-', alpha=0.6, linewidth=1)

        ax.set_xlabel('X (מטר)')
        ax.set_ylabel('Y (מטר)')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')

    def plot_3d_view(self, graph: Graph, ax, title):
        """הצגה תלת-ממדית"""
        for vertex in graph.vertices:
            x, y, z = vertex.point.x, vertex.point.y, vertex.point.z

            if isinstance(vertex, LightVertex):
                if getattr(vertex, 'light_type', 'center') == "center":
                    ax.scatter(x, y, z, c='red', s=200, marker='*', alpha=0.9)
                else:
                    ax.scatter(x, y, z, c='orange', s=120, marker='*', alpha=0.8)
            elif hasattr(vertex, 'required_lux') and vertex.required_lux > 0:
                ax.scatter(x, y, z, c='green', s=120, marker='o', alpha=0.7)
            elif hasattr(vertex, 'reflection_factor') and vertex.reflection_factor > 0.05:
                ax.scatter(x, y, z, c='blue', s=100, marker='s', alpha=0.7)
            else:
                ax.scatter(x, y, z, c='gray', s=80, marker='.', alpha=0.5)

        # הצגת קשתות
        for edge in graph.edges:
            if edge.start < len(graph.vertices) and edge.end < len(graph.vertices):
                start_vertex = graph.vertices[edge.start]
                end_vertex = graph.vertices[edge.end]

                ax.plot([start_vertex.point.x, end_vertex.point.x],
                        [start_vertex.point.y, end_vertex.point.y],
                        [start_vertex.point.z, end_vertex.point.z],
                        'b-', alpha=0.4, linewidth=1)

        ax.set_xlabel('X (מטר)')
        ax.set_ylabel('Y (מטר)')
        ax.set_zlabel('Z (מטר)')
        ax.set_title(title)