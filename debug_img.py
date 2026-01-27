import cv2
import numpy as np
import os

def check_img(path):
    print(f"Checking path: {path}")
    if not os.path.exists(path):
        print("Path does not exist")
        return
    
    # Try reading with imdecode for safety with non-ascii paths
    try:
        data = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            print("cv2.imdecode returned None")
            return
        print(f"Shape: {img.shape}")
    except Exception as e:
        print(f"Error: {e}")

path = r"d:\((Python TOOL\4cam分析照片\4cam_stripe_checker_v2\GOOD\4cam_cam01_dre_on.jpg"
check_img(path)
