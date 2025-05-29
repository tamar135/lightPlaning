import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import matplotlib.pyplot as plt
import os

data_dir = 'C:\\Users\\user\\Desktop\\פרויקט גמר\\fastApiProject\\machineLarning\\data'

print("תיקיות זמינות:", os.listdir(data_dir))

# עיבוד מקדים של התמונות
train_datagen = ImageDataGenerator(
    rescale=1./255,  # נרמול ערכי הפיקסלים
    rotation_range=10,
    width_shift_range=0.1,
    height_shift_range=0.1,
    horizontal_flip=True,
    validation_split=0.2  # 20% מהנתונים לוולידציה
)

# טעינת נתוני האימון
train_generator = train_datagen.flow_from_directory(
    data_dir,
    target_size=(150, 150),  # גודל תמונה קטן יותר לחיסכון בחישוב
    batch_size=16,
    class_mode='categorical',
    subset='training'
)

# טעינת נתוני הוולידציה
validation_generator = train_datagen.flow_from_directory(
    data_dir,
    target_size=(150, 150),
    batch_size=16,
    class_mode='categorical',
    subset='validation'
)

# הצגת המיפוי של התוויות
print("מיפוי תוויות:", train_generator.class_indices)

# בניית מודל CNN פשוט
model = tf.keras.Sequential([
    tf.keras.layers.Conv2D(16, (3, 3), activation='relu', input_shape=(150, 150, 3)),
    tf.keras.layers.MaxPooling2D(2, 2),
    tf.keras.layers.Conv2D(32, (3, 3), activation='relu'),
    tf.keras.layers.MaxPooling2D(2, 2),
    tf.keras.layers.Conv2D(64, (3, 3), activation='relu'),
    tf.keras.layers.MaxPooling2D(2, 2),
    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dropout(0.3),
    tf.keras.layers.Dense(train_generator.num_classes, activation='softmax')
])

# קומפילציה של המודל
model.compile(
    optimizer='adam',
    loss='categorical_crossentropy',
    metrics=['accuracy']
)

# סיכום המודל
model.summary()

# אימון המודל
history = model.fit(
    train_generator,
    epochs=10,
    validation_data=validation_generator
)

# הערכת המודל
val_loss, val_accuracy = model.evaluate(validation_generator)
print(f"Validation Loss: {val_loss:.4f}")
print(f"Validation Accuracy: {val_accuracy:.4f}")

# ויזואליזציה של תוצאות האימון
plt.figure(figsize=(12, 4))

# גרף דיוק
plt.subplot(1, 2, 1)
plt.plot(history.history['accuracy'], label='Training Accuracy')
plt.plot(history.history['val_accuracy'], label='Validation Accuracy')
plt.title('Model Accuracy')
plt.xlabel('Epoch')
plt.ylabel('Accuracy')
plt.legend()

# גרף הפסד
plt.subplot(1, 2, 2)
plt.plot(history.history['loss'], label='Training Loss')
plt.plot(history.history['val_loss'], label='Validation Loss')
plt.title('Model Loss')
plt.xlabel('Epoch')
plt.ylabel('Loss')
plt.legend()

plt.show()

# שמירת המודל
model.save('room_classifier.h5')
print("המודל נשמר כ-'room_classifier.h5'")