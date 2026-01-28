import cv2
import numpy as np
from scipy import signal
import os

class SplicingProcessor:
    def __init__(self):
        # Constants from 100cm.py
        self.x_30 = 88
        self.large_y = 30
        self.small_cam30 = 200
        self.ave_large = 310
        self.y_center_ave = 1440
        self.Pitch = [120, 110, 112]
        self.diff_thd = 10
        self.rate_thd = 0.1
        
        self.limit_w1 = self.small_cam30 - 20
        self.limit_H1 = self.large_y - 20
        self.limit_H2 = self.large_y + 40
        
        self.dx = int((self.ave_large + 100) / 2)
        self.up_dy = -50
        self.down_dy = 150
        
        self.roi_w = 30
        self.roi_ht = 8
        self.roi_hd = 20 # Restored to 20 as in 100cm.py line 443

    def ROI_position(self, center, dx, up_dy, down_dy):
        position_lx = max(0, center[0] - dx)
        position_rx = center[0] + dx
        position_uy = center[1] + up_dy
        position_dy = center[1] + down_dy
        return position_lx, position_rx, position_uy, position_dy

    def center_4_ROI(self, img_w):
        Dx = int(img_w / 4)
        roi_points = []
        for k in range(4):
            x_center = int(self.x_30 + Dx * k)
            y_center = int(self.y_center_ave)
            center = [x_center, y_center]
            pos = self.ROI_position(center, self.dx, self.up_dy, self.down_dy)
            roi_points.append(pos)
        return roi_points, Dx

    def Find_Center_ROI(self, image, roi_points):
        thd = 120
        found_targets = []
        h_img, w_img = image.shape[:2]
        
        for i in range(4):
            x1, x2, y1, y2 = roi_points[i]
            x1, x2 = max(0, int(x1)), min(w_img, int(x2))
            y1, y2 = max(0, int(y1)), min(h_img, int(y2))
            
            ROI_image = image[y1:y2, x1:x2]
            if ROI_image.size == 0: continue
            
            h, w = ROI_image.shape[:2]
            ROI_image_Rgray = np.zeros((h, w), dtype=np.uint8)
            
            # Red filtering logic (VEC)
            b, g, r = cv2.split(ROI_image)
            r_safe = r.astype(float)
            r_safe[r_safe == 0] = 1.0 
            # Correct logic from original script: rate_gr < 0.75 and rate_br < 0.75
            mask = (g / r_safe < 0.75) & (b / r_safe < 0.75)
            ROI_image_Rgray[mask] = r[mask]

            # BLACK line just like in original script
            BLACK_line = np.zeros((h, 3), dtype=np.uint8)
            ROI_image_Rgray = np.hstack((BLACK_line, ROI_image_Rgray))
            
            ret, binary = cv2.threshold(ROI_image_Rgray, thd, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            
            for cnt in contours:
                x, y, cw, ch = cv2.boundingRect(cnt)
                if cw > self.limit_w1 and ch > self.limit_H1 and ch < self.limit_H2:
                    pos_x = (x - 3) + x1 + int(cw/2)
                    if pos_x <= 1050:
                        found_targets.append({'x': self.x_30, 'y': y + y1, 'h': ch})
                    elif pos_x <= 3050:
                        found_targets.append({'x': self.x_30 + 1920, 'y': y + y1, 'h': ch})
                    elif pos_x <= 5050:
                        found_targets.append({'x': self.x_30 + 1920*2, 'y': y + y1, 'h': ch})
                    elif pos_x <= 7050:
                        found_targets.append({'x': self.x_30 + 1920*3, 'y': y + y1, 'h': ch})
                    break 
        return found_targets

    def Pixel_Shift_analysis(self, ROI_gray, diff_thd, center_line):
        h, w = ROI_gray.shape[:2]
        CL = int(center_line)
        # Use exact slice as 100cm.py
        Y_L = [np.mean(ROI_gray[i, (CL-6):(CL-1)]) for i in range(h)]
        Y_R = [np.mean(ROI_gray[i, (CL+1):(CL+6)]) for i in range(h)]
        
        Y_L_diff = np.array([(Y_L[i+1] - Y_L[i]) for i in range(h-1)])
        Y_R_diff = np.array([(Y_R[i+1] - Y_R[i]) for i in range(h-1)])
        
        for i in range(len(Y_L_diff)):
            if Y_L_diff[i] >= -diff_thd: Y_L_diff[i] = 0
        for i in range(len(Y_R_diff)):
            if Y_R_diff[i] >= -diff_thd: Y_R_diff[i] = 0
        
        valleys_L, _ = signal.find_peaks(-Y_L_diff, 1.0)
        valleys_R, _ = signal.find_peaks(-Y_R_diff, 1.0)
        
        def peak_valleys_zero(value):
            if len(value) == 0: return np.array([0])
            return value

        L_pixelsShift = [0]
        R_pixelsShift = [0]
        
        nl = len(valleys_L)
        if nl > 1:
            Y_L_diff_list = [Y_L_diff[v] for v in valleys_L]
            Y_L_list = sorted(Y_L_diff_list)
            rate_l = abs((Y_L_list[0] - Y_L_list[1]) / Y_L_list[0])
            if rate_l < self.rate_thd:
                L_pixelsShift.append(abs(int(valleys_L[0]) - int(valleys_L[1])))
            else:
                minl = np.argmin(Y_L_diff_list)
                valleys_L = np.array([valleys_L[minl]])
        
        nr = len(valleys_R)
        if nr > 1:
            Y_R_diff_list = [Y_R_diff[v] for v in valleys_R]
            Y_R_list = sorted(Y_R_diff_list)
            rate_r = abs((Y_R_list[0] - Y_R_list[1]) / Y_R_list[0])
            if rate_r < self.rate_thd:
                R_pixelsShift.append(abs(int(valleys_R[0]) - int(valleys_R[1])))
            else:
                minr = np.argmin(Y_R_diff_list)
                valleys_R = np.array([valleys_R[minr]])

        final_ps = max(max(L_pixelsShift), max(R_pixelsShift))
        return peak_valleys_zero(valleys_L), peak_valleys_zero(valleys_R), final_ps

    def analyze_image_prepare(self, filename):
        try:
            data = np.fromfile(filename, dtype=np.uint8)
            image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            image = None
            
        if image is None: return None
        
        h, w = image.shape[:2]
        roi_points, Dx = self.center_4_ROI(w)
        targets = self.Find_Center_ROI(image, roi_points)
        
        if not targets:
            # Replicate 100cm.py Line 467: ROI_SELECTOR_ERROR
            # Create a dummy image and targets to allow the pipeline to report 100px
            dummy_PX = self.x_30
            final_steps = []
            for i in range(3):
                final_steps.append({
                    'rect': (int(dummy_PX-self.roi_w), int(self.y_center_ave - 400 + i*400), int(dummy_PX+self.roi_w), int(self.y_center_ave - 400 + i*400 + 30)),
                    'index': i,
                    'force_fail': 100.0,
                    'msg': "ROI ERROR"
                })
            return image, final_steps
            
        target = targets[0]
        PX, PY = target['x'], target['y']
        
        delt_x, dshift = 20, 7
        image_slide_roi = image[:, max(0, PX-delt_x):min(w, PX+delt_x)]
        Wx = delt_x - dshift
        
        # Slower but exact slide logic from original script
        def get_slides(roi, wx):
            h_roi, w_roi = roi.shape[:2]
            ave_L = np.zeros((h_roi, 3), dtype=np.float64)
            ave_R = np.zeros((h_roi, 3), dtype=np.float64)
            for j in range(h_roi):
                row_l = roi[j, :wx]
                row_r = roi[j, -wx:]
                ave_L[j] = np.mean(row_l, axis=0) # [b, g, r]
                ave_R[j] = np.mean(row_r, axis=0)
            return ave_L, ave_R

        ave_L, ave_R = get_slides(image_slide_roi, Wx)
        
        def find_red_indices(ave_col, ref_col=None):
            indices = []
            thd = 120
            # Replicate 100cm.py bug: if ref_col is provided, use its color ratio for filtering
            # Line 190 & 194 in 100cm.py both use rate_gr_R and rate_br_R
            for j in range(len(ave_col)):
                b, g, r = ave_col[j]
                rb, rg, rr = ref_col[j] if ref_col is not None else (b, g, r)
                
                if rr <= 0: continue
                # Exact logic from original script: rate_gr_R < 0.75 and rate_br_R < 0.70
                if (rg/rr < 0.75) and (rb/rr < 0.70):
                    if r > thd and 400 < j < 2650:
                        indices.append(j)
            return indices

        L_R_list = find_red_indices(ave_L, ave_R) # Replicate bug: use ave_R for filtering L
        R_R_list = find_red_indices(ave_R, ave_R)
        
        if not L_R_list or not R_R_list: 
            return None
        
        def get_pyh(rgb_list, hlimit=750):
            if not rgb_list: return [], []
            py, h = [], []
            list0 = []
            for i in range(len(rgb_list)-1):
                if rgb_list[i+1] - rgb_list[i] == 1:
                    list0.append(rgb_list[i])
            if not list0: return [rgb_list[0]], [0]
            
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
            return py, h

        L_R_Py, L_R_H = get_pyh(L_R_list)
        R_R_Py, R_R_H = get_pyh(R_R_list)
        
        # Handle case where L_R_Py or R_R_Py is too short
        num_targets = min(len(L_R_Py), len(R_R_Py), 3) 
        
        # If still no targets found in Stage 2, fallback to ROI ERROR dummy steps
        if num_targets == 0:
            final_steps = []
            for i in range(3):
                final_steps.append({
                    'rect': (int(PX-self.roi_w), int(self.y_center_ave - 400 + i*400), int(PX+self.roi_w), int(self.y_center_ave - 400 + i*400 + 30)),
                    'index': i,
                    'force_fail': 100.0,
                    'msg': "ROI ERROR"
                })
            return image, final_steps

        final_steps = []
        for i in range(num_targets):
            alignment_offset = abs(L_R_Py[i] - R_R_Py[i])
            calibration = 1 if (R_R_Py[i] - L_R_Py[i]) > 1.0 else 0
            
            if L_R_Py[i] < R_R_Py[i]:
                std_py = L_R_Py[i] - L_R_H[i]
            else:
                std_py = R_R_Py[i] - R_R_H[i]
            
            final_steps.append({
                'rect': (int(PX-self.roi_w), int(std_py-self.roi_ht), int(PX+self.roi_w), int(std_py+self.roi_hd)),
                'px': PX,
                'py': std_py,
                'index': i,
                'alignment_offset': alignment_offset,
                'calibration': calibration
            })
            
        return image, final_steps

    def find_top10(self, arr):
        if len(arr) == 0: return np.zeros(10)
        # Use simple sort to avoid argsort complexity for small arrays
        return np.sort(arr)[-10:][::-1]

    def analyze_discontinuity(self, image, delta_h):
        try:
            h_orig, w_orig = image.shape[:2]
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            # 100cm.py Line 210
            gray_crop = gray[5:, :]
            
            dy_u, dy_d = 15, 3
            Tdelt_h = 4 * delta_h
            # ROI_imagecolor=image[dy_u:Tdelt_h-dy_d,:] 
            roi_color = image[dy_u:max(dy_u+1, Tdelt_h-dy_d), :]
            h_color, w_color = roi_color.shape[:2]
            
            Wx, dx_gap = int(w_color/2), 5
            
            def get_means(img_slice, channel):
                res = []
                for i in range(img_slice.shape[0]):
                    res.append(np.mean(img_slice[i, :, channel]))
                return np.array(res)

            # Left/Right slices
            slice_L = roi_color[:, :max(1, Wx-dx_gap)]
            slice_R = roi_color[:, min(w_color-1, Wx+dx_gap):]
            
            # B=0, G=1, R=2
            cB_L = get_means(slice_L, 0)
            cB_R = get_means(slice_R, 0)
            cG_L = get_means(slice_L, 1)
            cG_R = get_means(slice_R, 1)
            cR_L = get_means(slice_L, 2)
            cR_R = get_means(slice_R, 2)
            
            # Gray averages (Line 238)
            slice_gray_L = gray_crop[:, :max(1, Wx-dx_gap)]
            slice_gray_R = gray_crop[:, min(w_color-1, Wx+dx_gap):]
            white_L_list = []
            white_R_list = []
            for i in range(slice_gray_L.shape[0]):
                white_L_list.append(np.mean(slice_gray_L[i, :]))
                white_R_list.append(np.mean(slice_gray_R[i, :]))
            
            # Filtering (Line 230)
            cB_L = cB_L[cB_L <= 128]
            cB_R = cB_R[cB_R <= 128]
            
            def safe_mean_top10(arr):
                if len(arr) == 0: return 0.0
                return np.mean(self.find_top10(arr))

            blue_l_val, blue_r_val = safe_mean_top10(cB_L), safe_mean_top10(cB_R)
            green_l_val, green_r_val = safe_mean_top10(cG_L), safe_mean_top10(cG_R)
            red_l_val, red_r_val = safe_mean_top10(cR_L), safe_mean_top10(cR_R)
            white_l_val, white_r_val = safe_mean_top10(np.array(white_L_list)), safe_mean_top10(np.array(white_R_list))
            
            def calc_disc(l, r):
                denom = (l + r) / 2
                if denom == 0: return 0.0
                return abs(l - r) / denom

            white_disc = calc_disc(white_l_val, white_r_val)
            red_disc = calc_disc(red_l_val, red_r_val)
            green_disc = calc_disc(green_l_val, green_r_val)
            blue_disc = calc_disc(blue_l_val, blue_r_val)
            
            return white_disc, red_disc, green_disc, blue_disc
        except Exception:
            return 1.0, 1.0, 1.0, 1.0

    def process_step(self, image, step_info):
        force_fail = step_info.get('force_fail')
        if force_fail is not None:
            # 100cm.py Line 471-474: All discontinue = 100%
            return int(force_fail), np.zeros((100, 280, 3), dtype=np.uint8), (1.0, 1.0, 1.0, 1.0)

        x1, y1, x2, y2 = step_info['rect']
        h_img, w_img = image.shape[:2]
        ROI_img = image[max(0, y1):min(h_img, y2), max(0, x1):min(w_img, x2)]
        
        # Discontinuity Analysis (Stage 4)
        # Needs a specific ROI starting from py to py + delta*5
        std_py = int(step_info['py'])
        std_px = int(step_info['px'])
        delta_h = int(step_info.get('delta', 26))
        
        color_roi_y2 = min(h_img, std_py + delta_h * 5)
        roi_color_img = image[std_py:color_roi_y2, max(0, std_px-30):min(w_img, std_px+30)]
        white_d, red_d, green_d, blue_d = self.analyze_discontinuity(roi_color_img, delta_h)

        if ROI_img.size == 0: 
            return 0, np.zeros((100, 280, 3), dtype=np.uint8), (white_d, red_d, green_d, blue_d)
        
        gray = cv2.cvtColor(ROI_img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        
        centers = [int(w/2 - w/6*2), int(w/2 - w/6), int(w/2), int(w/2 + w/6), int(w/2 + w/6*2)]
        
        all_vL, all_vR, line_diffs = [], [], []
        for cl in centers:
            vL, vR, ps = self.Pixel_Shift_analysis(gray, self.diff_thd, cl)
            mvL, mvR = max(vL), max(vR)
            all_vL.append(mvL)
            all_vR.append(mvR)
            line_diffs.append(max(abs(mvL - mvR), ps))
            
        final_ps = max(line_diffs)
        max_vL, max_vR = max(all_vL), max(all_vR)
        
        if final_ps >= 15: final_ps = 15
        
        if step_info.get('alignment_offset', 0) >= 15:
            final_ps = max(final_ps, step_info['alignment_offset'])

        if step_info.get('calibration', 0) == 1:
            final_ps = abs(final_ps - 1)
        else:
            final_ps = abs(final_ps)
        
        debug_viz = ROI_img.copy()
        if max_vL > 0:
            cv2.line(debug_viz, (0, int(max_vL)), (int(w/2), int(max_vL)), (0, 255, 0), 1)
        if max_vR > 0:
            cv2.line(debug_viz, (int(w/2), int(max_vR)), (w, int(max_vR)), (0, 0, 255), 1)
            
        return int(final_ps), debug_viz, (white_d, red_d, green_d, blue_d)
