import ezdxf
import plotly.graph_objects as go
import numpy as np
import tempfile
import logging
import os

# הגדרת לוגר
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_dxf_visualization_html(dxf_path, lights, output_file):
    """
    יוצר קובץ HTML עם ויזואליזציה אינטראקטיבית של קובץ DXF בתלת מימד
    """
    try:
        # טעינת מודל ה-DXF
        doc = ezdxf.readfile(dxf_path)
        modelspace = doc.modelspace()
        logger.debug(f"קובץ DXF נטען בהצלחה. גרסה: {doc.dxfversion}")

        # יצירת הסצנה
        fig = go.Figure()

        # עיבוד האלמנטים לפי סוגים
        element_types = {
            "walls": ['LINE', 'LWPOLYLINE'],
            "furniture": ['INSERT', 'CIRCLE'],
            "other": ['ARC', 'TEXT', 'MTEXT', 'SOLID']
        }

        # מיפוי לצבעים לפי סוג אלמנט
        element_colors = {
            "wall": "lightblue",
            "window": "skyblue",
            "door": "red",
            "table": "brown",
            "desk": "brown",
            "chair": "orange",
            "bed": "purple",
            "other": "gray"
        }

        # מיפוי לגבהים ברירת מחדל
        default_heights = {
            "wall": 2.5,
            "window": 1.0,
            "door": 2.1,
            "table": 0.75,
            "desk": 0.75,
            "chair": 0.8,
            "bed": 0.6,
            "other": 0.5
        }

        for category, entity_types in element_types.items():
            for entity_type in entity_types:
                entities = modelspace.query(entity_type)
                logger.debug(f"נמצאו {len(entities)} אלמנטים מסוג {entity_type}")

                for entity in entities:
                    try:
                        # זיהוי סוג האלמנט מהשכבה
                        element_type = "other"  # ברירת מחדל

                        if hasattr(entity, 'dxf') and hasattr(entity.dxf, 'layer'):
                            layer_name = entity.dxf.layer.upper()

                            # זיהוי פשוט לפי שם השכבה
                            if any(kw in layer_name for kw in ["WALL", "קיר", "PARTITION"]):
                                element_type = "wall"
                            elif any(kw in layer_name for kw in ["WINDOW", "חלון", "GLAZ"]):
                                element_type = "window"
                            elif any(kw in layer_name for kw in ["DOOR", "דלת"]):
                                element_type = "door"
                            elif any(kw in layer_name for kw in ["TABLE", "שולחן"]):
                                element_type = "table"
                            elif any(kw in layer_name for kw in ["CHAIR", "כיסא"]):
                                element_type = "chair"
                            elif any(kw in layer_name for kw in ["BED", "מיטה"]):
                                element_type = "bed"
                            elif any(kw in layer_name for kw in ["DESK", "שולחן עבודה"]):
                                element_type = "desk"

                        # צבע לפי סוג האלמנט
                        color = element_colors.get(element_type, "gray")
                        height = default_heights.get(element_type, 0.5)

                        # לוגיקה שונה לפי סוג הישות
                        if entity_type == 'LINE':
                            start = entity.dxf.start
                            end = entity.dxf.end

                            # הוספת קו פשוט
                            fig.add_trace(go.Scatter3d(
                                x=[start[0], end[0]],
                                y=[start[1], end[1]],
                                z=[0, 0],
                                mode='lines',
                                line=dict(color=color, width=5),
                                name=f'{element_type}_{entity.dxf.handle}'
                            ))

                            # הוספת קיר/אלמנט בגובה (אקסטרוזיה של הקו)
                            fig.add_trace(go.Mesh3d(
                                x=[start[0], end[0], end[0], start[0], start[0], end[0], end[0], start[0]],
                                y=[start[1], end[1], end[1], start[1], start[1], end[1], end[1], start[1]],
                                z=[0, 0, height, height, 0, 0, height, height],
                                i=[0, 0, 0, 1, 4, 4],
                                j=[1, 2, 4, 2, 5, 6],
                                k=[2, 3, 5, 3, 6, 7],
                                opacity=0.7,
                                color=color,
                                name=f'{element_type}_{entity.dxf.handle}'
                            ))

                        elif entity_type == 'LWPOLYLINE':
                            # עיבוד פוליליין
                            if hasattr(entity, 'get_points'):
                                points = list(entity.get_points())
                            else:
                                points = list(entity.vertices())

                            if len(points) > 1:
                                x_vals = [p[0] for p in points]
                                y_vals = [p[1] for p in points]
                                z_vals = [0] * len(points)

                                # הוספת הקו הבסיסי
                                fig.add_trace(go.Scatter3d(
                                    x=x_vals,
                                    y=y_vals,
                                    z=z_vals,
                                    mode='lines',
                                    line=dict(color=color, width=3),
                                    name=f'{element_type}_{entity.dxf.handle}'
                                ))

                                # אם הפוליליין סגור, נוכל להוסיף משטח
                                if entity.closed:
                                    # הוספת רצפה (משטח בגובה 0)
                                    fig.add_trace(go.Mesh3d(
                                        x=x_vals,
                                        y=y_vals,
                                        z=z_vals,
                                        opacity=0.5,
                                        color="lightgray",
                                        name=f'Floor_{entity.dxf.handle}'
                                    ))

                                    # אם זה קיר, נוסיף אקסטרוזיה לגובה
                                    if element_type == "wall":
                                        # בניית נקודות לקיר בגובה
                                        x_extrude = []
                                        y_extrude = []
                                        z_extrude = []
                                        triangles_i = []
                                        triangles_j = []
                                        triangles_k = []

                                        # בניית האקסטרוזיה
                                        for i in range(len(points)):
                                            # נקודה נוכחית
                                            current = points[i]
                                            # נקודה הבאה (במעגל)
                                            next_point = points[(i + 1) % len(points)]

                                            # הוספת נקודות מלמטה למעלה
                                            idx = len(x_extrude)
                                            x_extrude.extend([current[0], next_point[0], next_point[0], current[0]])
                                            y_extrude.extend([current[1], next_point[1], next_point[1], current[1]])
                                            z_extrude.extend([0, 0, height, height])

                                            # הוספת המשולשים
                                            triangles_i.extend([idx, idx + 2])
                                            triangles_j.extend([idx + 1, idx + 3])
                                            triangles_k.extend([idx + 2, idx])

                                        # יצירת הקיר
                                        fig.add_trace(go.Mesh3d(
                                            x=x_extrude,
                                            y=y_extrude,
                                            z=z_extrude,
                                            i=triangles_i,
                                            j=triangles_j,
                                            k=triangles_k,
                                            opacity=0.7,
                                            color=color,
                                            name=f'Wall_{entity.dxf.handle}'
                                        ))

                        elif entity_type == 'CIRCLE':
                            # עיבוד עיגול
                            center = entity.dxf.center
                            radius = entity.dxf.radius

                            # יצירת עיגול מנקודות
                            theta = np.linspace(0, 2 * np.pi, 36)
                            x = center[0] + radius * np.cos(theta)
                            y = center[1] + radius * np.sin(theta)
                            z = [0] * len(theta)

                            # הוספת העיגול הבסיסי
                            fig.add_trace(go.Scatter3d(
                                x=x,
                                y=y,
                                z=z,
                                mode='lines',
                                line=dict(color=color, width=3),
                                name=f'{element_type}_{entity.dxf.handle}'
                            ))

                            # אם זה כיסא או שולחן, נוסיף נפח בסיסי (צילינדר)
                            if element_type in ["table", "chair"]:
                                # שילוב של משטח עליון ומשטח תחתון
                                fig.add_trace(go.Mesh3d(
                                    x=list(x) + list(x),
                                    y=list(y) + list(y),
                                    z=list(z) + [height] * len(z),
                                    opacity=0.7,
                                    color=color,
                                    name=f'{element_type}_volume_{entity.dxf.handle}'
                                ))

                        elif entity_type == 'INSERT':
                            # עיבוד בלוק
                            insertion = entity.dxf.insert

                            # בדיקה אם יש מידות סקייל
                            scale_x = getattr(entity.dxf, 'xscale', 1)
                            scale_y = getattr(entity.dxf, 'yscale', 1)

                            # מידות ברירת מחדל לפי סוג האלמנט
                            width = 1.0 * scale_x
                            length = 1.0 * scale_y

                            if element_type == "table":
                                width, length = 1.2 * scale_x, 0.8 * scale_y
                            elif element_type == "desk":
                                width, length = 1.6 * scale_x, 0.8 * scale_y
                            elif element_type == "chair":
                                width, length = 0.5 * scale_x, 0.5 * scale_y
                            elif element_type == "bed":
                                width, length = 1.4 * scale_x, 2.0 * scale_y

                            # יצירת תיבה פשוטה
                            x_vals = [insertion[0], insertion[0] + width, insertion[0] + width, insertion[0],
                                      insertion[0], insertion[0] + width, insertion[0] + width, insertion[0]]
                            y_vals = [insertion[1], insertion[1], insertion[1] + length, insertion[1] + length,
                                      insertion[1], insertion[1], insertion[1] + length, insertion[1] + length]
                            z_vals = [0, 0, 0, 0, height, height, height, height]

                            fig.add_trace(go.Mesh3d(
                                x=x_vals,
                                y=y_vals,
                                z=z_vals,
                                i=[0, 0, 0, 1, 4, 4],
                                j=[1, 2, 4, 2, 5, 6],
                                k=[2, 3, 5, 3, 6, 7],
                                opacity=0.7,
                                color=color,
                                name=f'{element_type}_{entity.dxf.handle}'
                            ))

                    except Exception as e:
                        logger.warning(f"שגיאה בעיבוד אלמנט {entity_type}: {str(e)}")

        # הוספת הנורות
        for light in lights:
            if isinstance(light, dict):
                light_id = light.get("id", 0)
                light_x = light.get("x", 0)
                light_y = light.get("y", 0)
                light_z = light.get("z", 0)
                light_power = light.get("power", 300)
            else:
                light_id = 0
                light_x, light_y, light_z, light_power = light

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
                name=f'Light {light_id}'
            ))

            # אפקט האור (חרוט)
            radius = light_power / 100  # רדיוס לפי עוצמה
            fig.add_trace(go.Cone(
                x=[light_x],
                y=[light_y],
                z=[light_z],
                u=[0],
                v=[0],
                w=[-1],  # כיוון כלפי מטה
                sizemode="absolute",
                sizeref=radius,
                showscale=False,
                colorscale=[[0, 'rgba(255, 255, 0, 0.1)'], [1, 'rgba(255, 255, 0, 0.5)']],
                opacity=0.3,
                name=f'Light Cone {light_id}'
            ))

        # הגדרות התצוגה
        fig.update_layout(
            title="הדמיית DXF עם מערכת תאורה",
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
            margin=dict(l=0, r=0, b=0, t=40),
            autosize=True,
            width=1000,
            height=800
        )

        # שמירת הקובץ
        fig.write_html(output_file, auto_open=False, include_plotlyjs='cdn')
        logger.debug(f"נשמר קובץ HTML: {output_file}")

        return output_file

    except Exception as e:
        logger.error(f"שגיאה ביצירת ויזואליזציה: {str(e)}")
        raise


