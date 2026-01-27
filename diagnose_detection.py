import cv2
import numpy as np
import os
from splicing_logic import SplicingProcessor

def imread_unicode(path):
    try:
        data = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"Error reading image: {e}")
        return None

def diagnose(path):
    print(f"--- Diagnosing: {os.path.basename(path)} ---")
    image = imread_unicode(path)
    if image is None:
        print("FAILED: Image could not be loaded (is None)")
        return
    
    h, w = image.shape[:2]
    print(f"Image Resolution: {w}x{h}")
    
    proc = SplicingProcessor()
    roi_points, Dx = proc.center_4_ROI(w)
    print(f"Dx: {Dx}")
    
    for i, (x1, x2, y1, y2) in enumerate(roi_points):
        print(f"ROI {i}: x=[{x1}, {x2}], y=[{y1}, {y2}]")
        if x1 < 0 or x2 > w or y1 < 0 or y2 > h:
            print(f"  WARNING: ROI {i} is out of bounds!")
            
        ROI_image = image[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        if ROI_image.size == 0:
            print(f"  FAILED: ROI {i} image is empty!")
            continue
            
        rh, rw = ROI_image.shape[:2]
        # Mimic Find_Center_ROI color filtering
        b, g, r = cv2.split(ROI_image)
        r_safe = r.astype(float)
        r_safe[r_safe == 0] = 1.0 
        mask = (g / r_safe < 0.75) & (b / r_safe < 0.75)
        
        Rgray = np.zeros((rh, rw), dtype=np.uint8)
        Rgray[mask] = r[mask]
        
        # Binary threshold
        ret, binary = cv2.threshold(Rgray, 120, 255, cv2.THRESH_BINARY)
        num_pixels = cv2.countNonZero(binary)
        print(f"  ROI {i}: Binary pixels > 120: {num_pixels}")
        
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        print(f"  ROI {i}: Contours found: {len(contours)}")
        
        for cnt_idx, cnt in enumerate(contours):
            x, y, cw, ch = cv2.boundingRect(cnt)
            match_w = cw > proc.limit_w1
            match_h = (ch > proc.limit_H1 and ch < proc.limit_H2)
            print(f"    Contour {cnt_idx}: w={cw}, h={ch} | MatchW={match_w} (limit>{proc.limit_w1}), MatchH={match_h} ({proc.limit_H1}<h<{proc.limit_H2})")

    targets = proc.Find_Center_ROI(image, roi_points)
    print(f"--- Stage 1: Target Finding ---")
    print(f"Found {len(targets)} targets")
    
    if not targets:
        print("FAILED: No targets found in Stage 1")
        return

    target = targets[0]
    PX, PY = target['x'], target['y']
    print(f"Selected target: x={PX}, y={PY}")
    
    delt_x, dshift = 20, 7
    image_slide_roi = image[:, max(0, PX-delt_x):min(w, PX+delt_x)]
    Wx = delt_x - dshift
    
    def get_slides(roi, wx):
        h_roi, w_roi = roi.shape[:2]
        ave_L = np.zeros((h_roi, 3), dtype=np.float64)
        ave_R = np.zeros((h_roi, 3), dtype=np.float64)
        for j in range(h_roi):
            # Sum using slicing for speed
            row_l = roi[j, :wx]
            row_r = roi[j, -wx:]
            ave_L[j] = np.mean(row_l, axis=0)
            ave_R[j] = np.mean(row_r, axis=0)
        return ave_L, ave_R

    ave_L, ave_R = get_slides(image_slide_roi, Wx)
    print(f"Ave slides computed. Height: {len(ave_L)}")
    
    def find_red_indices_diag(ave_col, name):
        indices = []
        thd = 120
        count_r_zero = 0
        count_color_fail = 0
        count_thd_fail = 0
        count_y_fail = 0
        
        for j in range(len(ave_col)):
            b, g, r = ave_col[j]
            if r == 0: 
                count_r_zero += 1
                continue
            if not ((g/r < 0.75) and (b/r < 0.70)):
                count_color_fail += 1
                continue
            if r <= thd:
                count_thd_fail += 1
                continue
            if not (400 < j < 2650):
                count_y_fail += 1
                continue
            indices.append(j)
            
        print(f"  {name}: Found {len(indices)} red pixels. Failures: R=0:{count_r_zero}, Color:{count_color_fail}, Thd:{count_thd_fail}, Y-range:{count_y_fail}")
        return indices

    L_R_list = find_red_indices_diag(ave_L, "Left Slide")
    R_R_list = find_red_indices_diag(ave_R, "Right Slide")
    
    if not L_R_list or not R_R_list:
        print("FAILED: No red pixels found in one or both slides in Stage 2")
        return

    print("--- Stage 2: Red Indices Found ---")
    
    def get_pyh_diag(rgb_list, name, hlimit=750):
        py, h = [], []
        list0 = []
        for i in range(len(rgb_list)-1):
            if rgb_list[i+1] - rgb_list[i] == 1:
                list0.append(rgb_list[i])
        if not list0: 
            print(f"  {name}: No contiguous blocks found")
            return [rgb_list[0]], [0]
        
        py.append(list0[0])
        nums = []
        for i in range(len(rgb_list)-1):
            if rgb_list[i+1] - rgb_list[i] > hlimit:
                nums.append(i+1)
                py.append(rgb_list[i+1])
        
        total = len(rgb_list)
        if not nums:
            h = [total]
        else:
            nums.append(total)
            h.append(nums[0])
            for i in range(1, len(nums)):
                h.append(nums[i] - nums[i-1])
        print(f"  {name}: Py points found: {py}")
        return py, h

    L_R_Py, L_R_H = get_pyh_diag(L_R_list, "Left Py")
    R_R_Py, R_R_H = get_pyh_diag(R_R_list, "Right Py")
    
    num_targets = min(len(L_R_Py), len(R_R_Py), 3)
    print(f"FINAL: Can identify {num_targets} targets at this intersection.")

if __name__ == "__main__":
    test_path = r"d:\((Python TOOL\4cam分析照片\4cam_stripe_checker_v2\GOOD\4cam_cam01_dre_on.jpg"
    diagnose(test_path)
