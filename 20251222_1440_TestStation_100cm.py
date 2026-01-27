import sys
import cv2
import matplotlib.pyplot as plt # type: ignore
import numpy as np
import csv
from scipy import signal
import os

def show(name):
    name=name[:,:,::-1]
    # plt.imshow(name)
    # plt.show()

def show_g(name):
    name=name[:,:]
    # plt.imshow(name)
    # plt.show()
    
def findfile(root,type1,type2,type3):
    extensions=[type1,type2,type3]
    file_list = []
    counter=1
    for root, dirs, files in os.walk(root):
        for file in files:
            if any(file.lower().endswith(ext) for ext in extensions):
                file_list.append(root+file)
                counter +=1  
    return file_list

def ROI_position(center,dx,up_dy,down_dy):
    position_lx=center[0]-dx
    if position_lx < 0:
        position_lx=0
        position_rx=center[0]+dx
        position_uy=center[1]+up_dy
        position_dy=center[1]+down_dy
    else:
        position_lx=center[0]-dx
        position_rx=center[0]+dx
        position_uy=center[1]+up_dy
        position_dy=center[1]+down_dy
    return position_lx,position_rx,position_uy,position_dy

def ROI_area(y_center,y_down,y_top):
    dy_top=[]
    dy_down=[]
    for i in range(4):
        dynum_top=y_center[i]-y_top[i]
        dynum_dowm=y_down[i]-y_center[i]
        dy_top.append(dynum_top)
        dy_down.append(dynum_dowm)
    delta_y_top=int(np.mean(dy_top))
    delta_y_down=int(np.mean(dy_down))
    y_center_ave=int(np.mean(y_center))
    return y_center_ave,delta_y_down,delta_y_top

def ROI_area90(y_center,y_down,y_top,y_top90):
    dy_top=[]
    dy_top90=[]
    dy_down=[]
    for i in range(4):
        dynum_top90=y_center[i]-y_top90[i]
        dynum_top=y_center[i]-y_top[i]
        dynum_dowm=y_down[i]-y_center[i]
        dy_top90.append(dynum_top90)
        dy_top.append(dynum_top)
        dy_down.append(dynum_dowm)
    delta_y_top90=int(np.mean(dy_top90))
    delta_y_top=int(np.mean(dy_top))
    delta_y_down=int(np.mean(dy_down))
    y_center_ave=int(np.mean(y_center))
    return y_center_ave,delta_y_down,delta_y_top,delta_y_top90

def center_4_ROI(x_30,Dx,y_center_ave,dx,up_dy,down_dy):
    for k in range(4):
        x_center=int(x_30+Dx*k)
        y_center=int(y_center_ave)
        center=[x_center,y_center]
        center_point.append(center)
        position_lx,position_rx,position_uy,position_dy=ROI_position(center,dx,up_dy,down_dy)
        position=[position_lx,position_rx,position_uy,position_dy]
        ROIpoints.append(position)
    return    ROIpoints 

