#!/usr/bin/env python
"""V 通道方案微调"""

import cv2
import numpy as np
import os

IMAGE_PATH = "/mnt/work/AutoScan_04/S26C-726073013520_0005.jpg"
OUT_DIR = "/mnt/raid10/print"

img = cv2.imread(IMAGE_PATH)
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
h, s, v = cv2.split(hsv)

# 11：纯 V 通道（已有）
cv2.imwrite(os.path.join(OUT_DIR, "11_HSV_V通道.jpg"), v)

# 13：V通道 + 自适应二值化（已有12，再调参数）
binary = cv2.adaptiveThreshold(
    v, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 8
)
cv2.imwrite(os.path.join(OUT_DIR, "13_V通道+二值化_block21.jpg"), binary)

# 14：V通道 + OTSU 二值化
_, otsu = cv2.threshold(v, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
cv2.imwrite(os.path.join(OUT_DIR, "14_V通道+OTSU.jpg"), otsu)

# 15：V通道 + CLAHE 增强
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
v_clahe = clahe.apply(v)
cv2.imwrite(os.path.join(OUT_DIR, "15_V通道+CLAHE.jpg"), v_clahe)

# 16：V通道 + CLAHE + OTSU
v_clahe_otsu = cv2.threshold(v_clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
cv2.imwrite(os.path.join(OUT_DIR, "16_V通道+CLAHE+OTSU.jpg"), v_clahe_otsu)

# 17：V通道 + 中值滤波降噪 + 二值化
v_denoised = cv2.medianBlur(v, 3)
v_denoised_binary = cv2.adaptiveThreshold(
    v_denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 8
)
cv2.imwrite(os.path.join(OUT_DIR, "17_V通道+降噪+二值化.jpg"), v_denoised_binary)

# 18：HSV S通道（饱和度，公章通常高饱和）
cv2.imwrite(os.path.join(OUT_DIR, "18_S通道.jpg"), s)

# 19：S通道 + 二值化
s_binary = cv2.adaptiveThreshold(
    s, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 8
)
cv2.imwrite(os.path.join(OUT_DIR, "19_S通道+二值化.jpg"), s_binary)

print("13-19 已输出到 /mnt/raid10/print/")
