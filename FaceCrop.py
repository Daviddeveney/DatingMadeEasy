import cv2
import os
import glob
import numpy as np
from PIL import Image

# Load the DNN model for face detection
model_file = "./models/res10_300x300_ssd_iter_140000.caffemodel"
config_file = "./models/deploy.prototxt"
net = cv2.dnn.readNetFromCaffe(config_file, model_file)

def detect_and_crop_main_face(img):
    try:
        # Convert the PIL Image to OpenCV format
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        h, w = img.shape[:2]

        # Prepare the image for DNN face detection
        blob = cv2.dnn.blobFromImage(img, 1.0, (300, 300), (104.0, 177.0, 123.0))

        # Perform DNN face detection
        net.setInput(blob)
        detections = net.forward()

        main_face = None
        max_confidence = 0

        for i in range(detections.shape[2]):
            # Get the confidence of the detected face
            confidence = detections[0, 0, i, 2]

            # Only consider detections with a confidence greater than 0.5
            if confidence > 0.5:
                # Get the bounding box coordinates
                box = detections[0, 0, i, 3:7] * [w, h, w, h]
                x, y, x2, y2 = np.clip(box.astype("int"), 0, [w, h, w, h])

                # Crop the face
                cropped_face = img[y:y2, x:x2]

                if confidence > max_confidence:
                    max_confidence = confidence
                    main_face = cropped_face

        return main_face
    except Exception as e:
        print(f"Error processing image: {e}")
        return None

def main():
    # Process all images in the unclassified folder
    unclassified_folder = './images/unclassified/*'
    image_extensions = ('.png', '.jpg', '.jpeg')

    for image_path in glob.glob(unclassified_folder):
        if image_path.lower().endswith(image_extensions):
            print(f"Processing image: {image_path}")
            main_face = detect_and_crop_main_face(image_path)

            if main_face is not None:
                # Overwrite the original image with the cropped main face
                cv2.imwrite(image_path, main_face)
                print(f"Updated {image_path} with main face")
            else:
                # Delete the original image if there is an issue or no face detected
                os.remove(image_path)
                print(f"Deleted {image_path}")

if __name__ == '__main__':
    main()
