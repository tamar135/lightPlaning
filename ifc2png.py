# import aspose.cad as c
# from aspose.cad import Color  # הוספת ייבוא של מחלקת Color
# from aspose.cad.imageoptions import PngOptions  # הוספת ייבוא של PngOptions
#
# image = c.Image.load("C:\\Users\\user\\Desktop\\פרויקט גמר\\fastApiProject\\upload\\לתמר.ifc")
#
# cadRasterizationOptions = c.imageoptions.CadRasterizationOptions()
# cadRasterizationOptions.page_height = 800.5
# cadRasterizationOptions.page_width = 800.5
# cadRasterizationOptions.zoom = 1.5
# cadRasterizationOptions.layers = "Layer"
# cadRasterizationOptions.background_color = Color.green  # עכשיו Color מוגדר
#
# options = PngOptions()  # עכשיו PngOptions מוגדר
# options.vector_rasterization_options = cadRasterizationOptions
#
# image.save("result.png", options)

import aspose.cad as c
from aspose.cad.imageoptions import PngOptions
import os
from PIL import Image
import numpy as np


def convert_ifc_smart_crop(ifc_path):
    """המרה עם זיהוי אוטומטי של סימן המים וקיצוץ"""

    # המרה ראשונית
    image = c.Image.load(ifc_path)

    cadRasterizationOptions = c.imageoptions.CadRasterizationOptions()
    cadRasterizationOptions.page_height = 1000
    cadRasterizationOptions.page_width = 1000
    cadRasterizationOptions.zoom = 1.5

    options = PngOptions()
    options.vector_rasterization_options = cadRasterizationOptions

    temp_path = "temp_image.png"
    image.save(temp_path, options)

    # ניתוח התמונה וקיצוץ חכם
    with Image.open(temp_path) as img:
        img_array = np.array(img)
        width, height = img.size

        # חיפוש אזור לבן בחלק העליון (סימן מים)
        top_section = img_array[:100, :, :]  # 100 פיקסלים עליונים

        # זיהוי אזור לבן (סימן מים)
        white_pixels = np.all(top_section > 200, axis=2)  # פיקסלים לבנים

        if np.sum(white_pixels) > 1000:  # אם יש הרבה פיקסלים לבנים
            crop_top = 120  # קצץ יותר
        else:
            crop_top = 50  # קצץ פחות

        # קיצוץ התמונה
        cropped = img.crop((0, crop_top, width, height))

        # שמירה סופית
        output_dir = os.path.dirname(ifc_path)
        output_filename = os.path.splitext(os.path.basename(ifc_path))[0] + ".png"
        output_path = os.path.join(output_dir, output_filename)

        cropped.save(output_path)

    # ניקוי
    os.remove(temp_path)

    print(f"התמונה נשמרה (ללא סימן מים) ב: {output_path}")
    return output_path


# התקנה נדרשת:
# pip install pillow numpy

# שימוש
ifc_path = "C:\\Users\\user\\Desktop\\פרויקט גמר\\fastApiProject\\upload\\לתמר.ifc"
convert_ifc_smart_crop(ifc_path)