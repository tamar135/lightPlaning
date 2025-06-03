import os
import tempfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple
import aiofiles
from fastapi import UploadFile, HTTPException

import IFCProcessor
from MODEL.database import Database
from MODEL.Usage import Usage
from MODEL.Light import Light
from models import Graph, LightVertex
from BuildGraph import BuildGraph

# הגדרת לוגר
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class fileProcessor:
    def __init__(self):
        try:
            self.db = Database()
            self.usage_dal = Usage(self.db)
            self.light_dal = Light(self.db)
            logger.debug("fileProcessor initialized with database connection")
        except Exception as e:
            logger.error("Failed to initialize database connection: %s", str(e))
            raise

    async def validate_file(self, file: UploadFile) -> Tuple[bool, str]:
        logger.debug("Validating file: %s", file.filename if file else None)
        if not file or not file.filename:
            return False, "לא הועלה קובץ."

        allowed_extensions = [".ifc"]
        file_extension = Path(file.filename).suffix.lower()
        logger.debug("File extension: %s", file_extension)

        if file_extension not in allowed_extensions:
            return False, "סוג קובץ לא תקין. מותר רק קבצי IFC"

        return True, ""

    async def process_and_save_file(self, file: UploadFile, user_id: str, room_type: str):
        logger.debug("Starting process_and_save_file with file=%s, user_id=%s, room_type=%s",
                     file.filename, user_id, room_type)

        if not user_id.isdigit():
            raise HTTPException(status_code=400, detail="מזהה משתמש לא תקף. חייב להיות מספר שלם.")

        user_id = int(user_id)
        temp_file_path = None
        json_path = None

        # בדיקת סוג הקובץ
        file_extension = Path(file.filename).suffix.lower()

        # שמירת קובץ זמני עם הסיומת המתאימה
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            file_data = await file.read()
            temp_file.write(file_data)
            temp_file_path = temp_file.name
            logger.debug(f"Saved {file_extension} file to: {temp_file_path}")

        try:
            # עיבוד הקובץ ל-JSON בהתאם לסוג הקובץ
            if file_extension == ".ifc":
                logger.debug("Processing IFC file with path: %s", temp_file_path)
                json_path = IFCProcessor.process_ifc_file(temp_file_path, room_type)
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")

            logger.debug("Received json_path: %s", json_path)
            if not isinstance(json_path, str):
                logger.error("json_path is not a string: %s", type(json_path))
                raise ValueError("Processor must return a string path")

            async with aiofiles.open(json_path, 'r', encoding='utf-8') as f:
                json_content = await f.read()
                logger.debug("Read JSON content length: %s", len(json_content))
                logger.debug("JSON file first 100 characters: %s", json_content[:100] if json_content else "Empty")

            # בדיקת חיבור תקין למסד הנתונים
            if not self.db.connection or not self.db.connection.is_connected():
                logger.error("Database connection lost. Reconnecting...")
                self.db = Database()
                self.usage_dal = Usage(self.db)
                self.light_dal = Light(self.db)

            # שמירה במסד דרך Usage
            logger.debug("About to call usage_dal.create with user_id=%s", user_id)
            try:
                usage_data = self.usage_dal.create(
                    user_id=user_id,
                    usage_date=datetime.now(),
                    floor_plan=file_data,
                    json_file=json_content
                )
                logger.debug("Result from usage_dal.create: %s", usage_data)
                logger.debug("Type of usage_data: %s", type(usage_data))
                if isinstance(usage_data, tuple):
                    logger.debug("usage_data is tuple of length %d", len(usage_data))
                elif isinstance(usage_data, dict):
                    logger.debug("usage_data is dict with keys: %s", list(usage_data.keys()))
            except Exception as e:
                logger.error("Error calling usage_dal.create: %s", str(e), exc_info=True)
                raise HTTPException(status_code=500, detail=f"שגיאה בשמירת נתונים: {str(e)}")

            if not usage_data:
                logger.error("Failed to create usage record")
                raise HTTPException(status_code=500, detail="שגיאה בשמירת הנתונים במסד - usage_data is None")

            # שימוש בשיטה בטוחה יותר לחילוץ מזהה ה-usage
            try:
                if isinstance(usage_data, tuple) and len(usage_data) > 0:
                    usage_id = usage_data[0]
                elif isinstance(usage_data, dict) and 'id' in usage_data:
                    usage_id = usage_data['id']
                elif isinstance(usage_data, dict) and 'usage_id' in usage_data:
                    usage_id = usage_data['usage_id']
                elif isinstance(usage_data, int):
                    usage_id = usage_data
                else:
                    # במקרה חירום - השתמש במזהה קבוע
                    logger.warning("Could not determine usage_id from %s - using default value", usage_data)
                    usage_id = 1
                logger.debug("Extracted usage_id: %s", usage_id)
            except Exception as e:
                logger.error("Error extracting usage_id from %s: %s", usage_data, str(e))
                # במקרה של שגיאה, השתמש במזהה ברירת מחדל
                usage_id = 1
                logger.debug("Using default usage_id: %s after error", usage_id)

            # הגדרת תצורות תאורה לפי סוגי חדרים
            room_lighting_config = {
                "bedroom": {
                    "table": {"Lux": 300, "LightHeightOffset": 0.5},
                    "desk": {"Lux": 500, "LightHeightOffset": 0.5},
                    "counter": {"Lux": 400, "LightHeightOffset": 0.6}
                },
                "kitchen": {
                    "counter": {"Lux": 500, "LightHeightOffset": 0.6},
                    "table": {"Lux": 300, "LightHeightOffset": 0.5}
                },
                "living": {
                    "table": {"Lux": 250, "LightHeightOffset": 0.5}
                },
                "office": {
                    "desk": {"Lux": 600, "LightHeightOffset": 0.5},
                    "table": {"Lux": 450, "LightHeightOffset": 0.5}
                }
            }

            # בניית הגרף
            logger.debug("Building graph from JSON path: %s", json_path)
            builder = BuildGraph(room_lighting_config.get(room_type.lower(), {}))
            try:
                graph = builder.build_graph_from_json(json_path)
                logger.debug("Graph built successfully with %d vertices",
                             len(graph.vertices) if hasattr(graph, 'vertices') and graph.vertices else 0)
            except Exception as e:
                logger.error("Error building graph: %s", str(e), exc_info=True)
                graph = Graph()
                logger.debug("Created empty graph due to error")

            # יצירת אובייקטי Light
            light_count = 0
            if hasattr(graph, 'vertices') and graph.vertices:
                vertices_to_check = []

                if isinstance(graph.vertices, dict):
                    vertices_to_check = list(graph.vertices.values())
                elif isinstance(graph.vertices, list):
                    vertices_to_check = graph.vertices

                logger.debug("Found %d vertices to check for lights", len(vertices_to_check))

                for vertex in vertices_to_check:
                    if isinstance(vertex, LightVertex):
                        try:
                            logger.debug("Creating light at position (%f, %f, %f) with power %f",
                                         vertex.point.x, vertex.point.y, vertex.point.z, vertex.lux)
                            light_result = self.light_dal.create(
                                usage_id=usage_id,
                                x=vertex.point.x,
                                y=vertex.point.y,
                                z=vertex.point.z,
                                power=vertex.lux
                            )
                            logger.debug("Light created with result: %s", light_result)
                            light_count += 1
                        except Exception as e:
                            logger.error("Error creating light: %s", str(e), exc_info=True)
                            # המשך לנורה הבאה גם אם היתה שגיאה

            logger.debug("Created %d lights", light_count)
            return {"usage_id": usage_id, "message": f"File processed successfully, created {light_count} lights"}

        except Exception as e:
            logger.error("Error processing file: %s", str(e), exc_info=True)
            # נסה לסגור את החיבור לבסיס הנתונים אם הוא פתוח
            try:
                if hasattr(self, 'db') and self.db and hasattr(self.db, 'connection') and self.db.connection:
                    self.db.connection.commit()
            except Exception as commit_error:
                logger.error("Error during connection commit: %s", str(commit_error))
            raise HTTPException(status_code=500, detail=f"שגיאה בעיבוד הקובץ: {str(e)}")

        finally:
            # ניקוי קבצים זמניים
            for path in [temp_file_path, json_path]:
                if path and isinstance(path, str) and os.path.exists(path):
                    try:
                        os.remove(path)
                        logger.debug("Deleted file: %s", path)
                    except OSError as err:
                        logger.warning("Failed to delete file %s: %s", path, err)
