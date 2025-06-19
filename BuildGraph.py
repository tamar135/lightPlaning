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

# ייבוא קבועים - כל הקבועים יבואו מקובץ אחד
from constants import (
    DEFAULT_LIGHT_OFFSET, DEFAULT_CEILING_HEIGHT, DEFAULT_ROOM_AREA, DEFAULT_ELEMENT_AREA,
    SAFETY_FACTOR, DEFAULT_LUX, FURNITURE_LUX_MULTIPLIERS, FURNITURE_REQUIRING_LIGHT,
    VISUALIZATION_SETTINGS
)

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class BuildGraph:
    def __init__(self):
        """אתחול מחלקת BuildGraph"""
        logger.debug("BuildGraph initialized")

    def build_graph_from_json(self, json_path: str) -> Graph:
        """בניית גרף מקובץ JSON - גרסה מפושטת"""
        logger.debug("Starting build_graph_from_json with path: %s", json_path)

        # בדיקת קיום הקובץ
        if not os.path.exists(json_path):
            logger.error("JSON file does not exist: %s", json_path)
            return Graph()

        # טעינת JSON
        json_array = self._load_json_safely(json_path)
        if not json_array or len(json_array) < 4:
            logger.error("Invalid JSON data")
            return Graph()

        # חילוץ מידע בסיסי על החדר
        room_info = self._extract_room_info(json_array)
        elements = json_array[4:] if len(json_array) > 4 else []

        # יצירת הגרף
        graph = Graph()

        # הוספת תאורה מרכזית
        self._add_center_light(graph, elements, room_info)

        # הוספת אלמנטים ותאורת ריהוט
        self._process_elements(graph, elements, room_info)

        # הצגה ואופטימיזציה
        self._visualize_and_optimize(graph, room_info["RoomType"])

        return graph

    def _load_json_safely(self, json_path: str) -> list:
        """טעינה בטוחה של קובץ JSON"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_content = f.read()
                logger.debug("JSON file content length: %d", len(json_content))
                return json.loads(json_content)
        except Exception as e:
            logger.error("Error reading/parsing JSON file: %s", str(e))
            return []

    def _extract_room_info(self, json_array: list) -> dict:
        """חילוץ מידע על החדר מהמערך"""
        try:
            return {
                "RecommendedLux": float(json_array[0].get("RecommendedLux", DEFAULT_LUX)),
                "RoomType": json_array[1].get("RoomType", "unknown"),
                "RoomHeight": float(json_array[2].get("RoomHeight", DEFAULT_CEILING_HEIGHT)),
                "RoomArea": float(json_array[3].get("RoomArea", DEFAULT_ROOM_AREA))
            }
        except Exception as e:
            logger.error("Error extracting room properties: %s", str(e))
            return {
                "RecommendedLux": DEFAULT_LUX,
                "RoomType": "unknown",
                "RoomHeight": DEFAULT_CEILING_HEIGHT,
                "RoomArea": DEFAULT_ROOM_AREA
            }

    def _add_center_light(self, graph: Graph, elements: list, room_info: dict):
        """הוספת תאורה מרכזית לחדר"""
        try:
            room_center_x, room_center_y = self.calculate_room_center(elements)
            light_height = room_info["RoomHeight"] - DEFAULT_LIGHT_OFFSET

            room_center = Point3D(room_center_x, room_center_y, light_height)
            room_lumens = self.calculate_lumens(room_info["RoomArea"], room_info["RecommendedLux"])

            center_light = LightVertex(
                room_center,
                room_info["RecommendedLux"],
                room_lumens,
                target_id=None,
                light_type="center"
            )

            graph.add_vertex(center_light)
            graph.set_center(room_center)

            logger.debug("מנורה מרכזית בנקודה (%f, %f, %f)",
                         room_center.x, room_center.y, room_center.z)
        except Exception as e:
            logger.error("Error creating center light: %s", str(e))
            # ברירת מחדל
            default_center = Point3D(0, 0, DEFAULT_CEILING_HEIGHT - DEFAULT_LIGHT_OFFSET)
            default_light = LightVertex(default_center, DEFAULT_LUX,
                                        self.calculate_lumens(DEFAULT_ROOM_AREA, DEFAULT_LUX),
                                        None, "center")
            graph.add_vertex(default_light)
            graph.set_center(default_center)

    def _process_elements(self, graph: Graph, elements: list, room_info: dict):
        """עיבוד כל האלמנטים והוספתם לגרף"""
        for i, element in enumerate(elements):
            try:
                logger.debug("Processing element %d: %s", i, element)
                self.add_element(graph, element)

                # בדיקה אם האלמנט דורש תאורה
                if self.is_require_light_fixed(element):
                    logger.debug("Element %d requires light", i)
                    furniture_light = self.add_light_above_element(
                        graph, element, room_info["RoomType"],
                        room_info["RoomHeight"], room_info["RecommendedLux"]
                    )
                    if furniture_light:
                        logger.debug("נוספה מנורת ריהוט")

            except Exception as e:
                logger.error("Error processing element %d: %s", i, str(e))

    def _visualize_and_optimize(self, graph: Graph, room_type: str):
        """הצגת הגרף ואופטימיזציה"""
        try:
            # הצגה לפני אופטימיזציה
            self.visualize_graph(graph, f"תכנית תאורה לפני אופטימיזציה - {room_type}")

            # אופטימיזציה
            logger.debug("מתחיל אופטימיזציה...")
            optimized_lights = algorithm.algorithm(graph)
            logger.debug(f"האופטימיזציה החזירה: {len(optimized_lights)} מנורות")

            # הצגה אחרי אופטימיזציה
            self.visualize_graph(graph, f"תכנית תאורה אחרי אופטימיזציה - {room_type}")

        except Exception as e:
            logger.warning("Could not complete visualization/optimization: %s", str(e))

    def calculate_room_center(self, elements: list) -> tuple:
        """חישוב מרכז החדר לפי האלמנטים"""
        if not elements:
            return (0, 0)

        all_x, all_y = [], []

        for element in elements:
            try:
                x = float(element.get("X", 0) or 0)
                y = float(element.get("Y", 0) or 0)
                width = float(element.get("Width", 0) or 0)
                length = float(element.get("Length", 0) or 0)

                all_x.extend([x, x + width])
                all_y.extend([y, y + length])
            except:
                continue

        if all_x and all_y:
            center_x = (min(all_x) + max(all_x)) / 2
            center_y = (min(all_y) + max(all_y)) / 2
            logger.debug(f"מרכז החדר מחושב: ({center_x:.1f}, {center_y:.1f})")
            return (center_x, center_y)

        return (0, 0)

    def is_require_light_fixed(self, element: dict) -> bool:
        """בדיקה אם אלמנט דורש תאורה - גרסה פשוטה"""
        if not isinstance(element, dict):
            return False

        element_type = element.get("ElementType", "").lower()
        element_name = element.get("Name", "").lower()

        # בדיקה מול רשימת הריהוט מהקבועים
        return any(furniture_type in element_type or furniture_type in element_name
                   for furniture_type in FURNITURE_REQUIRING_LIGHT)

    def add_light_above_element(self, graph: Graph, element: dict, room_type: str,
                                ceiling_height: float, recommended_lux: float):
        """הוספת מנורה מעל אלמנט ריהוט - גרסה פשוטה"""
        if not isinstance(element, dict):
            logger.warning("Cannot add light above non-dict element")
            return None

        try:
            # חילוץ מידות ומיקום
            location_data = self._extract_element_location(element)
            if not location_data:
                return None

            # חישוב עוצמת תאורה באמצעות מקדם מהקבועים
            light_lux = self._calculate_element_lux(element, recommended_lux)

            # חישוב גובה ומיקום התאורה
            light_height = min(
                location_data["z"] + location_data["height"] + DEFAULT_LIGHT_OFFSET,
                ceiling_height
            )

            point = Point3D(location_data["center_x"], location_data["center_y"], light_height)

            # חישוב לומן
            element_area = location_data["area"] if location_data["area"] > 0 else DEFAULT_ELEMENT_AREA
            lumens = self.calculate_lumens(element_area, light_lux)

            # יצירת מנורת ריהוט
            furniture_light = LightVertex(
                point, light_lux, lumens,
                element.get("ID", element.get("ElementId", 0)),
                light_type="furniture"
            )

            graph.add_vertex(furniture_light)
            return furniture_light

        except Exception as e:
            logger.error("Error adding light above element: %s", str(e))
            return None

    def _extract_element_location(self, element: dict) -> dict:
        """חילוץ מיקום ומידות של אלמנט"""
        try:
            width = float(element.get("Width", element.get("width", 0)) or 0)
            length = float(element.get("Length", element.get("length", 0)) or 0)

            return {
                "center_x": float(element.get("X", 0) or 0) + width / 2,
                "center_y": float(element.get("Y", 0) or 0) + length / 2,
                "z": float(element.get("Z", 0) or 0),
                "height": float(element.get("Height", element.get("height", 0)) or 0),
                "area": width * length
            }
        except Exception as e:
            logger.error("Error extracting element location: %s", str(e))
            return None

    def _calculate_element_lux(self, element: dict, recommended_lux: float) -> float:
        """חישוב עוצמת תאורה לאלמנט באמצעות מקדמים מהקבועים"""
        element_type = element.get("ElementType", "").lower()

        # חיפוש מקדם מתאים
        multiplier = next((mult for keyword, mult in FURNITURE_LUX_MULTIPLIERS.items()
                           if keyword in element_type), 1.0)

        return recommended_lux * multiplier

    def calculate_lumens(self, area: float, lux: float = DEFAULT_LUX) -> float:
        """חישוב לומן נדרש - גרסה פשוטה"""
        try:
            area = float(area) if area else 0
            return area * lux * SAFETY_FACTOR
        except Exception as e:
            logger.error("Error calculating lumens: %s", str(e))
            return 0

    def add_element(self, g: Graph, e: dict):
        """הוספת אלמנט לגרף - גרסה מקוצרת"""
        if not isinstance(e, dict):
            logger.warning("Element is not a dictionary, skipping")
            return

        try:
            # חילוץ קואורדינטות
            coords = self._extract_coordinates(e)
            if not coords:
                return

            # יצירת נקודות הפינות
            points = self._create_corner_points(coords)

            # הוספת צמתים לגרף
            vertex_ids = [g.add_vertex(ObstanceVertex(0, pt, 0, 0)) for pt in points]

            # הוספת קשתות
            self._add_element_edges(g, vertex_ids, coords)

            # הוספת השתקפויות אם קיימות
            self._add_reflections(g, e, vertex_ids, coords)

        except Exception as e:
            logger.error("Error in add_element: %s", str(e))

    def _extract_coordinates(self, element: dict) -> dict:
        """חילוץ קואורדינטות מאלמנט"""
        try:
            return {
                "x": float(element.get("X", 0) or 0),
                "y": float(element.get("Y", 0) or 0),
                "z": float(element.get("Z", 0) or 0),
                "width": float(element.get("Width", element.get("width", 0)) or 0),
                "length": float(element.get("Length", element.get("length", 0)) or 0),
                "height": float(element.get("Height", element.get("height", 0)) or 0)
            }
        except Exception as e:
            logger.error("Error extracting coordinates: %s", str(e))
            return None

    def _create_corner_points(self, coords: dict) -> list:
        """יצירת נקודות פינות הקובייה"""
        x, y, z = coords["x"], coords["y"], coords["z"]
        w, l, h = coords["width"], coords["length"], coords["height"]

        return [
            Point3D(x, y, z), Point3D(x + w, y, z),
            Point3D(x, y + l, z), Point3D(x + w, y + l, z),
            Point3D(x, y, z + h), Point3D(x + w, y, z + h),
            Point3D(x, y + l, z + h), Point3D(x + w, y + l, z + h)
        ]

    def _add_element_edges(self, graph: Graph, vertex_ids: list, coords: dict):
        """הוספת קשתות האלמנט"""
        edges = [
            (0, 1, coords["width"]), (1, 3, coords["length"]),
            (3, 2, coords["width"]), (2, 0, coords["length"]),
            (4, 5, coords["width"]), (5, 7, coords["length"]),
            (7, 6, coords["width"]), (6, 4, coords["length"]),
            (0, 4, coords["height"]), (1, 5, coords["height"]),
            (2, 6, coords["height"]), (3, 7, coords["height"])
        ]

        for i, j, length in edges:
            if i < len(vertex_ids) and j < len(vertex_ids):
                graph.add_edge(Edge(vertex_ids[i], vertex_ids[j], 0, length))

    def _add_reflections(self, graph: Graph, element: dict, vertex_ids: list, coords: dict):
        """הוספת השתקפויות אם קיימות"""
        reflection_factor = float(element.get("ReflectionFactor", 0) or 0)
        if reflection_factor <= 0:
            return

        try:
            face_center = Point3D(
                coords["x"] + coords["width"] / 2,
                coords["y"],
                coords["z"] + coords["height"] / 2
            )

            reflection_range = float(element.get("ReflectionRange", 1.0) or 1.0)

            for dist in [i * 0.5 for i in range(1, int(reflection_range / 0.5) + 1)]:
                reflection_point = Point3D(
                    face_center.x,
                    face_center.y - dist,  # נורמל בכיוון Y-
                    face_center.z
                )

                reflection_vertex = graph.add_vertex(Vertex(reflection_point))
                graph.add_edge(Edge(vertex_ids[0], reflection_vertex, reflection_factor, dist))

        except Exception as e:
            logger.debug("Error adding reflections: %s", str(e))

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
        """הצגה דו-ממדית - מפושטת עם קבועים"""
        # מיון נקודות לפי סוג
        points_by_type = self._categorize_vertices(graph)

        # הצגת כל סוג עם הגדרות מהקבועים
        for vertex_type, (x_coords, y_coords) in points_by_type.items():
            if x_coords:  # רק אם יש נקודות מהסוג הזה
                settings = VISUALIZATION_SETTINGS[vertex_type]
                ax.scatter(x_coords, y_coords, **settings)

        # הצגת קשתות
        self._plot_edges_2d(graph, ax)

        ax.set_xlabel('X (מטר)')
        ax.set_ylabel('Y (מטר)')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=VISUALIZATION_SETTINGS["grid_alpha"])
        ax.set_aspect('equal')

    def _categorize_vertices(self, graph: Graph) -> dict:
        """מיון צמתים לפי סוג"""
        categories = {
            "walls": ([], []),
            "center_lights": ([], []),
            "furniture_lights": ([], []),
            "furniture": ([], []),
            "other": ([], [])
        }

        for vertex in graph.vertices:
            x, y = vertex.point.x, vertex.point.y

            if isinstance(vertex, LightVertex):
                if getattr(vertex, 'light_type', 'center') == "center":
                    categories["center_lights"][0].append(x)
                    categories["center_lights"][1].append(y)
                else:
                    categories["furniture_lights"][0].append(x)
                    categories["furniture_lights"][1].append(y)
            elif hasattr(vertex, 'reflection_factor') and vertex.reflection_factor > 0.05:
                categories["walls"][0].append(x)
                categories["walls"][1].append(y)
            elif hasattr(vertex, 'required_lux') and vertex.required_lux > 0:
                categories["furniture"][0].append(x)
                categories["furniture"][1].append(y)
            else:
                categories["other"][0].append(x)
                categories["other"][1].append(y)

        return categories

    def _plot_edges_2d(self, graph: Graph, ax):
        """הצגת קשתות במבט דו-ממדי"""
        for edge in graph.edges:
            if (edge.start < len(graph.vertices) and edge.end < len(graph.vertices)):
                start_vertex = graph.vertices[edge.start]
                end_vertex = graph.vertices[edge.end]

                # רק קשתות שאינן מתאורה
                if not isinstance(start_vertex, LightVertex) and not isinstance(end_vertex, LightVertex):
                    ax.plot([start_vertex.point.x, end_vertex.point.x],
                            [start_vertex.point.y, end_vertex.point.y],
                            'b-', alpha=VISUALIZATION_SETTINGS["edge_alpha"], linewidth=1)

    def plot_3d_view(self, graph: Graph, ax, title):
        """הצגה תלת-ממדית מפושטת"""
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

        # קשתות תלת-ממדיות
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