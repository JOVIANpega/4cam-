import cv2
import numpy as np
import os

def check_circles(folder):
    files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.png'))]
    print(f"Checking {len(files)} files for circles...")
    
    for f in files:
        path = os.path.join(folder, f)
        data = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None: continue
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Simple circle detection
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 100, param1=50, param2=30, minRadius=10, maxRadius=100)
        
        if circles is not None:
            print(f"File: {f} -> Found {len(circles[0])} circles!")
        else:
            print(f"File: {f} -> No circles detected.")

if __name__ == "__main__":
    check_circles("IMAGE")