def Find_Center_ROI(image,ROIpoints,limit_w1,limit_w2,limit_H1,limit_H2):  
    # thd=140 
    thd=120 
    for i in range(4):
        ROI_image=image[ROIpoints[i][2]:ROIpoints[i][3],ROIpoints[i][0]:ROIpoints[i][1]]
        h,w=ROI_image.shape[:2]
        show(ROI_image)
        ROI_image_Rgray=np.zeros([h,w,1],dtype=np.uint8)
        for j in range(w):
            for k in range(h):
                R_b,R_g,R_r=(ROI_image[k,j])
                L_b,L_g,L_r=(ROI_image[k,j])
                rate_gr_R=R_g/R_r
                rate_br_R=R_b/R_r
                rate_gr_L=L_g/L_r
                rate_br_L=L_b/L_r
                if rate_gr_R < 0.75 and rate_gr_L < 0.75 and rate_br_R < 0.75 and rate_br_L < 0.75:  #######09/02改0.75 排除灰/黑/藍/綠
                    r = ROI_image.item(k,j,2)
                    ROI_image_Rgray.itemset((k,j,0),r)
        # show_g(ROI_image_Rgray)
        BLACK_line = np.full((h, 3, 1), 0, dtype=np.uint8)  ####### 在左邊添加R線
        ROI_image_Rgray= np.hstack((BLACK_line, ROI_image_Rgray))
        ROI_left_up_x=ROIpoints[i][0]
        ROI_left_up_y=ROIpoints[i][2]
        ret, ROI_image_Rgray=cv2.threshold(ROI_image_Rgray,thd,255,cv2.THRESH_BINARY)
        # show_g(ROI_image_Rgray)
        contours, hierarchy=cv2.findContours(ROI_image_Rgray,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(ROI_image_Rgray,contours,-1,255,3)
        x_30=88
        for i in contours:
            x,y,w,h=cv2.boundingRect(i)
            if w> limit_w1 and h > limit_H1  and h < limit_H2:
                cv2.rectangle(ROI_image_Rgray,(x,y),(x+w,y+h),255,3)
                position_x=x+ROI_left_up_x+int(w/2)
                show_g(ROI_image_Rgray)
                # print('position_x:',position_x)
                if position_x <= 1050 :
                    cv2.rectangle(ROI_image_Rgray,(x,y),(x+w,y+h),255,3)
                    point_x.append(x_30)
                    point_y.append(int(y+ROI_left_up_y))
                    roi_h.append(h)                 
                elif position_x <= 3050 :
                    cv2.rectangle(ROI_image_Rgray,(x,y),(x+w,y+h),255,3)
                    point_x.append(x_30+1920)
                    point_y.append(int(y+ROI_left_up_y))
                    roi_h.append(h)
                elif position_x <= 5050 :
                    cv2.rectangle(ROI_image_Rgray,(x,y),(x+w,y+h),255,3)
                    point_x.append(x_30+1920*2)
                    point_y.append(int(y+ROI_left_up_y))
                    roi_h.append(h) 
                elif position_x <= 7050 :
                    cv2.rectangle(ROI_image_Rgray,(x,y),(x+w,y+h),255,3)
                    point_x.append(x_30+1920*3)
                    point_y.append(int(y+ROI_left_up_y))
                    roi_h.append(h) 
            else:
                continue
    return point_x,point_y,roi_h

def slit_RGB(image_slide_roi,Wx,d_x):
    h,w=image_slide_roi.shape[:2]
    image_slide_L=np.zeros([h,d_x,3],dtype=np.uint8)
    image_slide_R=np.zeros([h,d_x,3],dtype=np.uint8)
    w_R=w-1
    for j in range(image_slide_L.shape[0]):
        r,g,b=0,0,0
        for i in range(Wx):
            r += image_slide_roi.item(j,i,2)
            g += image_slide_roi.item(j,i,1)
            b += image_slide_roi.item(j,i,0)
        ave_r=r/Wx
        ave_g=g/Wx
        ave_b=b/Wx
        for k in range(d_x):
            image_slide_L.itemset((j,k,0),ave_b)
            image_slide_L.itemset((j,k,1),ave_g)
            image_slide_L.itemset((j,k,2),ave_r)
    # cv2.imwrite('image_slide_L.bmp',image_slide_L)
    for j in range(image_slide_R.shape[0]):
        r,g,b=0,0,0
        for i in range(Wx):
            r += image_slide_roi.item(j,(w_R-i),2)
            g += image_slide_roi.item(j,(w_R-i),1)
            b += image_slide_roi.item(j,(w_R-i),0)
        ave_r=r/Wx
        ave_g=g/Wx
        ave_b=b/Wx
        for k in range(d_x):
            image_slide_R.itemset((j,k,0),ave_b)
            image_slide_R.itemset((j,k,1),ave_g)
            image_slide_R.itemset((j,k,2),ave_r)
    return image_slide_L,image_slide_R

def find_RGB_List(image_slide_L,image_slide_R):
    thd=120
    L_R_list,R_R_list=[],[]
    for j in range(image_slide_L.shape[0]): 
        R_b,R_g,R_r=(image_slide_R[j,0])
        L_b,L_g,L_r=(image_slide_L[j,0])
        rate_gr_R=R_g/R_r
        rate_br_R=R_b/R_r
        rate_gr_L=L_g/L_r
        rate_br_L=L_b/L_r
        # if rate_gr_R < 0.75 and rate_br_R < 0.75 :  #######排除灰/黑/藍/綠
        if rate_gr_R < 0.75 and rate_br_R < 0.70 :  #######排除灰/黑/藍/綠
            if R_r> thd and j > 400 and j <2650:
                R_R_list.append(j)
        # if rate_gr_L < 0.75 and rate_br_L < 0.75:  #######排除灰/黑/藍/綠
        if rate_gr_R < 0.75 and rate_br_R < 0.70 :  #######排除灰/黑/藍/綠
            if L_r> thd and j > 400 and j <2650 :
                L_R_list.append(j)  
    return L_R_list,R_R_list

def find_top10(arr):
    # print(arr)
    top_10_indices = np.argsort(arr)[-10:]  # 從小到大排序，取最後 10 個索引
    sorted_indices = top_10_indices[np.argsort(-arr[top_10_indices])]  
    top_10_values_sorted = arr[sorted_indices]
    # print(top_10_values_sorted)
    return top_10_values_sorted

def ROI_image_colorDiscontinue(image,delta_h):       ############delta=[28,26,24]
    # threshold = 255
    gray= cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)  
    gray=gray[5::,:]        ######20250305改
    h,w=image.shape[:2]
    show(image)
    show_g(gray)
    dy_u=15      ########裁切上方黑邊20250224改 由5==>15 
    dy_d=3       ########裁切下方白邊
    Tdelt_h=4*delta_h
    ROI_imagecolor=image[dy_u:Tdelt_h-dy_d,:] 
    show(ROI_imagecolor)
    Wx,dx=int(w/2), 5
    ColorDisB_L=[(np.mean(ROI_imagecolor[i,:(Wx-dx),0])) for i in range (Tdelt_h-dy_u-dy_d)]
    ColorDisB_R=[(np.mean(ROI_imagecolor[i,(Wx+dx):,0])) for i in range (Tdelt_h-dy_u-dy_d)]
    ColorDisG_L=[(np.mean(ROI_imagecolor[i,:(Wx-dx),1])) for i in range (Tdelt_h-dy_u-dy_d)]
    ColorDisG_R=[(np.mean(ROI_imagecolor[i,(Wx+dx):,1])) for i in range (Tdelt_h-dy_u-dy_d)]
    ColorDisR_L=[(np.mean(ROI_imagecolor[i,:(Wx-dx),2])) for i in range (Tdelt_h-dy_u-dy_d)]
    ColorDisR_R=[(np.mean(ROI_imagecolor[i,(Wx+dx):,2])) for i in range (Tdelt_h-dy_u-dy_d)]
    # ColorDisB_L = [x for x in ColorDisB_L if x <= 125]    ######20250224改    0311改改
    # ColorDisB_R = [x for x in ColorDisB_R if x <= 125]    ######20250224改    0311改
    # ColorDisB_L = [x for x in ColorDisB_L if x <= 140]    ######20250303改
    # ColorDisB_R = [x for x in ColorDisB_R if x <= 140]    ######20250303改
    ColorDisB_L = [x for x in ColorDisB_L if x <= 128]    ######20250311改
    ColorDisB_R = [x for x in ColorDisB_R if x <= 128]    ######20250311改
    ColorDisG_L = [x for x in ColorDisG_L if x <= 255]    ######20250224改
    ColorDisG_R = [x for x in ColorDisG_R if x <= 255]    ######20250224改
    ColorDisR_L = [x for x in ColorDisR_L if x <= 255]    ######20250224改
    ColorDisR_R = [x for x in ColorDisR_R if x <= 255]    ######20250224改
    # BrightnessDisR_L=[(np.mean(gray[i,:(Wx-dx)])) for i in range (h)]
    # BrightnessDisR_R=[(np.mean(gray[i,(Wx+dx):])) for i in range (h)]
    BrightnessDisR_L=[(np.mean(gray[i,:(Wx-dx)])) for i in range (h-5)]      ######20250305改
    BrightnessDisR_R=[(np.mean(gray[i,(Wx+dx):])) for i in range (h-5)]    ######20250305改
    # print('B:')
    Bluelist_L=find_top10(np.array(ColorDisB_L))
    Bluelist_R=find_top10(np.array(ColorDisB_R))
    # print('G:')
    Greenlist_L=find_top10(np.array(ColorDisG_L))
    Greenlist_R=find_top10(np.array(ColorDisG_R))
    # print('R:')
    Redlist_L=find_top10(np.array(ColorDisR_L))
    redlist_R=find_top10(np.array(ColorDisR_R))
    # print('W:')
    whitelist_L=find_top10(np.array(BrightnessDisR_L))
    whitelist_R=find_top10(np.array(BrightnessDisR_R))
    Blue_L=np.mean(Bluelist_L)
    Blue_R=np.mean(Bluelist_R)
    Green_L=np.mean(Greenlist_L)
    Green_R=np.mean(Greenlist_R)
    Red_L=np.mean(Redlist_L)
    red_R=np.mean(redlist_R)
    white_L=np.mean(whitelist_L)
    white_R=np.mean(whitelist_R)
    # print('Blue_L:',Bluelist_L)
    # print('Blue_R:',Bluelist_R)
    white_brightness=abs(white_L-white_R)/int((white_L+white_R)/2)
    red_brightness=abs(Red_L-red_R)/int((Red_L+red_R)/2)
    green_brightness=abs(Green_L-Green_R)/int((Green_L+Green_R)/2)
    blue_brightness=abs(Blue_L-Blue_R)/int((Blue_L+Blue_R)/2)
    return white_brightness,red_brightness,green_brightness,blue_brightness

