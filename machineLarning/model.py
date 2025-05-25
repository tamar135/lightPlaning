import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Input, Conv2D, MaxPooling2D, Flatten, Dense, Dropout, Reshape, Lambda
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from tensorflow.keras.optimizers import Adam
import numpy as np
import pandas as pd
import os
import cv2
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image, ImageDraw, ImageFont
import io

# הגדרות גלובליות
TARGET_SIZE = (320, 320)  # גודל תמונה גדול יותר לזיהוי טוב של חדרים קטנים
BATCH_SIZE = 4
MAX_DETECTIONS = 20  # מספר מקסימלי של חדרים שניתן לזהות בתמונה אחת


# פונקציה לטעינת הנתונים
def load_floorplan_data(annotations_file, images_dir):
    # טעינת אנוטציות
    df = pd.read_csv(annotations_file, sep=" ", header=None)
    if len(df.columns) != 8:  # בדיקה אם הפורמט תואם
        df = pd.read_csv(annotations_file)

    # קביעת שמות העמודות
    if len(df.columns) == 8:
        df.columns = ['filename', 'width', 'height', 'class', 'xmin', 'ymin', 'xmax', 'ymax']

    # מיפוי שמות מחלקות למספרים
    class_mapping = {name: i for i, name in enumerate(df['class'].unique())}
    id_to_class = {i: name for name, i in class_mapping.items()}

    # הדפסת מידע על הנתונים
    print(f"טעינת {len(df)} אנוטציות מ-{df['filename'].nunique()} תמונות")
    print(f"סוגי חדרים: {', '.join(class_mapping.keys())}")

    return df, class_mapping, id_to_class, images_dir


# הכנת הנתונים במבנה המתאים לזיהוי אובייקטים מרובים
def prepare_multiobject_data(df, images_dir, target_size=TARGET_SIZE, max_objects=MAX_DETECTIONS):
    # מיפוי מחלקות
    class_mapping = {name: i for i, name in enumerate(df['class'].unique())}
    num_classes = len(class_mapping)

    # רשימות לנתונים
    images = []
    all_bboxes = []
    all_labels = []

    # עיבוד תמונה אחר תמונה
    unique_images = df['filename'].unique()

    for img_name in unique_images:
        # קבלת אנוטציות לתמונה זו
        img_df = df[df['filename'] == img_name]

        # טעינת התמונה
        img_path = os.path.join(images_dir, img_name)
        if not os.path.exists(img_path):
            print(f"הקובץ {img_path} לא נמצא, מדלג")
            continue

        img = cv2.imread(img_path)
        if img is None:
            print(f"לא ניתן לקרוא את {img_path}, מדלג")
            continue

        # שמירת הגודל המקורי
        orig_height, orig_width = img.shape[:2]

        # עיבוד התמונה
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, target_size)
        img = img.astype(np.float32) / 255.0

        # הכנת מערכים לתיבות ותוויות לתמונה זו
        bboxes = np.zeros((max_objects, 4))
        labels = np.zeros(max_objects)

        # מילוי האנוטציות
        for i, (_, row) in enumerate(img_df.iterrows()):
            if i >= max_objects:
                print(f"אזהרה: יותר מ-{max_objects} אובייקטים בתמונה {img_name}")
                break

            # נרמול של הקואורדינטות
            x1 = row['xmin'] / orig_width
            y1 = row['ymin'] / orig_height
            x2 = row['xmax'] / orig_width
            y2 = row['ymax'] / orig_height

            # וידוא שהקואורדינטות תקינות
            x1, x2 = max(0, x1), min(1, x2)
            y1, y2 = max(0, y1), min(1, y2)

            if x2 <= x1 or y2 <= y1:
                print(f"אזהרה: קואורדינטות לא תקינות בתמונה {img_name}")
                continue

            # שמירת האנוטציה
            bboxes[i] = [x1, y1, x2, y2]
            labels[i] = class_mapping[row['class']]

        # הוספה לרשימות הראשיות
        images.append(img)
        all_bboxes.append(bboxes)
        all_labels.append(labels)

    return np.array(images), np.array(all_bboxes), np.array(all_labels), num_classes


