# algorithm.py - תיקון לקריאה לאופטימיזציה לפי חדרים
from models import Graph, LightVertex
from ShadowOptimizer import ShadowOptimizer
import logging

logger = logging.getLogger(__name__)


def algorithm(room_graph: Graph):
    """
    אלגוריתם האופטימיזציה הראשי - נקרא מהשרת
    עכשיו עם תמיכה בחדרים נפרדים
    """
    try:
        logger.debug("Running lighting optimization algorithm with room separation")

        optimizer = ShadowOptimizer(room_graph)

        # **שימוש בפונקציה החדשה לאופטימיזציה לפי חדרים**
        # במקום optimize_lighting_by_shadow_analysis
        optimized_lights = optimizer.optimize_lighting_by_rooms()

        # הסרת מנורות מרכזיות ישנות מהגרף
        room_graph.vertices = [v for v in room_graph.vertices
                               if not (isinstance(v, LightVertex) and getattr(v, 'light_type', 'center') == 'center')]

        # הוספת המנורות המאופטמות החדשות
        for light in optimized_lights:
            room_graph.add_vertex(light)

        logger.debug(f"Room-based optimization completed. Final lights: {len(optimized_lights)}")
        return optimized_lights

    except Exception as e:
        logger.error(f"Algorithm failed: {str(e)}")
        return []