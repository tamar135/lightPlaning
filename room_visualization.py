# room_visualization.py
import ifcopenshell
import plotly.graph_objects as go
import json
import os
from MODEL.database import Database
from MODEL.Usage import Usage
from MODEL.Light import Light
import webbrowser
from tempfile import NamedTemporaryFile
import sys


def create_visualization(usage_id):
    # התחבר למסד הנתונים
    db = Database()
    usage_dal = Usage(db)
    light_dal = Light(db)

    # קבל את נתוני השימוש
    usage_data = usage_dal.get_by_id(usage_id)
    if not usage_data:
        print(f"לא נמצא שימוש עם מזהה {usage_id}")
        return None

    # קבל את נתוני התאורה
    lights = light_dal.get_by_usage_id(usage_id)

    # המר את נתוני ה-JSON לשימוש
    try:
        json_data = json.loads(usage_data[4]) if usage_data[4] else []
    except json.JSONDecodeError:
        print("שגיאה בפענוח קובץ ה-JSON")
        return None

    # יצירת סצנה
    fig = go.Figure()

    # הוספת אלמנטים מה-JSON
    elements = json_data[4:] if len(json_data) > 4 else []

    for element in elements:
        if not isinstance(element, dict):
            continue

        x = element.get("X", 0)
        y = element.get("Y", 0)
        z = element.get("Z", 0)
        width = element.get("Width", 0)
        length = element.get("Length", 0)
        height = element.get("Height", 0)
        element_type = element.get("ElementType", "unknown").lower()

        # קביעת צבע לפי סוג האלמנט
        color = 'lightgray'  # ברירת מחדל
        opacity = 0.7

        if "wall" in element_type:
            color = 'lightblue'
        elif "table" in element_type or "desk" in element_type:
            color = 'brown'
            opacity = 0.9
        elif "floor" in element_type or "slab" in element_type:
            color = 'lightgreen'
        elif "window" in element_type:
            color = 'skyblue'
            opacity = 0.3
        elif "door" in element_type:
            color = 'red'

        # יצירת קוביה עבור האלמנט
        if width > 0 and length > 0 and height > 0:
            fig.add_trace(go.Mesh3d(
                x=[x, x + width, x + width, x, x, x + width, x + width, x],
                y=[y, y, y + length, y + length, y, y, y + length, y + length],
                z=[z, z, z, z, z + height, z + height, z + height, z + height],
                i=[0, 0, 0, 1, 4, 4],
                j=[1, 2, 4, 2, 5, 6],
                k=[2, 3, 5, 3, 6, 7],
                opacity=opacity,
                color=color,
                name=element_type
            ))

    # הוספת נקודות תאורה
    for light in lights:
        light_x = light[3] if light[3] is not None else 0
        light_y = light[4] if light[4] is not None else 0
        light_z = light[5] if light[5] is not None else 0
        light_power = light[6] if light[6] is not None else 300

        # נקודת האור עצמה
        fig.add_trace(go.Scatter3d(
            x=[light_x],
            y=[light_y],
            z=[light_z],
            mode='markers',
            marker=dict(
                size=10,
                color='yellow',
                symbol='circle',
                line=dict(color='orange', width=1)
            ),
            name=f'Light {light[0]}'
        ))

        # אפקט האור (כדור שקוף)
        radius = light_power / 100  # רדיוס לפי עוצמה
        fig.add_trace(go.Isosurface(
            x=[light_x + (radius * i / 5) for i in range(-5, 6)],
            y=[light_y + (radius * j / 5) for j in range(-5, 6)],
            z=[light_z + (radius * k / 5) for k in range(-5, 6)],
            value=[[[(i ** 2 + j ** 2 + k ** 2) for k in range(-5, 6)] for j in range(-5, 6)] for i in range(-5, 6)],
            isomin=0,
            isomax=radius,
            opacity=0.1,
            colorscale='YlOrRd',
            name=f'Light Effect {light[0]}'
        ))

    # עיצוב הסצנה
    fig.update_layout(
        title="סימולציית תאורת חדר",
        scene=dict(
            aspectmode='data',
            xaxis_title='X [מ׳]',
            yaxis_title='Y [מ׳]',
            zaxis_title='Z [מ׳]'
        ),
        scene_camera=dict(
            up=dict(x=0, y=0, z=1),
            center=dict(x=0, y=0, z=0),
            eye=dict(x=1.5, y=-1.5, z=1.5)
        ),
        margin=dict(l=0, r=0, b=0, t=40)
    )

    return fig


def show_visualization(usage_id):
    fig = create_visualization(usage_id)
    if fig:
        # שמירת הסצנה לקובץ HTML זמני ופתיחה בדפדפן
        temp_file = NamedTemporaryFile(delete=False, suffix='.html')
        fig.write_html(temp_file.name)
        temp_file.close()
        webbrowser.open('file://' + temp_file.name)
        print(f"הסימולציה נפתחה בדפדפן. קובץ HTML זמני: {temp_file.name}")

        return temp_file.name
    else:
        print("לא ניתן ליצור את הסימולציה")
        return None


if __name__ == "__main__":
    # בדיקה אם התקבל מזהה שימוש כפרמטר
    usage_id = int(sys.argv[1]) if len(sys.argv) > 1 else None

    if not usage_id:
        # אם לא התקבל מזהה שימוש, בקש מהמשתמש
        usage_id = int(input("הכנס מזהה שימוש: "))

    html_file = show_visualization(usage_id)