# בניית מודל לזיהוי חדרים מרובים בתוכנית קומה
def build_room_detection_model(input_shape, num_classes, max_detections=MAX_DETECTIONS):
    # מודל בסיס קל
    base_model = MobileNetV2(
        weights='imagenet',
        include_top=False,
        input_shape=input_shape
    )
    base_model.trainable = False  # הקפאת השכבות לאימון מהיר יותר

    # בניית המודל
    inputs = Input(shape=input_shape)
    x = base_model(inputs)

    # שכבות לזיהוי אובייקטים
    x = Conv2D(256, (3, 3), activation='relu', padding='same')(x)
    x = MaxPooling2D()(x)
    x = Conv2D(128, (3, 3), activation='relu', padding='same')(x)
    x = Flatten()(x)
    x = Dense(512, activation='relu')(x)
    x = Dropout(0.3)(x)

    # פלט לתיבות גבול - לכל חדר 4 ערכים (x1, y1, x2, y2)
    bbox_output = Dense(max_detections * 4, name='bbox_output')(x)
    bbox_output = Reshape((max_detections, 4))(bbox_output)

    # פלט לסיווג - לכל חדר num_classes אפשרויות
    class_output = Dense(max_detections * num_classes, name='class_output')(x)
    class_output = Reshape((max_detections, num_classes))(class_output)
    class_output = tf.keras.layers.Activation('softmax')(class_output)

    # פלט למיסוך - האם יש אובייקט או לא בכל מיקום
    mask_output = Dense(max_detections, activation='sigmoid', name='mask_output')(x)

    model = tf.keras.Model(inputs=inputs, outputs=[bbox_output, class_output, mask_output])

    model.compile(
        optimizer=Adam(learning_rate=0.0001),
        loss={
            'bbox_output': 'mse',  # שגיאה ריבועית ממוצעת לתיבות גבול
            'class_output': 'categorical_crossentropy',  # אנטרופיה צולבת לסיווג
            'mask_output': 'binary_crossentropy'  # אנטרופיה בינארית למיסוך
        },
        loss_weights={
            'bbox_output': 1.0,
            'class_output': 1.0,
            'mask_output': 0.5
        }
    )

    return model


# אימון המודל עם שמירת ביניים
def train_detection_model(model, images, bboxes, labels, num_classes, val_split=0.2, epochs=20):
    # הכנת נתוני אימון
    num_samples = len(images)
    num_val = int(num_samples * val_split)

    # חלוקה אקראית לאימון ואימות
    indices = np.random.permutation(num_samples)
    train_idx, val_idx = indices[num_val:], indices[:num_val]

    train_images = images[train_idx]
    train_bboxes = bboxes[train_idx]
    train_labels = labels[train_idx]

    val_images = images[val_idx]
    val_bboxes = bboxes[val_idx]
    val_labels = labels[val_idx]

    # המרת התוויות לפורמט one-hot
    train_labels_onehot = tf.keras.utils.to_categorical(train_labels, num_classes)
    val_labels_onehot = tf.keras.utils.to_categorical(val_labels, num_classes)

    # יצירת מסכות - 1 אם יש אובייקט, 0 אם אין
    train_masks = (train_labels > 0).astype(np.float32)
    val_masks = (val_labels > 0).astype(np.float32)

    # הגדרת callbacks
    callbacks = [
        EarlyStopping(patience=8, restore_best_weights=True),
        ModelCheckpoint('best_room_detection_model.h5', save_best_only=True)
    ]

    # אימון המודל
    history = model.fit(
        train_images,
        {
            'bbox_output': train_bboxes,
            'class_output': train_labels_onehot,
            'mask_output': train_masks
        },
        validation_data=(
            val_images,
            {
                'bbox_output': val_bboxes,
                'class_output': val_labels_onehot,
                'mask_output': val_masks
            }
        ),
        epochs=epochs,
        batch_size=BATCH_SIZE,
        callbacks=callbacks
    )

    return model, history