def find_RGB_PyH(L_R_list,R_R_list,hlimit):
    # print(L_R_list)
    # print(R_R_list)
    L_R_Py,R_R_Py,L_R_H,R_R_H=[],[],[],[]
    num_l,num_r=[],[]
    L_R_list_0,R_R_list_0=[],[]
    TotalH=len(L_R_list)
    TotarH=len(R_R_list)
    for i in range(len(L_R_list)-2) :
        diff=L_R_list[i+1]-L_R_list[i]
        if diff==1 :
            L_R_list_0.append(L_R_list[i])
    for i in range(len(R_R_list)-2) :
        diff=R_R_list[i+1]-R_R_list[i]
        if diff==1 :         
            R_R_list_0.append(R_R_list[i]) 
    L_R_Py.append(L_R_list_0[0]) 
    R_R_Py.append(R_R_list_0[0])
    for i in range(len(L_R_list)-1) :    
        diff=L_R_list[i+1]-L_R_list[i]
        if diff > hlimit:
            num_l.append(int(i+1))
            L_R_Py.append(L_R_list[i+1])  
        else:
            continue
    for i in range(len(R_R_list)-1) :    
        diff=R_R_list[i+1]-R_R_list[i]
        if diff > hlimit:
            num_r.append(int(i+1))
            R_R_Py.append(R_R_list[i+1])  
        else:
            continue
    # print(L_R_Py)
    # print(R_R_Py)
    # print('Each R_area_0 _1 _2:',abs(L_R_Py[0]-R_R_Py[0]),abs(L_R_Py[1]-R_R_Py[1]),abs(L_R_Py[2]-R_R_Py[2]))
    area_0=abs(L_R_Py[0]-R_R_Py[0])
    area_1=abs(L_R_Py[1]-R_R_Py[1])
    area_2=abs(L_R_Py[2]-R_R_Py[2])
    # 寬度計算
    DH_l=num_l[-1]
    DH_r=num_r[-1]
    num_l.append(TotalH-DH_l)
    num_r.append(TotarH-DH_r)
    for i in range(len(num_l)):  
        if i ==0 or i== (len(num_l)-1):       
            L_R_H.append(num_l[i])
            R_R_H.append(num_r[i])
        else:
            L_R_H.append(num_l[i]-num_l[i-1])
            R_R_H.append(num_r[i]-num_l[i-1])
    return L_R_Py,R_R_Py,L_R_H,R_R_H,area_0,area_1,area_2

