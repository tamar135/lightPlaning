import logging
import os
import pandas as pd
from PIL import Image
import numpy as np

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

train_dir = r'C:\Users\user\Documents\fastApiProject\machineLarning\data\train'
csv_path = os.path.join(train_dir, '_annotations.csv')

try:
    # טעינת קובץ התיוגים
    labels_df = pd.read_csv(csv_path)
    logger.debug("CSV loaded successfully")
    print("=== 5 השורות הראשונות מקובץ התיוגים ===")
    print(labels_df.head(5))
    print("\nמספר רשומות:", len(labels_df))
    print("עמודות:", labels_df.columns.tolist())

    # ספירת קבצים ייחודיים
    if 'filename' in labels_df.columns:
        unique_files = labels_df['filename'].nunique()
        print(f"מספר קבצים ייחודיים בקובץ התיוגים: {unique_files}")

        # הצגת 5 הקבצים הראשונים
        first_5_files = labels_df['filename'].unique()[:5]
        print("\n5 קבצי התמונות הראשונים בתיוגים:")
        for f in first_5_files:
            print(f"  - {f}")

    # מציאת קבצי תמונות בתיקייה
    image_extensions = ['.jpg', '.jpeg', '.png']
    image_files = []

    for file in os.listdir(train_dir):
        file_path = os.path.join(train_dir, file)
        if os.path.isfile(file_path) and any(file.lower().endswith(ext) for ext in image_extensions):
            image_files.append(file_path)

    logger.debug(f"Found {len(image_files)} image files in directory")
    print(f"\n=== נמצאו {len(image_files)} קבצי תמונה בתיקייה ===")

    # הצגת 5 שמות הקבצים הראשונים
    print("5 קבצי התמונות הראשונים בתיקייה:")
    for i, img_path in enumerate(sorted(image_files)[:5]):
        print(f"  {i + 1}. {os.path.basename(img_path)}")

    # בדיקת גדלי תמונות וחילוץ מידע
    max_to_check = min(20, len(image_files))
    print(f"\nבודק גדלי תמונות (ראשונות {max_to_check})...")

    shapes = []
    for i, img_path in enumerate(sorted(image_files)[:max_to_check]):
        try:
            with Image.open(img_path) as img:
                shapes.append(img.size)
                if i < 5:
                    print(f"  {os.path.basename(img_path)}: {img.size} (רוחב×גובה), מצב: {img.mode}")
        except Exception as e:
            logger.error(f"Error processing {os.path.basename(img_path)}: {e}")

    # ניתוח גדלי התמונות
    unique_shapes = set(shapes)
    if len(unique_shapes) == 1:
        print(f"\nכל התמונות באותו גודל: {next(iter(unique_shapes))}")
    else:
        print(f"\nהתמונות בגדלים שונים. נמצאו {len(unique_shapes)} גדלים שונים:")
        for shape in unique_shapes:
            count = shapes.count(shape)
            print(f"  גודל {shape}: {count} תמונות")

    # בדיקת התאמה בין התמונות לתיוגים
    if 'filename' in labels_df.columns:
        print("\n=== בדיקת התאמה בין תמונות לתיוגים ===")

        matched_count = 0
        image_basenames = [os.path.basename(path) for path in image_files]

        for i, filename in enumerate(image_basenames[:max_to_check]):
            # חיפוש בקובץ CSV
            matches = labels_df[labels_df['filename'] == filename]

            if not matches.empty:
                matched_count += 1
                if matched_count == 1:
                    print("\nדוגמה להתאמה:")
                    print(f"  תמונה: {filename}")
                    print(f"  תיוגים נמצאו: {len(matches)} רשומות")
                    print(f"  תיוג ראשון: {matches.iloc[0].to_dict()}")

        print(f"\nנמצאו התאמות עבור {matched_count} מתוך {min(max_to_check, len(image_files))} התמונות שנבדקו")

        # בדיקה מהצד השני - האם כל התיוגים מתאימים לתמונות קיימות
        labeled_files = labels_df['filename'].unique()
        existing_files = set(image_basenames)

        missing_files = [f for f in labeled_files if f not in existing_files]
        if missing_files:
            print(f"\nנמצאו {len(missing_files)} קבצים בתיוגים שאינם קיימים בתיקייה:")
            for f in missing_files[:5]:
                print(f"  - {f}")
            if len(missing_files) > 5:
                print(f"  ... ועוד {len(missing_files) - 5} קבצים נוספים")
        else:
            print("\nכל הקבצים המתויגים נמצאים בתיקייה")

except Exception as e:
    logger.error(f"An error occurred: {e}", exc_info=True)