# פונקציה לזיהוי חדרים בתמונה חדשה
def detect_rooms_in_image(model, image_path, id_to_class, threshold=0.5):
    """
    זיהוי חדרים בתמונת תוכנית קומה חדשה

    :param model: המודל המאומן
    :param image_path: נתיב לתמונה
    :param id_to_class: מילון להמרת מזהי מחלקות לשמות
    :param threshold: סף הסתברות לזיהוי
    :return: תוצאות הזיהוי ותמונה עם סימונים
    """
    # טעינת התמונה
    img = cv2.imread(image_path)
    if img is None:
        return None, None

    # שמירת הגודל המקורי
    orig_height, orig_width = img.shape[:2]

    # עיבוד התמונה
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_resized = cv2.resize(img_rgb, TARGET_SIZE)
    img_normalized = img_resized.astype(np.float32) / 255.0

    # ביצוע חיזוי
    bbox_pred, class_pred, mask_pred = model.predict(np.expand_dims(img_normalized, axis=0))

    # תמונה לסימון התוצאות
    result_img = img_rgb.copy()

    # עיבוד התוצאות
    results = []

    for i in range(MAX_DETECTIONS):
        # בדיקה אם יש אובייקט במיקום זה
        if mask_pred[0][i] < threshold:
            continue

        # קבלת תיבת הגבול
        bbox = bbox_pred[0][i]

        # המרה לקואורדינטות בתמונה המקורית
        x1 = int(bbox[0] * orig_width)
        y1 = int(bbox[1] * orig_height)
        x2 = int(bbox[2] * orig_width)
        y2 = int(bbox[3] * orig_height)

        # בדיקת תקינות הקואורדינטות
        if x1 >= x2 or y1 >= y2:
            continue

        # קבלת המחלקה
        class_id = np.argmax(class_pred[0][i])
        confidence = class_pred[0][i][class_id]

        # דילוג על רקע (מחלקה 0)
        if class_id == 0:
            continue

        # המרת מזהה מחלקה לשם
        class_name = id_to_class.get(class_id, "לא ידוע")

        # הוספת תוצאה
        results.append({
            'class': class_name,
            'confidence': float(confidence),
            'bbox': [x1, y1, x2, y2]
        })

        # ציור תיבת גבול
        cv2.rectangle(result_img, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # הוספת תווית
        label = f"{class_name} ({confidence:.2f})"
        cv2.putText(result_img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return results, result_img


# פונקציה ראשית לאימון המודל
def train_floorplan_model(train_annotations, train_images_dir):
    # טעינת הנתונים
    print("טוען נתונים...")
    df, class_mapping, id_to_class, _ = load_floorplan_data(train_annotations, train_images_dir)

    # הכנת הנתונים
    print("מכין נתונים לאימון...")
    images, bboxes, labels, num_classes = prepare_multiobject_data(df, train_images_dir)

    # בניית המודל
    print(f"בונה מודל לזיהוי חדרים ({num_classes} סוגים)...")
    model = build_room_detection_model(TARGET_SIZE + (3,), num_classes)

    # אימון המודל
    print("מתחיל אימון המודל...")
    model, history = train_detection_model(model, images, bboxes, labels, num_classes, epochs=20)

    # שמירת המודל ומיפוי המחלקות
    model.save('floorplan_room_detection_model.h5')

    import json
    with open('room_class_mapping.json', 'w') as f:
        json.dump(id_to_class, f)

    print("המודל נשמר בהצלחה!")

    return model, id_to_class


# פונקציה לקבלת תמונה מהמשתמש וזיהוי החדרים בה
def analyze_floorplan(model_path, class_mapping_path, image_path):
    """
    ניתוח תוכנית קומה שהמשתמש העלה

    :param model_path: נתיב למודל השמור
    :param class_mapping_path: נתיב למיפוי המחלקות
    :param image_path: נתיב לתמונה שהמשתמש העלה
    :return: תוצאות הזיהוי והתמונה המסומנת
    """
    # טעינת המודל
    model = tf.keras.models.load_model(model_path)

    # טעינת מיפוי המחלקות
    with open(class_mapping_path, 'r') as f:
        id_to_class = json.load(f)

    # המרת מחרוזות מפתח למספרים
    id_to_class = {int(k): v for k, v in id_to_class.items()}

    # זיהוי חדרים בתמונה
    results, result_img = detect_rooms_in_image(model, image_path, id_to_class)

    if results is None:
        return None, None

    # הכנת סיכום טקסטואלי
    summary = f"זוהו {len(results)} חדרים בתוכנית הקומה:\n\n"

    for i, result in enumerate(results):
        summary += f"{i + 1}. {result['class']} - רמת ביטחון: {result['confidence']:.2f}\n"

    return summary, result_img


# ממשק משתמש פשוט (באמצעות קובץ HTML ו-Flask)
def create_simple_ui():
    from flask import Flask, request, render_template_string, send_file

    app = Flask(__name__)

    # תבנית HTML פשוטה
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>זיהוי חדרים בתוכנית קומה</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #333; }
            .result-container { margin-top: 20px; }
            .result-image { max-width: 100%; border: 1px solid #ddd; margin-top: 10px; }
            .result-text { white-space: pre-line; background: #f5f5f5; padding: 10px; border-radius: 4px; }
        </style>
    </head>
    <body>
        <h1>זיהוי חדרים בתוכנית קומה</h1>
        <form method="post" enctype="multipart/form-data">
            <div>
                <label for="file">בחר תמונת תוכנית קומה:</label>
                <input type="file" id="file" name="file" accept="image/*" required>
            </div>
            <div style="margin-top: 10px;">
                <button type="submit">זהה חדרים</button>
            </div>
        </form>

        {% if result_image %}
        <div class="result-container">
            <h2>תוצאות הזיהוי:</h2>
            <div class="result-text">{{ result_text }}</div>
            <h3>תמונה מסומנת:</h3>
            <img src="{{ result_image }}" class="result-image">
        </div>
        {% endif %}
    </body>
    </html>
    """

    @app.route('/', methods=['GET', 'POST'])
    def index():
        result_text = None
        result_image = None

        if request.method == 'POST':
            # קבלת הקובץ שהועלה
            file = request.files['file']
            if file:
                # שמירת הקובץ
                temp_path = 'temp_floorplan.jpg'
                file.save(temp_path)

                # ניתוח התמונה
                summary, img_result = analyze_floorplan(
                    'floorplan_room_detection_model.h5',
                    'room_class_mapping.json',
                    temp_path
                )

                if summary:
                    result_text = summary

                    # שמירת התמונה המסומנת לצפייה
                    result_path = 'static/result.jpg'
                    os.makedirs('static', exist_ok=True)
                    cv2.imwrite(result_path, cv2.cvtColor(img_result, cv2.COLOR_RGB2BGR))
                    result_image = result_path

        return render_template_string(html_template, result_text=result_text, result_image=result_image)

    # הרצת השרת
    app.run(debug=True)


# פונקציה ראשית
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'train':
        # מצב אימון
        train_annotations = 'C:\\Users\\user\\Documents\\fastApiProject\\machineLarning\\data\\train\\_annotations.csv'
        train_images_dir = 'C:\\Users\\user\\Documents\\fastApiProject\\machineLarning\\data\\train\\images'
        train_floorplan_model(train_annotations, train_images_dir)
    else:
        # מצב ממשק משתמש
        if os.path.exists('floorplan_room_detection_model.h5') and os.path.exists('room_class_mapping.json'):
            create_simple_ui()
        else:
            print("שגיאה: המודל לא נמצא. אנא הרץ קודם את תהליך האימון (python script.py train)")