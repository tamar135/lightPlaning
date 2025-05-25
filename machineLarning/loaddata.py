import cv2
import numpy as np
import os

def load_data(image_dir, mask_dir, img_size=(128, 128)):
    images, masks = [], []

    for fname in os.listdir(image_dir):
        img = cv2.imread(os.path.join(image_dir, fname), cv2.IMREAD_GRAYSCALE)
        img = cv2.resize(img, img_size)
        img = img / 255.0
        images.append(img)

        mask = cv2.imread(os.path.join(mask_dir, fname), cv2.IMREAD_GRAYSCALE)
        mask = cv2.resize(mask, img_size)
        masks.append(mask)

    X = np.expand_dims(np.array(images), -1)
    y = np.expand_dims(np.array(masks), -1)

    return X, y
