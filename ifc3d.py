import ifcopenshell
import os
import json
import argparse
import tempfile
import numpy as np
import plotly.graph_objects as go
from MODEL.database import Database
from MODEL.Usage import Usage
from MODEL.Light import Light
import logging

# הגדרת לוגר
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_visualization_html(ifc_path, lights, output_file):
    """
    יוצר קובץ HTML עם ויזואליזציה אינטראקטיבית של קובץ IFC

    Args:
        ifc_path: נתיב לקובץ IFC
        lights: רשימת נורות עם מיקום ועוצמה
        output_file: שם הקובץ לשמירת פלט ה-HTML
    """
    try:
        # טעינת מודל ה-IFC
        model = ifcopenshell.open(ifc_path)
        logger.debug(f"קובץ IFC נטען בהצלחה. סכמה: {model.schema}")

        # יצירת הסצנה
        fig = go.Figure()

        # עיבוד האלמנטים
        for element_type in ["IfcWall", "IfcSlab", "IfcWindow", "IfcDoor", "IfcFurnishingElement"]:
            elements = model.by_type(element_type)
            logger.debug(f"מעבד {len(elements)} אלמנטים מסוג {element_type}")

            for element in elements:
                try:
                    # חילוץ מיקום ומידות בסיסיות
                    if hasattr(element, "ObjectPlacement") and element.ObjectPlacement:
                        if hasattr(element.ObjectPlacement,
                                   "RelativePlacement") and element.ObjectPlacement.RelativePlacement:
                            if hasattr(element.ObjectPlacement.RelativePlacement,
                                       "Location") and element.ObjectPlacement.RelativePlacement.Location:
                                coords = element.ObjectPlacement.RelativePlacement.Location.Coordinates
                                x, y, z = coords

                                # קביעת מידות וצבע לפי סוג האלמנט
                                if "IfcWall" in element_type:
                                    color = "lightblue"
                                    width, length, height = 0.2, 3.0, 2.5
                                elif "IfcSlab" in element_type:
                                    color = "lightgreen"
                                    width, length, height = 5.0, 5.0, 0.2
                                elif "IfcWindow" in element_type:
                                    color = "skyblue"
                                    width, length, height = 1.0, 0.1, 1.0
                                    opacity = 0.3
                                elif "IfcDoor" in element_type:
                                    color = "red"
                                    width, length, height = 0.9, 0.1, 2.1
                                    opacity = 0.8
                                else:
                                    color = "brown"
                                    width, length, height = 1.0, 1.0, 0.8
                                    opacity = 0.9

                                # יצירת אובייקט תלת-ממדי עבור האלמנט
                                fig.add_trace(go.Mesh3d(
                                    x=[x, x + width, x + width, x, x, x + width, x + width, x],
                                    y=[y, y, y + length, y + length, y, y, y + length, y + length],
                                    z=[z, z, z, z, z + height, z + height, z + height, z + height],
                                    i=[0, 0, 0, 1, 4, 4],
                                    j=[1, 2, 4, 2, 5, 6],
                                    k=[2, 3, 5, 3, 6, 7],
                                    opacity=0.7,
                                    color=color,
                                    name=f"{element_type} {element.id()}"
                                ))
                except Exception as e:
                    logger.warning(f"שגיאה בעיבוד אלמנט {element.id()}: {str(e)}")

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
            title="הדמיית IFC עם מערכת תאורה",
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
    מעבד נתונים ישירות ממסד הנתונים

    Args:
        usage_id: מזהה השימוש
        output_file: קובץ פלט
    """
    try:
        # התחברות למסד הנתונים
        db = Database()
        usage_dal = Usage(db)
        light_dal = Light(db)

        # שליפת השימוש
        usage_data = usage_dal.get_by_id(usage_id)
        logger.debug(
            f"סוג usage_data: {type(usage_data)}, אורך: {len(usage_data) if hasattr(usage_data, '__len__') else 'N/A'}")

        if not usage_data:
            logger.error(f"לא נמצא שימוש עם מזהה {usage_id}")
            return None

        logger.debug(
            f"מבנה usage_data: {usage_data}, אורך: {len(usage_data) if isinstance(usage_data, tuple) else 'לא טאפל'}")

        floor_plan = None
        if isinstance(usage_data, dict):
            floor_plan = usage_data.get('floor_plan')
        elif isinstance(usage_data, tuple) and len(usage_data) > 3:
            floor_plan = usage_data[3]

        # בדיקה אם יש קובץ IFC
        if not floor_plan:
            logger.error(f"אין קובץ IFC בשימוש {usage_id}")
            return None

        # מציאת floor_plan באופן בטוח
        floor_plan_data = None
        try:
            if isinstance(usage_data, tuple):
                logger.debug(f"אורך הטאפל: {len(usage_data)}")

                # רישום המבנה של הטאפל לצורך דיבוג
                for i in range(len(usage_data)):
                    try:
                        if isinstance(usage_data[i], bytes):
                            logger.debug(f"שדה {i}: סוג {type(usage_data[i])}, גודל {len(usage_data[i])} בתים")
                        else:
                            logger.debug(f"שדה {i}: סוג {type(usage_data[i])}, ערך {usage_data[i]}")
                    except Exception as e:
                        logger.warning(f"שגיאה בבדיקת שדה {i}: {str(e)}")

                # חיפוש שדה שנראה כמו floor_plan
                # ננסה למצוא את השדה שהוא מסוג bytes וגדול מ-1000 בתים
                floor_plan_index = None
                for i in range(len(usage_data)):
                    if isinstance(usage_data[i], bytes) and len(usage_data[i]) > 1000:
                        floor_plan_index = i
                        logger.debug(f"נמצא floor_plan כנראה בשדה {i} בגודל {len(usage_data[i])} בתים")
                        break

                if floor_plan_index is not None:
                    floor_plan_data = usage_data[floor_plan_index]
                else:
                    # אם לא מצאנו שדה גדול, ננסה אינדקס 3 או 4
                    if len(usage_data) > 3:
                        if isinstance(usage_data[3], bytes):
                            floor_plan_data = usage_data[3]
                            logger.debug("משתמש באינדקס 3 לfloor_plan")
                        elif len(usage_data) > 4 and isinstance(usage_data[4], bytes):
                            floor_plan_data = usage_data[4]
                            logger.debug("משתמש באינדקס 4 לfloor_plan")
            else:
                logger.error(f"usage_data אינו טאפל אלא {type(usage_data)}")
                if isinstance(usage_data, dict) and 'floor_plan' in usage_data:
                    floor_plan_data = usage_data['floor_plan']
                    logger.debug("מצאתי floor_plan במילון")

            if not floor_plan_data:
                logger.error(f"לא נמצא שדה floor_plan בנתונים")
                return None

            # בדיקה שזה באמת קובץ בינארי
            if not isinstance(floor_plan_data, bytes):
                logger.error(f"floor_plan אינו מסוג bytes אלא {type(floor_plan_data)}")
                # נסה להמיר אם אפשר
                if isinstance(floor_plan_data, str):
                    floor_plan_data = floor_plan_data.encode('utf-8')
                    logger.debug("המרתי floor_plan מסטרינג לבינארי")
                else:
                    return None

        except Exception as e:
            logger.error(f"שגיאה בגישה לנתוני floor_plan: {str(e)}")
            # הוספת מידע מפורט על השגיאה
            import traceback
            logger.error(traceback.format_exc())
            return None

        # קבלת נתוני הנורות
        lights = light_dal.get_by_usage_id(usage_id)
        light_data = []

        if lights:
            logger.debug(f"נמצאו {len(lights)} נורות")
        else:
            logger.warning(f"לא נמצאו נורות לשימוש {usage_id}")

        for light in lights:
            try:
                if isinstance(light, tuple):
                    logger.debug(f"אורך טאפל נורה: {len(light)}")
                    if len(light) > 5:
                        # עבור כל שדה בטאפל הנורה - בדוק את הסוג שלו
                        for i in range(len(light)):
                            logger.debug(f"נורה שדה {i}: {type(light[i])}")

                        # גישה בטוחה לשדות
                        try:
                            x = float(light[3]) if light[3] is not None else 0
                            y = float(light[4]) if light[4] is not None else 0
                            z = float(light[5]) if light[5] is not None else 0
                            power = float(light[6]) if len(light) > 6 and light[6] is not None else 0
                        except (ValueError, TypeError) as e:
                            logger.warning(f"שגיאה בהמרת ערכי נורה: {str(e)}")
                            x, y, z, power = 0, 0, 0, 300

                        light_data.append({
                            "id": light[0] if light[0] is not None else 0,
                            "x": x,
                            "y": y,
                            "z": z,
                            "power": power
                        })
                    else:
                        logger.warning(f"טאפל נורה קצר מדי: {len(light)}")
                else:
                    logger.warning(f"נורה אינה טאפל אלא {type(light)}")
            except Exception as e:
                logger.warning(f"שגיאה בעיבוד נתוני נורה: {str(e)}")
                continue

        # שמירת הקובץ לקובץ זמני
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as temp_file:
                temp_file.write(floor_plan_data)
                ifc_path = temp_file.name
                logger.debug(f"נכתב קובץ IFC זמני: {ifc_path}, גודל: {os.path.getsize(ifc_path)} בתים")

                # בדיקה שהקובץ נראה תקין
                try:
                    with open(ifc_path, 'rb') as f:
                        header = f.read(100).decode('utf-8', errors='ignore')
                        logger.debug(f"תחילת קובץ IFC: {header}")
                        if "ISO" in header or "STEP" in header or "HEADER" in header or "FILE_DESCRIPTION" in header:
                            logger.debug("הקובץ נראה כמו קובץ IFC תקין")
                        else:
                            logger.warning("הקובץ לא נראה כמו קובץ IFC תקין!")
                except Exception as e:
                    logger.warning(f"שגיאה בבדיקת תחילת הקובץ: {str(e)}")
        except Exception as e:
            logger.error(f"שגיאה בכתיבת קובץ IFC זמני: {str(e)}")
            return None

        # יצירת הויזואליזציה
        try:
            result = create_visualization_html(ifc_path, light_data, output_file)
            logger.debug(f"נוצרה ויזואליזציה: {result}")
            return result
        except Exception as e:
            logger.error(f"שגיאה ביצירת ויזואליזציה: {str(e)}")
            # הוספת traceback מפורט
            import traceback
            logger.error(traceback.format_exc())
            return None
        finally:
            # ניקוי קובץ זמני
            try:
                os.remove(ifc_path)
                logger.debug(f"נמחק קובץ IFC זמני: {ifc_path}")
            except Exception as e:
                logger.warning(f"שגיאה במחיקת קובץ זמני: {str(e)}")
    except Exception as e:
        logger.error(f"שגיאה כללית בתהליך: {str(e)}")
        # הוספת traceback מפורט
        import traceback
        logger.error(traceback.format_exc())
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='יצירת ויזואליזציה לקובץ IFC')
    parser.add_argument('--usage_id', type=int, help='מזהה השימוש')
    parser.add_argument('--output', default='ifc_visualization.html', help='נתיב לקובץ הפלט')

    args = parser.parse_args()

    # הוספת לוג על הפרמטרים שהתקבלו
    logger.debug(f"התקבלו פרמטרים: usage_id={args.usage_id}, output={args.output}")

    result = process_from_database(args.usage_id, args.output)

    if result:
        print(f"נוצרה ויזואליזציה בהצלחה: {result}")
        # פתיחת הקובץ בדפדפן אם מריצים ישירות
        if __name__ == "__main__" and os.path.exists(result):
            import webbrowser

            webbrowser.open('file://' + os.path.abspath(result))
    else:
        print("לא ניתן ליצור ויזואליזציה")