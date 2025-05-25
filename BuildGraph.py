# BuildGraph.py
import json
import os
import logging
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from models import Graph, Point3D, LightVertex, ObstanceVertex, Edge, Vertex

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
                try:
                    json_content = f.read()
                    logger.debug("JSON file content length: %d", len(json_content))
                    json_array = json.loads(json_content)
                    logger.debug("JSON parsed successfully, array length: %d", len(json_array))
                except json.JSONDecodeError as e:
                    logger.error("Error parsing JSON: %s", e)
                    return Graph()
                except Exception as e:
                    logger.error("Error reading JSON file: %s", str(e))
                    return Graph()
        except Exception as e:
            logger.error("Error opening JSON file: %s", str(e))
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

        # זיהוי חדרים ותכנון תאורה בסיסי
        try:
            rooms = self.identify_rooms(elements, room_area)
            logger.debug("Identified %d rooms", len(rooms))

            for i, room in enumerate(rooms):
                room_center = room['center']
                room_lumens = self.calculate_lumens(room['area'], recommended_lux)

                # **מנורה מרכזית - מסומנת כ"center"**
                center_light = LightVertex(
                    room_center,
                    recommended_lux,
                    room_lumens,
                    target_id=None,
                    light_type="center"  # 🏷️ תג מנורת מרכז
                )
                graph.add_vertex(center_light)
                logger.debug("Added CENTER light for room %d at (%f, %f, %f) with %f lumens",
                             i + 1, room_center.x, room_center.y, room_center.z, room_lumens)

                if i == 0 or room['area'] > rooms[0]['area']:
                    graph.set_center(room_center)

        except Exception as e:
            logger.error("Error identifying rooms and adding center lights: %s", str(e))
            default_center = Point3D(0, 0, ceiling_height - 0.5)
            lumens = self.calculate_lumens(room_area, recommended_lux)

            # **מנורה מרכזית ברירת מחדל**
            default_light = LightVertex(
                default_center,
                recommended_lux,
                lumens,
                target_id=None,
                light_type="center"  # 🏷️ תג מנורת מרכז
            )
            graph.add_vertex(default_light)
            graph.set_center(default_center)

        # הוספת כל האלמנטים לגרף
        try:
            for i, element in enumerate(elements):
                try:
                    logger.debug("Processing element %d: %s", i, element)
                    self.add_element(graph, element)

                    if self.is_require_light(element):
                        logger.debug("Element %d requires light", i)
                        # **מנורה מעל ריהוט - מסומנת כ"furniture"**
                        self.add_light_above_element(graph, element, room_type, ceiling_height, recommended_lux)
                except Exception as e:
                    logger.error("Error processing element %d: %s", i, str(e))
        except Exception as e:
            logger.error("Error iterating through elements: %s", str(e))

        logger.debug("Graph building completed with %d vertices and %d edges",
                     len(graph.vertices), len(graph.edges))

        # **הצגת הגרף לפני האופטימיזציה**
        try:
            self.visualize_graph(graph, f"תכנית תאורה לפני אופטימיזציה - {room_type}")
        except Exception as e:
            logger.warning("Could not display graph visualization: %s", str(e))

        # **הדפסת מצב לפני אופטימיזציה**
        center_lights_before = [v for v in graph.vertices if
                                isinstance(v, LightVertex) and getattr(v, 'light_type', 'center') == "center"]
        furniture_lights_before = [v for v in graph.vertices if
                                   isinstance(v, LightVertex) and getattr(v, 'light_type', 'furniture') == "furniture"]
        obstacles_before = [v for v in graph.vertices if isinstance(v, ObstanceVertex)]

        logger.debug(
            f"🔍 לפני אופטימיזציה: {len(center_lights_before)} מנורות מרכזיות, {len(furniture_lights_before)} מנורות ריהוט, {len(obstacles_before)} מכשולים")

        # **אופטימיזציה ללא שינוי הגרף המקורי**
        optimized_lights = None
        try:
            logger.debug("Starting lighting optimization...")

            optimizer = ShadowOptimizer(graph)
            optimized_lights = optimizer.optimize_lighting_by_shadow_analysis()

            logger.debug(f"🔍 האופטימיזציה החזירה: {len(optimized_lights)} מנורות")
            logger.debug("✅ Optimization completed successfully")

        except Exception as e:
            logger.error(f"❌ שגיאה באופטימיזציה: {str(e)}")

        # **הצגת תוצאות האופטימיזציה ללא שינוי הגרף**
        if optimized_lights:
            try:
                self.visualize_optimization_results(graph, optimized_lights,
                                                    f"תכנית תאורה אחרי אופטימיזציה - {room_type}")
            except Exception as e:
                logger.warning("Could not display optimized graph visualization: %s", str(e))

        # **החזרת הגרף המקורי ללא שום שינוי**
        logger.debug(f"מחזיר גרף מקורי עם {len(graph.vertices)} צמתים ו-{len(graph.edges)} קשתות")
        return graph

    def visualize_optimization_results(self, original_graph: Graph, optimized_lights: list, title: str):
        """הדמיה של תוצאות האופטימיזציה ללא שינוי הגרף המקורי"""
        try:
            if not original_graph.vertices:
                logger.warning("Graph is empty, nothing to visualize")
                return

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

            # הדמיה דו-ממדית
            self.plot_optimized_2d_view(original_graph, optimized_lights, ax1, f"{title} - מבט עליון")

            # הדמיה תלת-ממדית
            ax2.remove()
            ax2 = fig.add_subplot(122, projection='3d')
            self.plot_optimized_3d_view(original_graph, optimized_lights, ax2, f"{title} - תלת-ממד")

            plt.tight_layout()
            plt.show()

        except Exception as e:
            logger.error(f"שגיאה בהדמיית תוצאות: {str(e)}")

    def plot_optimized_2d_view(self, original_graph: Graph, optimized_lights: list, ax, title):
        """הדמיה דו-ממדית עם המנורות המאופטמות"""
        walls_x, walls_y = [], []
        center_lights_x, center_lights_y = [], []
        furniture_lights_x, furniture_lights_y = [], []
        furniture_x, furniture_y = [], []
        other_x, other_y = [], []

        # הצגת כל הצמתים מהגרף המקורי (מלבד מנורות מרכזיות)
        for vertex in original_graph.vertices:
            x, y = vertex.point.x, vertex.point.y

            if isinstance(vertex, LightVertex):
                # הצגת מנורות ריהוט בלבד מהגרף המקורי
                if getattr(vertex, 'light_type', 'center') == "furniture":
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

        # הצגת המנורות המאופטמות
        for light in optimized_lights:
            if isinstance(light, LightVertex) and getattr(light, 'light_type', 'center') == "center":
                center_lights_x.append(light.point.x)
                center_lights_y.append(light.point.y)

        # רישום הנקודות
        if walls_x:
            ax.scatter(walls_x, walls_y, c='blue', s=100, marker='s', label='קירות', alpha=0.7)
        if center_lights_x:
            ax.scatter(center_lights_x, center_lights_y, c='red', s=200, marker='*', label='תאורה מרכזית מאופטמת',
                       alpha=0.9)
        if furniture_lights_x:
            ax.scatter(furniture_lights_x, furniture_lights_y, c='orange', s=120, marker='*', label='תאורת ריהוט',
                       alpha=0.8)
        if furniture_x:
            ax.scatter(furniture_x, furniture_y, c='green', s=120, marker='o', label='ריהוט', alpha=0.7)
        if other_x:
            ax.scatter(other_x, other_y, c='gray', s=80, marker='.', label='אחר', alpha=0.5)

        # הצגת קשתות (רק של האלמנטים שאינם מנורות מרכזיות)
        for edge in original_graph.edges:
            if edge.start < len(original_graph.vertices) and edge.end < len(original_graph.vertices):
                start_vertex = original_graph.vertices[edge.start]
                end_vertex = original_graph.vertices[edge.end]

                # הצגת קשתות רק בין צמתים שאינם מנורות מרכזיות
                start_is_center_light = isinstance(start_vertex, LightVertex) and getattr(start_vertex, 'light_type',
                                                                                          'center') == 'center'
                end_is_center_light = isinstance(end_vertex, LightVertex) and getattr(end_vertex, 'light_type',
                                                                                      'center') == 'center'

                if not start_is_center_light and not end_is_center_light:
                    ax.plot([start_vertex.point.x, end_vertex.point.x],
                            [start_vertex.point.y, end_vertex.point.y],
                            'b-', alpha=0.6, linewidth=1)

        ax.set_xlabel('X (מטר)')
        ax.set_ylabel('Y (מטר)')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')

    def plot_optimized_3d_view(self, original_graph: Graph, optimized_lights: list, ax, title):
        """הדמיה תלת-ממדית עם המנורות המאופטמות"""
        # הצגת כל הצמתים מהגרף המקורי (מלבד מנורות מרכזיות)
        for vertex in original_graph.vertices:
            x, y, z = vertex.point.x, vertex.point.y, vertex.point.z

            if isinstance(vertex, LightVertex):
                # הצגת מנורות ריהוט בלבד מהגרף המקורי
                if getattr(vertex, 'light_type', 'center') == "furniture":
                    ax.scatter(x, y, z, c='orange', s=120, marker='*', alpha=0.8)
            elif hasattr(vertex, 'required_lux') and vertex.required_lux > 0:
                ax.scatter(x, y, z, c='green', s=120, marker='o', alpha=0.7)
            elif hasattr(vertex, 'reflection_factor') and vertex.reflection_factor > 0.05:
                ax.scatter(x, y, z, c='blue', s=100, marker='s', alpha=0.7)
            else:
                ax.scatter(x, y, z, c='gray', s=80, marker='.', alpha=0.5)

        # הצגת המנורות המאופטמות
        for light in optimized_lights:
            if isinstance(light, LightVertex) and getattr(light, 'light_type', 'center') == "center":
                ax.scatter(light.point.x, light.point.y, light.point.z, c='red', s=200, marker='*', alpha=0.9)

        # הצגת קשתות (רק של האלמנטים שאינם מנורות מרכזיות)
        for edge in original_graph.edges:
            if edge.start < len(original_graph.vertices) and edge.end < len(original_graph.vertices):
                start_vertex = original_graph.vertices[edge.start]
                end_vertex = original_graph.vertices[edge.end]

                # הצגת קשתות רק בין צמתים שאינם מנורות מרכזיות
                start_is_center_light = isinstance(start_vertex, LightVertex) and getattr(start_vertex, 'light_type',
                                                                                          'center') == 'center'
                end_is_center_light = isinstance(end_vertex, LightVertex) and getattr(end_vertex, 'light_type',
                                                                                      'center') == 'center'

                if not start_is_center_light and not end_is_center_light:
                    ax.plot([start_vertex.point.x, end_vertex.point.x],
                            [start_vertex.point.y, end_vertex.point.y],
                            [start_vertex.point.z, end_vertex.point.z],
                            'b-', alpha=0.4, linewidth=1)

        ax.set_xlabel('X (מטר)')
        ax.set_ylabel('Y (מטר)')
        ax.set_zlabel('Z (מטר)')
        ax.set_title(title)

    def identify_rooms(self, elements, default_area=20.0):
        """זיהוי חדרים נפרדים מתוך האלמנטים"""
        rooms = []

        try:
            space_elements = []
            for element in elements:
                if isinstance(element, dict):
                    element_type = element.get('ElementType', '').lower()
                    if any(keyword in element_type for keyword in ['חדר', 'space', 'room']):
                        space_elements.append(element)

            if space_elements:
                logger.debug("Found %d space elements, creating rooms based on them", len(space_elements))
                for space in space_elements:
                    try:
                        x = float(space.get('X', 0) or 0)
                        y = float(space.get('Y', 0) or 0)
                        z = float(space.get('Z', 2.5) or 2.5)
                        area = float(space.get('RoomArea', default_area) or default_area)

                        room_center = Point3D(x, y, z)
                        rooms.append({
                            'center': room_center,
                            'area': area,
                            'elements': [space]
                        })
                        logger.debug("Created room from space at (%f, %f, %f) with area %f", x, y, z, area)
                    except Exception as e:
                        logger.warning("Error processing space element: %s", str(e))
            else:
                logger.debug("No space elements found, creating single room based on furniture")
                furniture_elements = []
                walls = []

                for element in elements:
                    if isinstance(element, dict):
                        element_type = element.get('ElementType', '').lower()
                        if any(keyword in element_type for keyword in
                               ['table', 'desk', 'sofa', 'ספה', 'שולחן', 'chair', 'כיסא']):
                            furniture_elements.append(element)
                        elif any(keyword in element_type for keyword in ['קיר', 'wall']):
                            walls.append(element)

                if furniture_elements:
                    room_center = self.calculate_elements_center(furniture_elements)
                    logger.debug("Room center calculated from %d furniture elements", len(furniture_elements))
                elif walls:
                    room_center = self.calculate_room_center_from_walls(walls)
                    logger.debug("Room center calculated from %d walls", len(walls))
                else:
                    room_center = Point3D(0, 0, 2.5)
                    logger.debug("Using default room center")

                rooms.append({
                    'center': room_center,
                    'area': default_area,
                    'elements': furniture_elements + walls
                })

        except Exception as e:
            logger.error("Error in identify_rooms: %s", str(e))
            rooms = [{
                'center': Point3D(0, 0, 2.5),
                'area': default_area,
                'elements': []
            }]

        return rooms if rooms else [{
            'center': Point3D(0, 0, 2.5),
            'area': default_area,
            'elements': []
        }]

    def calculate_elements_center(self, elements):
        """חישוב מרכז גיאומטרי של קבוצת אלמנטים"""
        if not elements:
            return Point3D(0, 0, 2.5)

        sum_x = sum_y = count = 0

        try:
            for element in elements:
                if isinstance(element, dict):
                    x = float(element.get('X', 0) or 0)
                    y = float(element.get('Y', 0) or 0)
                    width = float(element.get('Width', element.get('width', 0)) or 0)
                    length = float(element.get('Length', element.get('length', 0)) or 0)

                    center_x = x + width / 2
                    center_y = y + length / 2

                    sum_x += center_x
                    sum_y += center_y
                    count += 1

            if count == 0:
                return Point3D(0, 0, 2.5)

            return Point3D(sum_x / count, sum_y / count, 2.5)

        except Exception as e:
            logger.error("Error calculating elements center: %s", str(e))
            return Point3D(0, 0, 2.5)

    def calculate_room_center_from_walls(self, walls):
        """חישוב מרכז חדר על בסיס קירות"""
        if not walls:
            return Point3D(0, 0, 2.5)

        try:
            min_x = min_y = float('inf')
            max_x = max_y = float('-inf')

            for wall in walls:
                if isinstance(wall, dict):
                    x = float(wall.get('X', 0) or 0)
                    y = float(wall.get('Y', 0) or 0)
                    width = float(wall.get('Width', wall.get('width', 0)) or 0)
                    length = float(wall.get('Length', wall.get('length', 0)) or 0)

                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x + width)
                    max_y = max(max_y, y + length)

            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2

            return Point3D(center_x, center_y, 2.5)

        except Exception as e:
            logger.error("Error calculating room center from walls: %s", str(e))
            return Point3D(0, 0, 2.5)

    def add_element(self, g: Graph, e: dict):
        if not isinstance(e, dict):
            logger.warning("Element is not a dictionary, skipping: %s", e)
            return

        logger.debug("Adding element to graph: %s", e)

        try:
            x = float(e.get("X", 0) or 0)
            y = float(e.get("Y", 0) or 0)
            z = float(e.get("Z", 0) or 0)

            width = float(e.get("Width", e.get("width", 0)) or 0)
            length = float(e.get("Length", e.get("length", 0)) or 0)
            height = float(e.get("Height", e.get("height", 0)) or 0)

            logger.debug("Element dimensions: x=%f, y=%f, z=%f, width=%f, length=%f, height=%f",
                         x, y, z, width, length, height)

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

            logger.debug("Added %d vertices for element", len(vertex_ids))

            edges = [
                (0, 1, width), (1, 3, length), (3, 2, width), (2, 0, length),
                (4, 5, width), (5, 7, length), (7, 6, width), (6, 4, length),
                (0, 4, height), (1, 5, height), (2, 6, height), (3, 7, height)
            ]

            for i, j, l in edges:
                if i < len(vertex_ids) and j < len(vertex_ids):
                    g.add_edge(Edge(vertex_ids[i], vertex_ids[j], 0, l))
                else:
                    logger.warning("Invalid vertex indices: %d, %d for element %s", i, j, e)

            logger.debug("Added %d edges for element", len(edges))

            reflection_factor = float(e.get("ReflectionFactor", 0) or 0)
            if reflection_factor > 0:
                logger.debug("Element has reflection factor: %f", reflection_factor)
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

    def is_require_light(self, element: dict) -> bool:
        """בדיקה אם אלמנט דורש תאורה מעליו"""
        if not isinstance(element, dict):
            return False

        furniture_types = [
            "table", "שולחן",
            "desk", "שולחן עבודה", "שולחן כתיבה",
            "counter", "דלפק", "משטח עבודה",
            "workbench", "שולחן עבודה",
            "sofa", "ספה", "ספת",
            "couch", "ספה",
            "stage", "במה"
        ]

        element_type = element.get("ElementType", "").lower()
        element_name = element.get("Name", "").lower()

        requires_light = (
                any(furniture_type in element_type for furniture_type in furniture_types) or
                any(furniture_type in element_name for furniture_type in furniture_types)
        )

        logger.debug("Element type '%s' (name: '%s') requires light: %s", element_type, element_name, requires_light)
        return requires_light

    def add_light_above_element(self, graph: Graph, element: dict, room_type: str, ceiling_height: float,
                                recommended_lux: float):
        """הוספת מנורה מעל אלמנט ריהוט"""
        if not isinstance(element, dict):
            logger.warning("Cannot add light above non-dict element: %s", element)
            return

        logger.debug("Adding light above element: %s", element)

        try:
            width = float(element.get("Width", element.get("width", 0)) or 0)
            length = float(element.get("Length", element.get("length", 0)) or 0)

            center_x = float(element.get("X", 0) or 0) + width / 2
            center_y = float(element.get("Y", 0) or 0) + length / 2

            element_type = element.get("ElementType", "unknown").lower()

            logger.debug("Element center at (%f, %f), type: %s in room type: %s",
                         center_x, center_y, element_type, room_type)

            light_height_offset = 0.5
            element_z = float(element.get("Z", 0) or 0)
            element_height = float(element.get("Height", element.get("height", 0)) or 0)

            light_height = min(element_z + element_height + light_height_offset, ceiling_height)

            point = Point3D(center_x, center_y, light_height)

            if any(desk_type in element_type for desk_type in ["desk", "שולחן עבודה", "workbench"]):
                light_lux = recommended_lux * 1.5
            elif any(sofa_type in element_type for sofa_type in ["sofa", "ספה", "couch"]):
                light_lux = recommended_lux * 0.8
            else:
                light_lux = recommended_lux

            element_area = width * length if width > 0 and length > 0 else 2.0
            lumens = self.calculate_lumens(element_area, light_lux)
            element_id = element.get("ID", element.get("ElementId", 0))

            # **מנורת ריהוט - מסומנת כ"furniture"**
            furniture_light = LightVertex(
                point,
                light_lux,
                lumens,
                element_id,
                light_type="furniture"  # 🏷️ תג מנורת ריהוט
            )

            graph.add_vertex(furniture_light)
            logger.debug("Added FURNITURE light at (%f, %f, %f) with %f lux and %f lumens for element type %s",
                         point.x, point.y, point.z, light_lux, lumens, element_type)

        except Exception as e:
            logger.error("Error adding light above element: %s", str(e))

    def calculate_lumens(self, area, lux=300, safety=1.2):
        """חישוב לומן נדרש לפי שטח ועוצמת תאורה"""
        try:
            area = float(area) if area else 0
            logger.debug("Calculating lumens for area: %f, lux: %f", area, lux)
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
                else:  # furniture
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
                else:  # furniture
                    ax.scatter(x, y, z, c='orange', s=120, marker='*', alpha=0.8)
            elif hasattr(vertex, 'required_lux') and vertex.required_lux > 0:
                ax.scatter(x, y, z, c='green', s=120, marker='o', alpha=0.7)
            elif hasattr(vertex, 'reflection_factor') and vertex.reflection_factor > 0.05:
                ax.scatter(x, y, z, c='blue', s=100, marker='s', alpha=0.7)
            else:
                ax.scatter(x, y, z, c='gray', s=80, marker='.', alpha=0.5)

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