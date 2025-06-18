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

        # החלפת המנורות המרכזיות
        replace_center_lights_only(room_graph, optimized_lights)

        logger.debug(f"Room-based optimization completed. Final lights: {len(optimized_lights)}")
        return optimized_lights

    except Exception as e:
        logger.error(f"Algorithm failed: {str(e)}")
        return []



def replace_center_lights_only(graph: Graph, new_lights: list):
    """
    מחליף רק את המנורות המרכזיות 
    """
    # מפריד בין מרכז לריהוט ברשימה החדשה
    new_center_lights = [light for light in new_lights
                         if getattr(light, 'light_type', 'center') == 'center']

    # מחליף רק מנורות מרכז
    center_light_index = 0
    for i, vertex in enumerate(graph.vertices):
        if isinstance(vertex, LightVertex) and getattr(vertex, 'light_type', 'center') == 'center':
            if center_light_index < len(new_center_lights):
                graph.vertices[i] = new_center_lights[center_light_index]
                center_light_index += 1

    # מוסיף מנורות מרכז נוספות (אם יש)
    for i in range(center_light_index, len(new_center_lights)):
        graph.add_vertex(new_center_lights[i])