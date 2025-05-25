# algorithm.py
from models import Graph, LightVertex
from ShadowOptimizer import ShadowOptimizer
import logging

logger = logging.getLogger(__name__)


def algorithm(room_graph: Graph):
    """
    אלגוריתם האופטימיזציה הראשי - נקרא מהשרת
    """
    try:
        logger.debug("Running lighting optimization algorithm")

        optimizer = ShadowOptimizer(room_graph)
        optimized_lights = optimizer.optimize_lighting_by_shadow_analysis()

        room_graph.vertices = [v for v in room_graph.vertices
                               if not isinstance(v, LightVertex)]

        for light in optimized_lights:
            room_graph.add_vertex(light)

        logger.debug(f"Optimization completed. Final lights: {len(optimized_lights)}")
        return optimized_lights

    except Exception as e:
        logger.error(f"Algorithm failed: {str(e)}")
        return []