def PeakValleys_zero(value):
    if len(value) ==0:
        value=np.pad(value,(0,1),'constant',constant_values=(0)) 
    else:
        value=value
    return value

def Pixel_Shift_analysis(ROI_gray, diff_thd, center_line):
    CL=int(center_line)
    # print('CL,h,w:',CL,h,w)
    X_axis_diff=[i for i in range (h-1)]
    Y_L=[(np.mean(ROI_gray[i,(CL-6):(CL-1)])) for i in range (h)]
    Y_R=[(np.mean(ROI_gray[i,(CL+1):(CL+6)])) for i in range (h)]
    # print(Y_L)
    # print(Y_R)
    Y_L_diff=np.array([(Y_L[i+1]-Y_L[i]) for i in range (h-1)])
    Y_R_diff=np.array([(Y_R[i+1]-Y_R[i]) for i in range (h-1)])
    # print(Y_L_diff)
    # print(Y_R_diff)    
    for i in range(len(Y_L_diff)):
        if Y_L_diff[i] >= -diff_thd:
            Y_L_diff[i]=0
        else:
            Y_L_diff[i]=Y_L_diff[i]
    for i in range(len(Y_R_diff)):
        if Y_R_diff[i] >= -diff_thd:
            Y_R_diff[i]=0
        else:
            Y_R_diff[i]=Y_R_diff[i]
    valleys_L,_=signal.find_peaks(-Y_L_diff,1.0)
    valleys_R,_=signal.find_peaks(-Y_R_diff,1.0)
    # ########2025/06/11改由改由valleys的最大值決定pick位置
    nl=len(valleys_L)
    nr=len(valleys_R)
    L_pixelsShift=[]
    R_pixelsShift=[]
    L_pixelsShift.append(0)
    R_pixelsShift.append(0)

    if nl > 1:
        Y_L_diff_list=[]
        for i in range(nl):
            numl=valleys_L[i]
            Y_L_diff_list.append(Y_L_diff[numl])
        Y_L_list=sorted(Y_L_diff_list)
        Rate_L=abs((Y_L_list[0]-Y_L_list[1])/Y_L_list[0])
        # print('Rate_TWOPEAK_L:',Rate_L)
        if Rate_L < 0.1 :  #########20251222改
        # if Rate_L < 0.2 :
        # if Rate_L < 0.3 :    #########20251126 改
            L_PS=abs(int(valleys_L[0])-int(valleys_L[1]))
            L_pixelsShift.append(L_PS)
        else:
            minl=Y_L_diff_list.index(min(Y_L_diff_list))
            numl_valleys=valleys_L[minl]
            valleys_L=[]
            valleys_L.append(numl_valleys)
            L_pixelsShift.append(0)

    if nr > 1:
        Y_R_diff_list=[]
        for i in range(nr):
            numr=valleys_R[i]
            Y_R_diff_list.append(Y_R_diff[numr])
        Y_R_list=sorted(Y_R_diff_list)
        Rate_R=abs((Y_R_list[0]-Y_R_list[1])/Y_R_list[0])
        if Rate_R < 0.1 :  #########20251222改
        # if Rate_R < 0.2 :
        # if Rate_R < 0.3 :     #########20251126 改
            R_PS=abs(int(valleys_R[0])-int(valleys_R[1]))
            R_pixelsShift.append(R_PS)
        else:
            minr=Y_R_diff_list.index(min(Y_R_diff_list))
            numr_valleys=valleys_R[minr]
            valleys_R=[]
            valleys_R.append(numr_valleys)
            R_pixelsShift.append(0)

    # print('L_pixelsShift:',L_pixelsShift)
    # print('R_pixelsShift:',R_pixelsShift)
    L_pixelsShift=max(L_pixelsShift)
    R_pixelsShift=max(R_pixelsShift)
    pixelsShifT=max(L_pixelsShift,R_pixelsShift)
    # print('pixelsShifT:',pixelsShifT)

    # 以下 當peaks valleys 沒抓到數值時補上"0"值
    valleys_L=PeakValleys_zero(valleys_L)
    valleys_R=PeakValleys_zero(valleys_R)
    ############# # 開始作圖 檢查ok後可關閉
    # fig, ax = plt.subplots()
    # ax.plot(X_axis_diff, Y_L_diff ,'-' ,color='b',label="Y_L_diff")
    # ax.plot(X_axis_diff, Y_R_diff ,'-' ,color='yellow',label="Y_R_diff")
    # ax.legend(handlelength=4)
    # plt.grid(axis='both',color='b', linestyle=':' ,linewidth=0.1)
    # plt.show()
    # ##############  檢查ok後可關閉
    print('valleys_L,valleys_R:', valleys_L,valleys_R)
    return valleys_L,valleys_R,pixelsShifT

# 主程式開始
root=str(sys.argv[1])
# root=str('./20251222_we255100074/')        ######需修改
type1='.bmp'
type2='.png'
type3='.jpg'
file_list=findfile(root,type1,type2,type3)

