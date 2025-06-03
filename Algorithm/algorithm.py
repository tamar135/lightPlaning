# algorithm.py - תיקון לקריאה לאופטימיזציה לפי חדרים
from models import Graph, LightVertex
import Algorithm.ShadowOptimizer
from Algorithm.ShadowOptimizer import ShadowOptimizer
import logging

logger = logging.getLogger(__name__)


def algorithm(room_graph: Graph):
    """
    אלגוריתם האופטימיזציה הראשי
    """
    try:
        logger.debug("Running lighting optimization algorithm with room separation")

        optimizer = ShadowOptimizer(room_graph)
        optimized_lights = optimizer.optimize_lighting_room()

        # במקום למחוק ולהוסיף - רק החלף את המנורות המרכזיות
        replace_center_lights_only(room_graph, optimized_lights)

        logger.debug(f"Room-based optimization completed. Final lights: {len(optimized_lights)}")
        return optimized_lights

    except Exception as e:
        logger.error(f"Algorithm failed: {str(e)}")
        return []


def replace_center_lights_only(graph: Graph, new_lights: list):
    """
    מחליף רק את המנורות המרכזיות בלי לפגוע במבנה הגרף
    """
    # מסמן את המנורות המרכזיות הישנות למחיקה
    for i, vertex in enumerate(graph.vertices):
        if isinstance(vertex, LightVertex) and getattr(vertex, 'light_type', 'center') == 'center':
            # מחליף את המנורה הישנה במנורה חדשה מהרשימה
            if new_lights:
                graph.vertices[i] = new_lights.pop(0)

    # מוסיף מנורות נוספות שנותרו (אם יש)
    for remaining_light in new_lights:
        graph.add_vertex(remaining_light)

    # מנקה קשתות שבורות (אם יש)
    graph.edges = [edge for edge in graph.edges
                   if edge.start < len(graph.vertices) and edge.end < len(graph.vertices)]