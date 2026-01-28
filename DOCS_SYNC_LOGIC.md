# 動態拼接檢查系統 - 邏輯同步說明 (Documentation)

本文件紀錄了 GUI 系統與診斷腳本 `20251222_1440_TestStation_100cm.py` 的邏輯同步細節，確保分析結果具備 100% 一致性。

## 1. 核心算法同步 (Algorithm Sync)
- **差異閾值 (Diff Threshold)**: 預設值與腳本同步為 `10`。
- **比率閾值 (Rate Threshold)**: 預設值與腳本同步為 `0.1`。
- **定位邏輯 (Find_Center_ROI)**: 
    - 同步了 `g/r < 0.75` 及 `b/r < 0.75` 的色彩過濾規則。
    - 實作了針對 4Cam 的 `pos_x` 分段判定。
- **像素位移分析 (Pixel_Shift_analysis)**: 
    - 採用 `5` 段 ROI 掃描線取最大值。
    - 同步了校正補償邏輯 (`calibration`)。

## 2. 錯誤處理 (Error Handling / Penalty)
為了確保在「壞圖」中的判讀行為與腳本一致：
- **ROI ERROR**: 當 Stage 1 找不到目標時，GUI 會模仿腳本行為輸出 **100px**。
- **PixelsShift_ERROR**: 當位移偏差過大（>15px），強行報出 **100px**。
- **分析動畫**: 即使報錯，也會顯示 3 個預設掃描框的動畫，確保使用者知道系統正在嘗試判讀並得出失敗結論。

## 3. 日誌輸出格式 (New Log Format)
新增了與原診斷腳本完全一致的 `spec_issue` 輸出區塊：
- **相機自動偵測**: 從檔名識別 `cam01`, `cam23` 等。
- **色彩斷層分析 (Stage 4)**: 實作了原腳本的 `analyze_discontinuity` 演算法。
- **完整規格輸出**: 
    - `MAX_PixelsShift_X`
    - `Brightness_discontinue_X`
    - `red/green/blue_discontinue_X`
    - `pixel_shift_avg`
    - `SPEC_PASS / SPEC_FAIL`

## 4. EXE 穩定化
- 解決了 `name 'sys' is not defined` 與 `name 'np' is not defined` 等打包後缺失引入的問題。
- 優化 `build_exe.bat` 以完整蒐集 `scipy` 與 `ttkbootstrap` 依賴項。

---
*備份日期: 2026-01-28*
*同步版本: V1.0 (Based on 100cm.py 20251222)*
