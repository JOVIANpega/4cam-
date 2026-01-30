# 4CAM Stripe Checker V2 🚀

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-1.6.2-green.svg)](#)

這是一個專為 4-Camera 定位與拼接檢查開發的動態視覺分析系統。透過自動化的條紋掃描與像素位移分析，快速判定影像拼接的精準度。

![UI Preview](https://via.placeholder.com/800x450?text=Splicing+Check+System+UI+v1.6.2) 
*(使用內建功能產生的分析概覽圖)*

## ✨ 核心特色 (Unique Features)

- **玻璃感透明介面 (Glassmorphism Overlays)**: 分析結果日誌與數據採用 60%~70% 高透明度背景，在檢閱數據時完全不遮擋影像底層細節。
- **動態追蹤導引 (Active FOCUS Tracking)**: 在掃描過程中，系統會自動生成「橘色大箭頭」即時點向目前正在量測的條紋目標，視覺引導極其明確。
- **高效批次巡檢 (Batch Navigation Grid)**: 採用 8 欄位網格設計，可快速切換、預覽數十張甚至上百張的照片分析結果（PASS/FAIL 一目了然）。
- **智能濾波定位 (Smart ROI Locking)**: 採用 Find_Center_ROI 邏輯，結合 RGB 色彩過濾自動鎖定紅色標記點，確保在各種光源環境下都能精準抓取條紋。
- **高畫質目標快照 (Target Snapshots)**: 底部即時顯示各目標點的放大快照，並標註位移像素與判定結果，支援滑鼠懸停放大鏡功能。
- **版本控制與參數持久化**: 設定分頁可即時調整字體大小、分析閾值、放大鏡倍率，並自動儲存至 JSON 設定檔。

## 🛠️ 安裝與運行

### 環境需求
- Python 3.8+
- 必要庫: `ttkbootstrap`, `numpy`, `opencv-python`, `pillow`, `py7zr`

### 快速開始
1. 安裝依賴：
   ```bash
   pip install ttkbootstrap opencv-python pillow py7zr
   ```
2. 執行程序：
   ```bash
   python main.py
   ```

## 📋 版本更新日誌 (v1.6.2)

- **v1.6.2**: 強化資料夾載入偵錯邏輯，自動顯示非支援檔案範例，避免選錯目錄。
- **v1.6.1**: 增加 `.jpeg` 支援與深度診斷日誌（顯示檔案總數）。
- **v1.5.9**: 重新整合 FOCUS 橘色箭頭追蹤邏輯，優化批次全檢流程。
- **v1.5.8**: 實現 Alpha 60 極薄透明背景，優化掃描時的視覺清爽度。
- **v1.5.0**: 重構底部控制區，引入 8 欄位導航網格與浮水印結果。

---
*Developed with love by Antigravity AI Engine.*
