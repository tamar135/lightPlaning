from typing import List
import json
import math

class Point3D:
    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z

    def __repr__(self):
        return f"Point3D({self.x}, {self.y}, {self.z})"

class Vertex:
    def __init__(self, point: Point3D):
        self.point = point

class LightVertex(Vertex):
    def __init__(self, point: Point3D, lux: float, lumens: float, target_id=None):
        super().__init__(point)
        self.lux = lux
        self.lumens = lumens
        self.target_id = target_id

class ObstanceVertex(Vertex):
    def __init__(self, element_id, point: Point3D, reflection_factor: float, required_lux: float):
        super().__init__(point)
        self.element_id = element_id if element_id is not None else 0
        self.reflection_factor = reflection_factor
        self.required_lux = required_lux

class Edge:
    def __init__(self, start: int, end: int, weight: float, length: float):
        self.start = start
        self.end = end
        self.weight = weight
        self.length = length

class Graph:
    def __init__(self):
        self.vertices = []
        self.edges = []
        self.center = None

    def add_vertex(self, vertex: Vertex) -> int:
        self.vertices.append(vertex)
        return len(self.vertices) - 1

    def add_edge(self, edge: Edge):
        self.edges.append(edge)

    def set_center(self, point: Point3D):
        self.center = point

    def __repr__(self):
        return f"Graph(vertices={len(self.vertices)}, edges={len(self.edges)})"
