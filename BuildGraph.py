import json
import os
import logging
from models import Graph, Point3D, LightVertex, ObstanceVertex, Edge, Vertex

# הגדרת לוגר
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class BuildGraph:
    def __init__(self, room_lighting_analyzer):
        self.room_lighting_analyzer = room_lighting_analyzer
        logger.debug("BuildGraph initialized with room_lighting_analyzer: %s", room_lighting_analyzer)

    def build_graph_from_json(self, json_path: str) -> Graph:
        logger.debug("Starting build_graph_from_json with path: %s", json_path)

        # בדיקה שהקובץ קיים
        if not os.path.exists(json_path):
            logger.error("JSON file does not exist: %s", json_path)
            return Graph()

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                try:
                    json_content = f.read()
                    logger.debug("JSON file content length: %d", len(json_content))
                    logger.debug("JSON file content preview: %s", json_content[:200] if json_content else "Empty")

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
            # נסה לחלץ את הערכים הראשוניים
            recommended_lux = 300  # ערך ברירת מחדל
            room_type = "bedroom"  # ערך ברירת מחדל
            ceiling_height = 2.5  # ערך ברירת מחדל
            room_area = 20.0  # ערך ברירת מחדל

            if len(json_array) > 0 and isinstance(json_array[0], dict):
                recommended_lux = float(json_array[0].get("RecommendedLux", 300))
                logger.debug("Extracted RecommendedLux: %f", recommended_lux)

            if len(json_array) > 1 and isinstance(json_array[1], dict):
                room_type = json_array[1].get("RoomType", "bedroom")
                logger.debug("Extracted RoomType: %s", room_type)

            if len(json_array) > 2 and isinstance(json_array[2], dict):
                ceiling_height_value = json_array[2].get("RoomHeight", 2.5)
                ceiling_height = float(ceiling_height_value) if ceiling_height_value else 2.5
                logger.debug("Extracted RoomHeight: %f", ceiling_height)

            if len(json_array) > 3 and isinstance(json_array[3], dict):
                room_area_value = json_array[3].get("RoomArea", 20.0)
                room_area = float(room_area_value) if room_area_value else 20.0
                logger.debug("Extracted RoomArea: %f", room_area)
        except Exception as e:
            logger.error("Error extracting basic room properties: %s", str(e))
            # אם לא הצלחנו לחלץ את המאפיינים הבסיסיים, נשתמש בערכי ברירת מחדל
            recommended_lux = 300
            room_type = "bedroom"
            ceiling_height = 2.5
            room_area = 20.0

        # המשך החילוץ של האלמנטים
        elements = []
        try:
            if len(json_array) > 4:
                elements = json_array[4:]
                logger.debug("Extracted %d elements", len(elements))
        except Exception as e:
            logger.error("Error extracting elements from JSON: %s", str(e))

        graph = Graph()
        logger.debug("Created empty graph")

        # בדיקה אם יש אלמנט מרכזי - תיקון: שימוש ב-Width/Length באותיות גדולות
        try:
            center_element = None
            for e in elements:
                if (isinstance(e, dict) and
                        e.get('ElementType') == 'center_point' and
                        ((e.get('Width', 1) == 0 and e.get('Length', 1) == 0) or
                         (e.get('width', 1) == 0 and e.get('length', 1) == 0))):
                    center_element = e
                    break

            if center_element:
                logger.debug("Found center element: %s", center_element)
                try:
                    center_x = float(center_element.get('X', 0) or 0)
                    center_y = float(center_element.get('Y', 0) or 0)
                    center_z = float(center_element.get('Z', 0) or 0)

                    center_point = Point3D(center_x, center_y, center_z)
                    graph.set_center(center_point)

                    lumens = self.calculate_lumens(room_area, recommended_lux)
                    graph.add_vertex(LightVertex(center_point, recommended_lux, lumens))
                    logger.debug("Added center point to graph at (%f, %f, %f) with %f lumens",
                                 center_x, center_y, center_z, lumens)
                except Exception as e:
                    logger.error("Error processing center element: %s", str(e))
        except Exception as e:
            logger.error("Error finding center element: %s", str(e))

        # הוספת כל האלמנטים לגרף
        try:
            for i, element in enumerate(elements):
                try:
                    logger.debug("Processing element %d: %s", i, element)
                    self.add_element(graph, element)

                    if self.is_require_light(element):
                        logger.debug("Element %d requires light", i)
                        self.add_light_above_element(graph, element, room_type, ceiling_height)
                except Exception as e:
                    logger.error("Error processing element %d: %s", i, str(e))
                    # המשך לאלמנט הבא
        except Exception as e:
            logger.error("Error iterating through elements: %s", str(e))

        logger.debug("Graph building completed with %d vertices and %d edges",
                     len(graph.vertices) if hasattr(graph, 'vertices') and graph.vertices else 0,
                     len(graph.edges) if hasattr(graph, 'edges') and graph.edges else 0)

        return graph

    def add_element(self, g: Graph, e: dict):
        if not isinstance(e, dict):
            logger.warning("Element is not a dictionary, skipping: %s", e)
            return

        logger.debug("Adding element to graph: %s", e)

        try:
            # המרת ערכים למספרים עם ברירות מחדל
            # בדיקה לשני סוגי הכתיב: אותיות גדולות וקטנות
            x = float(e.get("X", 0) or 0)
            y = float(e.get("Y", 0) or 0)
            z = float(e.get("Z", 0) or 0)

            width = float(e.get("Width", e.get("width", 0)) or 0)
            length = float(e.get("Length", e.get("length", 0)) or 0)
            height = float(e.get("Height", e.get("height", 0)) or 0)

            logger.debug("Element dimensions: x=%f, y=%f, z=%f, width=%f, length=%f, height=%f",
                         x, y, z, width, length, height)

            # ערך דמה במקום ID
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

            # החזרת אור - בדיקה של קיום המפתחות
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
        if not isinstance(element, dict):
            return False

        types = ["table", "desk", "counter", "workbench", "stage"]
        element_type = element.get("ElementType", "").lower()
        requires_light = any(t in element_type for t in types)

        logger.debug("Element type '%s' requires light: %s", element_type, requires_light)
        return requires_light

    def add_light_above_element(self, graph: Graph, element: dict, room_type: str, ceiling_height: float):
        if not isinstance(element, dict):
            logger.warning("Cannot add light above non-dict element: %s", element)
            return

        logger.debug("Adding light above element: %s", element)

        try:
            # פתרון בעיית אותיות ראשיות לעומת קטנות
            width = float(element.get("Width", element.get("width", 0)) or 0)
            length = float(element.get("Length", element.get("length", 0)) or 0)

            center_x = float(element.get("X", 0) or 0) + width / 2
            center_y = float(element.get("Y", 0) or 0) + length / 2

            room_enum = room_type.lower()
            element_type = element.get("ElementType", "unknown").lower()

            logger.debug("Element center at (%f, %f), type: %s in room type: %s",
                         center_x, center_y, element_type, room_enum)

            if not self.room_lighting_analyzer:
                logger.warning("No room_lighting_analyzer available")
                # הגדר ברירת מחדל בסיסית
                default_config = {"Lux": 300, "LightHeightOffset": 0.5}
                logger.debug("Using default config: %s", default_config)
            else:
                # יצירת ערכי ברירת מחדל
                default_config = {
                    "table": {"Lux": 300, "LightHeightOffset": 0.5},
                    "desk": {"Lux": 500, "LightHeightOffset": 0.5},
                    "counter": {"Lux": 400, "LightHeightOffset": 0.6}
                }

                # בדיקה אם יש תצורת תאורה מתאימה לחדר
                room_config = self.room_lighting_analyzer.get(room_enum, {})
                if not room_config:
                    # אין תצורות לסוג החדר הזה
                    logger.warning("No room config found for %s, using default room", room_enum)
                    # נסה למצוא תצורת ברירת מחדל (bedroom)
                    room_config = self.room_lighting_analyzer.get("bedroom", {})

                logger.debug("Room config for %s: %s", room_enum, room_config)

                config = None
                # חיפוש לפי סוג האלמנט המדויק תחילה
                if element_type in room_config:
                    config = room_config[element_type]
                    logger.debug("Found exact config for element type: %s", element_type)
                else:
                    # חיפוש לפי מילת מפתח
                    for key, cfg in room_config.items():
                        if key in element_type:
                            config = cfg
                            logger.debug("Found config by keyword %s in element type: %s", key, element_type)
                            break

                # אם עדיין לא נמצאה תצורה, נחפש בכל התצורות האפשריות
                if not config:
                    logger.warning("No lighting config found in %s, searching all configs", room_enum)
                    # חיפוש בכל החדרים
                    for room_name, room_cfg in self.room_lighting_analyzer.items():
                        # חיפוש לפי סוג אלמנט מדויק
                        if element_type in room_cfg:
                            config = room_cfg[element_type]
                            logger.debug("Found config for %s in room %s", element_type, room_name)
                            break
                        # חיפוש לפי מילת מפתח
                        for key, cfg in room_cfg.items():
                            if key in element_type:
                                config = cfg
                                logger.debug("Found config for keyword %s in room %s", key, room_name)
                                break
                        if config:
                            break

                # אם עדיין אין תצורה, השתמש בתצורת ברירת מחדל
                if not config:
                    logger.warning("No lighting config found for %s in any room, using default", element_type)
                    for default_type, default_cfg in default_config.items():
                        if default_type in element_type:
                            config = default_cfg
                            logger.debug("Using default config for %s", default_type)
                            break

                # אם עדיין אין תצורה, השתמש בתצורת שולחן כברירת מחדל אחרונה
                if not config:
                    logger.warning("Using last resort default table config for %s", element_type)
                    config = default_config["table"]

            # אם עדיין אין תצורה, צור תצורה בסיסית
            if not config:
                config = {"Lux": 300, "LightHeightOffset": 0.5}

            logger.debug("Using lighting config: %s", config)

            # חישוב גובה האור
            light_height_offset = float(config.get("LightHeightOffset", 0.5))
            element_z = float(element.get("Z", 0) or 0)
            element_height = float(element.get("Height", element.get("height", 0)) or 0)

            light_height = min(element_z + element_height + light_height_offset, ceiling_height)

            point = Point3D(center_x, center_y, light_height)

            # חישוב עוצמת האור
            element_length = length
            element_width = width
            light_lux = float(config.get("Lux", 300))

            # אם אין מידות לאלמנט, השתמש בשטח ברירת מחדל
            if element_width == 0 or element_length == 0:
                element_width = 1.0
                element_length = 1.0
                logger.debug("Using default dimensions 1.0 x 1.0 for element with zero width/length")

            lumens = self.calculate_lumens(element_width, element_length, light_lux)
            element_id = element.get("ID", 0)

            logger.debug("Adding light at (%f, %f, %f) with %f lux and %f lumens",
                         point.x, point.y, point.z, light_lux, lumens)

            graph.add_vertex(LightVertex(point, light_lux, lumens, element_id))
        except Exception as e:
            logger.error("Error adding light above element: %s", str(e))

    def calculate_lumens(self, width, length=None, lux=300, safety=1.2):
        try:
            if length is None:
                # אם נשלח רק פרמטר אחד, מניחים שזהו שטח
                area = float(width)
                logger.debug("Calculating lumens for area: %f, lux: %f", area, lux)
                return area * lux * safety
            else:
                width = float(width) if width else 0
                length = float(length) if length else 0
                area = width * length
                logger.debug("Calculating lumens for width: %f, length: %f, area: %f, lux: %f",
                             width, length, area, lux)
                return area * lux * safety
        except Exception as e:
            logger.error("Error calculating lumens: %s", str(e))
            return 0