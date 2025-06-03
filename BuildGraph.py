# BuildGraph.py - גרסה מתוקנת
import json
import os
import logging
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from models import Graph, Point3D, LightVertex, ObstanceVertex, Edge, Vertex
import math
from Algorithm import algorithm

import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
algorithm_dir = os.path.join(current_dir, 'Algorithm')
if algorithm_dir not in sys.path:
    sys.path.append(algorithm_dir)

from Algorithm.ShadowOptimizer import ShadowOptimizer

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class BuildGraph:
    def __init__(self, config=None):
        """אתחול מחלקת BuildGraph"""
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
            recommended_lux = float(json_array[0].get("RecommendedLux", 300))
            room_type = json_array[1].get("RoomType", "bedroom")
            ceiling_height = float(json_array[2].get("RoomHeight", 2.5))
            room_area = float(json_array[3].get("RoomArea", 20.0))

            logger.debug(f" חדר: {room_type}, {recommended_lux} לוקס, גובה {ceiling_height}מ, שטח {room_area}מר")

        except Exception as e:
            logger.error("Error extracting room properties: %s", str(e))
            recommended_lux = 300
            room_type = "bedroom"
            ceiling_height = 2.5
            room_area = 20.0

        # אלמנטים
        elements = json_array[4:] if len(json_array) > 4 else []
        logger.debug("Extracted %d elements", len(elements))

        graph = Graph()

        try:
            # חישוב מרכז החדר לפי האלמנטים
            room_center_x, room_center_y = self.calculate_room_center(elements)
            actual_ceiling_height = max(ceiling_height, 2.5)

            room_center = Point3D(room_center_x, room_center_y, actual_ceiling_height - 0.5)
            room_lumens = self.calculate_lumens(room_area, recommended_lux)

            center_light = LightVertex(
                room_center,
                recommended_lux,
                room_lumens,
                target_id=None,
                light_type="center"
            )
            graph.add_vertex(center_light)
            graph.set_center(room_center)

            logger.debug(" מנורה מרכזית בנקודה (%f, %f, %f)",
                         room_center.x, room_center.y, room_center.z)

        except Exception as e:
            logger.error("Error creating center light: %s", str(e))
            # חדר ברירת מחדל
            default_center = Point3D(0, 0, max(ceiling_height, 2.5) - 0.5)
            default_light = LightVertex(default_center, recommended_lux,
                                        self.calculate_lumens(room_area, recommended_lux),
                                        None, "center")
            graph.add_vertex(default_light)
            graph.set_center(default_center)

        # הוספת כל האלמנטים לגרף
        furniture_elements = []
        try:
            for i, element in enumerate(elements):
                try:
                    logger.debug("Processing element %d: %s", i, element)
                    self.add_element(graph, element)

                    if self.is_require_light_fixed(element):
                        logger.debug("Element %d requires light", i)

                        furniture_light = self.add_light_above_element(graph, element, room_type,
                                                                       actual_ceiling_height, recommended_lux)
                        if furniture_light:
                            furniture_elements.append(element)
                            logger.debug("🪑 הוספתי מנורת ריהוט")

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

        # אופטימיזציה - תוקן
        try:
            logger.debug("🔧 מתחיל אופטימיזציה...")

            optimized_lights = algorithm.algorithm(graph)

            logger.debug(f"✅ האופטימיזציה החזירה: {len(optimized_lights)} מנורות")

            # הצגת תוצאות האופטימיזציה
            try:
                self.visualize_graph(graph, f"תכנית תאורה אחרי אופטימיזציה - {room_type}")
            except Exception as e:
                logger.warning("Could not display optimized graph: %s", str(e))

        except Exception as e:
            logger.error(f"❌ שגיאה באופטימיזציה: {str(e)}")

        logger.debug(f"מחזיר גרף עם {len(graph.vertices)} צמתים ו-{len(graph.edges)} קשתות")
        return graph

    def calculate_room_center(self, elements: list) -> tuple:
        """חישוב מרכז החדר לפי האלמנטים - פונקציה חדשה"""
        if not elements:
            return (0, 0)

        all_x = []
        all_y = []

        for element in elements:
            try:
                x = float(element.get("X", 0) or 0)
                y = float(element.get("Y", 0) or 0)
                width = float(element.get("Width", 0) or 0)
                length = float(element.get("Length", 0) or 0)

                # הוסף נקודות פינות
                all_x.extend([x, x + width])
                all_y.extend([y, y + length])
            except:
                continue

        if all_x and all_y:
            center_x = (min(all_x) + max(all_x)) / 2
            center_y = (min(all_y) + max(all_y)) / 2
            logger.debug(f"🎯 מרכז החדר מחושב: ({center_x:.1f}, {center_y:.1f})")
            return (center_x, center_y)

        return (0, 0)

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
        """הוספת מנורה מעל אלמנט ריהוט"""
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