##########      參數輸入     #########
##### 測試距離為100cm :
x_30=88
large_y=30               #######紅光帶寬
# small_cam30=245        ###aoci   243~251 AVE 247
small_cam30=200          ###tauyun 205
ave_large=310            ###aoci   306~316 AVE 310
y_center_ave=1440        ######## y_center=[1435,1441,1440,1443]
Pitch=[120,110,112]      ####### 輸入各區塊的帶寬
# thd=160                ####160~170 AVE 167  , 下限 135~143 AVE138
limit_w1_100,limit_w2_100= small_cam30- 20,small_cam30+ 40    #####桃園與AOCI一起改  +- 30 (>limit_w1_100開始ROI選擇框) (w < limit_w2,X30)
limit_H1_100,limit_H2_100= large_y-20,large_y+40              ########RGB區域的高度上下邊界 
dx, up_dy, down_dy=int((ave_large+100)/2),-50, 150            ###### 中央4區塊的ROI視窗位置與大小
# roi_ds,roi_w,roi_ht,roi_hd= 10,20,10,15                       #####RGB區域計算pixels_Shift時的計算寬度,中心往上距離,中心往下距離
# roi_ds,roi_w,roi_ht,roi_hd= 15,20,15,20                      #####20250528_RGB區域計算pixels_Shift時的計算寬度,中心往上距離,中心往下距離
# roi_ds,roi_w,roi_ht,roi_hd= 15,20,8,20                      #####20250611_應映valleys_peak調整roi_RGB區域計算pixels_Shift時的計算寬度,中心往上距離,中心往下距離
roi_w,roi_ht,roi_hd= 30,8,20                      #####20250901_改為30PS切分5段roi_ds另外計算,ROI寬度,中心往上距離,中心往下距離
roi_ds=5