def process_from_database(usage_id, output_file):
    """
    מעבד נתונים ישירות ממסד הנתונים ומייצר קובץ ויזואליזציה

    Args:
        usage_id: מזהה השימוש
        output_file: קובץ פלט

    Returns:
        str: נתיב לקובץ HTML שנוצר
    """
    from MODEL.database import Database
    from MODEL.Usage import Usage
    from MODEL.Light import Light

    try:
        # התחברות למסד הנתונים
        db = Database()
        usage_dal = Usage(db)
        light_dal = Light(db)

        # שליפת השימוש
        usage_data = usage_dal.get_by_id(usage_id)

        if not usage_data:
            logger.error(f"לא נמצא שימוש עם מזהה {usage_id}")
            return None

        # בדיקה אם יש קובץ DXF
        if len(usage_data) <= 3 or not usage_data[3]:
            logger.error(f"אין קובץ DXF בשימוש {usage_id}")
            return None

        # קבלת נתוני הנורות
        lights = light_dal.get_by_usage_id(usage_id)
        light_data = []

        for light in lights:
            if isinstance(light, tuple) and len(light) > 5:
                x = float(light[3]) if light[3] is not None else 0
                y = float(light[4]) if light[4] is not None else 0
                z = float(light[5]) if light[5] is not None else 0
                power = float(light[6]) if light[6] is not None else 0
                light_data.append({
                    "id": light[0],
                    "x": x,
                    "y": y,
                    "z": z,
                    "power": power
                })

        # שמירת הקובץ לקובץ זמני
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as temp_file:
            temp_file.write(usage_data[3])
            dxf_path = temp_file.name

        # יצירת הויזואליזציה
        result = create_dxf_visualization_html(dxf_path, light_data, output_file)

        # ניקוי קובץ זמני
        try:
            os.remove(dxf_path)
        except:
            pass

        return result

    except Exception as e:
        logger.error(f"שגיאה בתהליך הויזואליזציה: {str(e)}")
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='יצירת ויזואליזציה לקובץ DXF')
    parser.add_argument('--usage_id', type=int, help='מזהה השימוש')
    parser.add_argument('--output', default='dxf_visualization.html', help='נתיב לקובץ הפלט')

    args = parser.parse_args()

    result = process_from_database(args.usage_id, args.output)

    if result:
        print(f"נוצרה ויזואליזציה בהצלחה: {result}")
        # פתיחת הקובץ בדפדפן אם מריצים ישירות
        if os.path.exists(result):
            import webbrowser

            webbrowser.open('file://' + os.path.abspath(result))
    else:
        print("לא ניתן ליצור ויזואליזציה")