DEFAULT_LUX = 300
DEFAULT_ROOM_HEIGHT = 2.5
DEFAULT_ROOM_AREA = 20.0
DEFAULT_SAFETY_FACTOR = 1.2
DEFAULT_LIGHT_HEIGHT_OFFSET = 0.5
DEFAULT_REFLECTION_RANGE = 1.0
REFLECTION_STEP = 0.5
SAFETY_FACTOR = 1.2
DEFAULT_LIGHT_OFFSET = 0.5
DEFAULT_CEILING_HEIGHT = 2.5
DEFAULT_ELEMENT_AREA = 2.0

FURNITURE_REQUIRING_LIGHT = [
    "table", "שולחן",
    "desk", "שולחן עבודה",
    "counter", "דלפק",
    "workbench", "kitchen counter",
    "sofa", "ספה", "ספת", "couch"
]

FURNITURE_LUX_MULTIPLIERS = {
    "desk": 1.5,
    "שולחן עבודה": 1.5,
    "workbench": 1.5,
    "counter": 1.3,
    "דלפק": 1.3,
    "kitchen counter": 1.3,
    "sofa": 0.8,
    "ספה": 0.8,
    "couch": 0.8,
    "table": 1.0,
    "שולחן": 1.0
}
VISUALIZATION_SETTINGS = {
    "walls": {"c": 'blue', "s": 100, "marker": 's', "label": 'קירות', "alpha": 0.7},
    "center_lights": {"c": 'red', "s": 200, "marker": '*', "label": 'תאורה מרכזית', "alpha": 0.9},
    "furniture_lights": {"c": 'orange', "s": 120, "marker": '*', "label": 'תאורת ריהוט', "alpha": 0.8},
    "furniture": {"c": 'green', "s": 120, "marker": 'o', "label": 'ריהוט', "alpha": 0.7},
    "other": {"c": 'gray', "s": 80, "marker": '.', "label": 'אחר', "alpha": 0.5},
    "edge_alpha": 0.6,
    "grid_alpha": 0.3
}