# diff_thd=40    #####分析數據Pick數據時將noise 雜峰刪除
# diff_thd=20    #####分析數據Pick數據時將noise 雜峰刪除_02/21改 
# diff_thd=40    #####0528分析數據Pick數據時將noise 雜峰刪除_05/28改 
# diff_thd=50    #####TY3_0610分析桃園廠數據Pick數據時將noise 雜峰刪除_0610改 
# diff_thd=30    #####TY3_0610分析桃園廠數據Pick數據時將noise 雜峰刪除_0610改 
diff_thd=10    #####202512/22 分析AOCI AND TY3廠數據 (線上未調整)
# 開始計算每張圖片
for i in range(len(file_list)):
    print(len(file_list),i)
    filename=file_list[i]
    print(filename)
    image=cv2.imread(filename)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h,w=gray.shape[:2]
    point_x,point_y,roi_h,center_point,ROIpoints=[],[],[],[],[]
    Dx=int(w/4)
    print('1_stage: start to find the Center_ROI: (Threshold_Brightness)')
    ROIpoints=center_4_ROI(x_30,Dx,y_center_ave,dx,up_dy,down_dy)              ###### 中央4區塊的ROI視窗位置與大小
    point_x,point_y,roi_h=Find_Center_ROI(image,ROIpoints,limit_w1_100,limit_w2_100,limit_H1_100,limit_H2_100)   ###### 找出圖片是哪條拚接縫,與y位置
    # 若沒找到則顯示錯誤
    if point_y == [] or point_x == []:
        print("ROI_SELECTOR_ERROR:")
        for i in range(3):
            print(filename)
            print('MAX_PixelsShift_' + str(i) + '=' + str(1.0* 100.0) + 'pixels'+'MAX_PixelsShift_'+str(i) +'_END')
            print('Brightness_discontinue_' + str(i) + '=' + str(1.0* 100.0) + '%'+'Brightness_discontinue_'+str(i)+'_END')
            print('red_discontinue_' + str(i) + '=' + str(1.0 * 100.0) + '%'+'red_discontinue_' + str(i) +'_END')
            print('green_discontinue_' + str(i) + '=' + str(1.0 * 100.0) + '%'+'green_discontinue_' + str(i)+'_END')
            print('blue_discontinue_' + str(i) + '=' + str(1.0 * 100.0) + '%'+'blue_discontinue_' + str(i)+'_END')
        continue
    print('Center_ROI_done: (Threshold_Brightness ok )')
    PX,PY=int(point_x[0]),int(point_y[0])   ##########  找到正確的RGB區域座標(中央/上點)
    print('PX,PY:',PX,PY)

    ##########        開始尋找上下R/G/B的方框區間,利用紅色過濾找到R/G/B的方框區間        ##########################
    delt_x,dshift=20 , 7        #####  dshift 交界線的位移
    w_R=int(delt_x*2-1)
    image_slide_roi=image[:,PX-delt_x:PX+delt_x]
    # show(image_slide_roi)
    Wx=delt_x-dshift                      #####平均的帶寬
    d_x=Wx                                #####計算的條寬,可為1   
    hlimit= 750
    print('2_stage: start to Find 3/4 Color zone  slide_R: (R parameter is KEY)')    
    image_slide_L,image_slide_R=slit_RGB(image_slide_roi,Wx,d_x)
    L_R_list,R_R_list=find_RGB_List(image_slide_L,image_slide_R)
    L_R_Py,R_R_Py,L_R_H,R_R_H,area_0,area_1,area_2=find_RGB_PyH(L_R_list,R_R_list,hlimit)          #######L_R_Py 左邊R的位置,R_R_Py 右邊R的位置,L_R_H左邊R的寬度,R_R_H左邊R的寬度

    # print('L_R_Py左邊R的位置,R_R_Py右邊R的位置,L_R_H左邊R的寬度,R_R_H左邊R的寬度:',L_R_Py,R_R_Py,L_R_H,R_R_H)
    L_R_H[0] =26 if L_R_H[0] <26 else L_R_H[0]
    L_R_H[1] =26 if L_R_H[1] <26 else L_R_H[1]
    L_R_H[2] =25 if L_R_H[2] <25 else L_R_H[2]
    R_R_H[0] =26 if R_R_H[0] <26 else R_R_H[0]
    R_R_H[1] =26 if R_R_H[1] <26 else R_R_H[1]
    R_R_H[2] =25 if R_R_H[2] <25 else R_R_H[2]

    Pixels_shift, Point_STD_h,delta =[],[],[]
    n=len(L_R_Py)
    if L_R_Py[0] < R_R_Py[0]:
        for i in range(n):
            Point_STD_h.append(L_R_Py[i] -L_R_H[i])                ####### 距離100cm 輸入交接線Y像素,0度/+45度/-45度 圖形頂點
            delta.append(L_R_H[i])
    else:
        for i in range(n):
            Point_STD_h.append(R_R_Py[i] -R_R_H[i])
            delta.append(R_R_H[i])
    # print('L_R_H',L_R_H)
    # print('R_R_H',R_R_H)
    # print('Point_STD_h:',Point_STD_h)
    # print('delta:',delta)
    Point_STD_w=[PX]                                             ####### 輸入交接線X像素
    print('Color zone  slide_R is done: (R parameter is ok)')   
    ##########              開始分別檢測center,down.top,top90 等RGB區域的pixels_shift      ##########################
    print('3_stage: start to analysis pixels_shift : ')    
    Area_PointCenter,max_ps,ave_ps=[],[],[]
    white_brightness,red_brightness,green_brightness,blue_brightness =[],[],[],[]
    for i in range(len(Point_STD_h)):
        std_py,std_px,roi_down=Point_STD_h[i],Point_STD_w[0],Pitch[i]
        ROI_image_up=image[std_py-roi_ht:std_py+roi_hd,std_px-roi_w:std_px+roi_w]          #####區域上方尋找峰/谷值
        show(ROI_image_up)
        ROI_gray= cv2.cvtColor(ROI_image_up, cv2.COLOR_BGR2GRAY)
        h,w=ROI_gray.shape[:2]
        center_line_0=int(w/2-w/6*2)
        center_line_1=int(w/2-w/6)
        center_line_2=int(w/2)
        center_line_3=int(w/2+w/6)
        center_line_4=int(w/2+w/6*2)

        valleys_L_up_0,valleys_R_up_0,pixelsShifT_0=Pixel_Shift_analysis(ROI_gray, diff_thd, center_line_0)
        valleys_L_up_1,valleys_R_up_1,pixelsShifT_1=Pixel_Shift_analysis(ROI_gray, diff_thd, center_line_1)
        valleys_L_up_2,valleys_R_up_2,pixelsShifT_2=Pixel_Shift_analysis(ROI_gray, diff_thd, center_line_2)
        valleys_L_up_3,valleys_R_up_3,pixelsShifT_3=Pixel_Shift_analysis(ROI_gray, diff_thd, center_line_3)
        valleys_L_up_4,valleys_R_up_4,pixelsShifT_4=Pixel_Shift_analysis(ROI_gray, diff_thd, center_line_4)
        maxvalleys_L_0,maxvalleys_L_1,maxvalleys_L_2,maxvalleys_L_3,maxvalleys_L_4=max(valleys_L_up_0),max(valleys_L_up_1),max(valleys_L_up_2),max(valleys_L_up_3),max(valleys_L_up_4)
        maxvalleys_R_0,maxvalleys_R_1,maxvalleys_R_2,maxvalleys_R_3,maxvalleys_R_4=max(valleys_R_up_0),max(valleys_R_up_1),max(valleys_R_up_2),max(valleys_R_up_3),max(valleys_R_up_4)
        maxvalleys_0=abs(maxvalleys_L_0-maxvalleys_R_0)
        maxvalleys_1=abs(maxvalleys_L_1-maxvalleys_R_1)
        maxvalleys_2=abs(maxvalleys_L_2-maxvalleys_R_2)
        maxvalleys_3=abs(maxvalleys_L_3-maxvalleys_R_3)
        maxvalleys_4=abs(maxvalleys_L_4-maxvalleys_R_4)
        maxvalleys_0=max(maxvalleys_0,pixelsShifT_0)
        maxvalleys_1=max(maxvalleys_1,pixelsShifT_1)
        maxvalleys_2=max(maxvalleys_2,pixelsShifT_2)
        maxvalleys_3=max(maxvalleys_3,pixelsShifT_3)
        maxvalleys_4=max(maxvalleys_4,pixelsShifT_4)
        # print("valleys_L,valleys_R,valleys_R_0:",valleys_L_up_0,valleys_R_up_0,maxvalleys_0)
        # print("valleys_L,valleys_R,valleys_R_1:",valleys_L_up_1,valleys_R_up_1,maxvalleys_1)
        # print("valleys_L,valleys_R,valleys_R_2:",valleys_L_up_2,valleys_R_up_2,maxvalleys_2)
        # print("valleys_L,valleys_R,valleys_R_3:",valleys_L_up_3,valleys_R_up_3,maxvalleys_3)
        # print("valleys_L,valleys_R,valleys_R_4:",valleys_L_up_4,valleys_R_up_4,maxvalleys_4)
        maxvalleys_up=max(maxvalleys_0,maxvalleys_1,maxvalleys_2,maxvalleys_3,maxvalleys_4)
        print("pixels_shift_max:",maxvalleys_up)

        pixels_shift_max=maxvalleys_up
        # print('pixels_shift_max:',pixels_shift_max)
        if pixels_shift_max >= 15 :
            pixels_shift_max = 15
        elif pixels_shift_max >=-15:
            pixels_shift_max =pixels_shift_max
        else:
            pixels_shift_max = -15
        # print('MAX_PixelsShift_'+str(i)+'='+str(pixels_shift_max)+' pixelsMAX_PixelsShift_'+str(i)+'_END')
        ############      20250313改  補償因取點位置差異40PIXELS ,導致先天就有段差2pixels,因為有統計平均所以校正1pixels  ################
        if (R_R_Py[i] - L_R_Py[i]) > 1.0 :      
            pixels_shift_max= abs(pixels_shift_max- 1)
        else:
            pixels_shift_max= abs(pixels_shift_max)
        max_ps.append(pixels_shift_max)  
        print('MAX_PixelsShift_'+str(i)+'='+str(pixels_shift_max)+' pixelsMAX_PixelsShift_'+str(i)+'_END')

    ############           開始RGB_Color discontinue 計算        ##########
        delta[0] =27 if delta[0] <27 else delta[0]
        delta[1] =26 if delta[1] <26 else delta[1]
        delta[2] =26 if delta[2] <26 else delta[2]
        delta_h=int(delta[i])
    ############           開始RGB_Color discontinue 計算        ##########
        print('4_stage: start to analysis color_discontinue: ') 
        colorDis_x=30
        ROI_image_color=image[std_py:std_py+(delta_h*5),std_px-colorDis_x:std_px+colorDis_x]                 
        white,red,green,blue=ROI_image_colorDiscontinue(ROI_image_color,delta_h)
        # white_brightness.append(float(white))
        # red_brightness.append(red)
        # green_brightness.append(green)
        # blue_brightness.append(blue)
        print('analysis color_discontinue_done ')

    ############           開始RGB_Color discontinue 計算_ROI算法        ##########
        delta_h=int(delta[i])
        valleyshift_up=maxvalleys_up
        ######    取點的PIXELS SHIFT 位置校正
        if valleyshift_up > 0:
            DS_l=abs(pixels_shift_max)
            DS_R=0
        else:
            DS_l=0
            DS_R=abs(pixels_shift_max)
        black_py =std_py +int(delta_h/2)
        red_py   =std_py +int(delta_h*3/2)
        green_py =std_py +int(delta_h*5/2)
        blue_py  =std_py +int(delta_h*7/2)
        white_py =std_py +int(delta_h*9/2)
        Five_point_y=[black_py,red_py,green_py,blue_py,white_py]
        point_WL,point_WR= Point_STD_w[0]-10 , Point_STD_w[0]+10
        blue_px_L,green_px_L,red_px_L,black_px_L,white_px_L=point_WL,point_WL,point_WL,point_WL,point_WL
        blue_px_R,green_px_R,red_px_R,black_px_R,white_px_R=point_WR,point_WR,point_WR,point_WR,point_WR
        center=[[blue_py+DS_l,blue_px_L],[blue_py+DS_R,blue_px_R],[green_py+DS_l,green_px_L],[green_py+DS_R,green_px_R],[red_py+DS_l,red_px_L],[red_py+DS_R,red_px_R],
                [black_py+DS_l,black_px_L],[black_py+DS_R,black_px_R],[white_py+DS_l,white_px_L],[white_py+DS_R,white_px_R]]
        ######### 計算數值時需關閉畫出點
        # for i in range(len(center)):
        #     center_x=int(center[i][1])
        #     center_y=int(center[i][0])
        #     cv2.circle(image,(center_x,center_y),5,(0,0,255),-1)
        # cv2.imwrite(filename+'_check.bmp',image)
        # show(image)
        ##############################
        # print('center:',center)
        ave_list=[]
        ave_R,ave_G,ave_B=[],[],[]
        for i in range(len(center)):
            x=int(center[i][1])
            y=int(center[i][0])
            n,sum,sum_R,sum_G,sum_B,ave_r,ave_g,ave_b=0,0,0,0,0,0,0,0
            for j in range(x-5,x+5):
                for k in range(y-5,y+5):
                    n+=1
                    sum += gray[k,j]
                    sum_R += image[k,j,2]
                    sum_G += image[k,j,1]
                    sum_B += image[k,j,0]
                    # image[k,j]=0
            ave,ave_r,ave_g,ave_b=sum/n,sum_R/n,sum_G/n,sum_B/n
            ave_list.append(ave)
            ave_R.append(ave_r)
            ave_G.append(ave_g)
            ave_B.append(ave_b)
        # print(ave_list)
        white_roi=abs(ave_list[8]-ave_list[9])/int((ave_list[8]+ave_list[9])/2)         
        rl,rr=ave_R[4], ave_R[5]
        red_roi=abs((rl-rr)/int((rl+rr)/2))
        gl,gr=ave_G[2],ave_G[3]
        green_roi=abs((gl-gr)/int((gl+gr)/2))
        bl,br=ave_B[0],ave_B[1]
        blue_roi=abs((bl-br)/int((bl+br)/2))
        # print('white,red,green,blue:',white,red,green,blue)
        # print('white_roi,red,green,blue:',white_roi,red_roi,green_roi,blue_roi)
        if white_roi < white:
            white_roi=white_roi
        else:
            white_roi=white

        if red_roi < red:
            red_roi=red_roi
        else:
            red_roi=red

        if green_roi < green:
            green_roi=green_roi
        else:
            green_roi=green

        if blue_roi < blue:
            blue_roi=blue_roi
        else:
            blue_roi=blue            
        Area_PointCenter.append(center)
        white_brightness.append(white_roi)
        red_brightness.append(red_roi)
        green_brightness.append(green_roi)
        blue_brightness.append(blue_roi)
        # print('white,red,green,blue:',white,red,green,blue)
        # print('white_roi,red,green,blue:',white_roi,red_roi,green_roi,blue_roi)
        print('analysis color_discontinue_done ')
    
    ########################################### 增加超過15pixels 問題處理  ###########        
    print('Each R_area:',area_0,area_1,area_2)
    if area_0 >=15 or area_1 >=15 or area_2>=15:
        print("PixelsShift_ERROR:")
        max_ps=[area_0,area_1,area_2]
        # for i in range(3):
        #     print('MAX_PixelsShift_' + str(i) + '=' + str(1.0 * 100.0) + 'pixels' + 'MAX_PixelsShift_' + str(i) + '_END')
        #     print('Brightness_discontinue_' + str(i) + '=' + str(1.0 * 100.0) + '%' + 'Brightness_discontinue_' + str(i) + '_END')
        #     print('red_discontinue_' + str(i) + '=' + str(1.0 * 100.0) + '%' + 'red_discontinue_' + str(i) + '_END')
        #     print('green_discontinue_' + str(i) + '=' + str(1.0 * 100.0) + '%' + 'green_discontinue_' + str(i) + '_END')
        #     print('blue_discontinue_' + str(i) + '=' + str(1.0 * 100.0) + '%' + 'blue_discontinue_' + str(i) + '_END')
        # continue
    else:
        print('pixels_shift analysis OK  ') 
    ###############    儲存數值  For ATS     #############################################
    print('4_stage: start to Save data: ')    
    for i in range(3):
        print('Brightness_discontinue_' + str(i) + '=' + str(white_brightness[i] * 100.0) + '%'+'Brightness_discontinue_' + str(i)+'_END')
        print('red_discontinue_' + str(i) + '=' + str(red_brightness [i]* 100.0) + '%'+'red_discontinue_' + str(i)+'_END')
        print('green_discontinue_' + str(i) + '=' + str(green_brightness[i] * 100.0) + '%'+'green_discontinue_' + str(i)+'_END')
        print('blue_discontinue_' + str(i) + '=' + str(blue_brightness[i] * 100.0) + '%'+'blue_discontinue_' + str(i)+'_END')
    # # ###############    儲存數值  For max     #############################################
    # print('4_stage: start to Save data: ')    
    # outdata='./20251222_we255100074/we255100074.csv'          ######需修改   100cm的CSV 路徑
    # with open(outdata,'a',newline='',)as file:
    #     writefile=csv.writer(file)
    #     fileName=filename.split("/")[-2]
    #     parts = filename.replace("\\", "/").split("/")
    #     # parts = parts[-2].split("_")
    #     print(parts)
    #     # '1107240011', '20241223', '11', '34', '37', '1m', 'stitch', 'area', '12.bmp'
    #     # writefile.writerow([name,'pixels_shift_ave','white_gray_discontinue','red_discontinue',"green_discontinue",'blue_discontinue'])
    # with open(outdata,'a',newline='',)as file:
    #     writefile=csv.writer(file)
    #     for i in range(3):
    #         with open(outdata,'a',newline='',)as file:
    #             writefile=csv.writer(file)
    #             # writefile.writerow([str(parts[-1]),str(i),parts[1]+':'+parts[2]+':'+parts[3]+':'+parts[4],max_ps[i],white_brightness[i]*1,red_brightness[i]*1,green_brightness[i]*1,blue_brightness[i]*1])
    #             writefile.writerow([str(parts[-2]),str(i),parts[-1],max_ps[i],white_brightness[i]*1,red_brightness[i]*1,green_brightness[i]*1,blue_brightness[i]*1])

    #         print('Brightness_discontinue_' + str(i) + '=' + str(white_brightness[i] * 1.0) + '%'+'Brightness_discontinue_' + str(i)+'_END')
    #         print('red_discontinue_' + str(i) + '=' + str(red_brightness [i]* 1.0) + '%'+'red_discontinue_' + str(i)+'_END')
    #         print('green_discontinue_' + str(i) + '=' + str(green_brightness[i] * 1.0) + '%'+'green_discontinue_' + str(i)+'_END')
    #         print('blue_discontinue_' + str(i) + '=' + str(blue_brightness[i] * 1.0) + '%'+'blue_discontinue_' + str(i)+'_END')