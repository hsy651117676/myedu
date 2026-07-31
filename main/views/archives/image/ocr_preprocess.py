"""
OCR 图像预处理：纠偏 + V通道OTSU二值化（自然去公章）
"""

import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


def deskew(image, max_angle=30):
    """
    检测文字倾斜角度并旋转矫正
    返回：矫正后的图像
    """
    if image is None:
        return image

    h, w = image.shape[:2]

    # 转灰度
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # 二值化（OTSU 自动阈值）
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 找所有非零点坐标
    coords = np.column_stack(np.where(binary > 0))

    if len(coords) < 100:
        return image

    # 最小外接矩形求角度
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]

    if angle < -45:
        angle = 90 + angle

    if abs(angle) < 0.5:
        return image

    if abs(angle) > max_angle:
        logger.debug(f"倾斜角度 {angle:.1f}° 超出阈值 {max_angle}°，跳过纠偏")
        return image

    logger.debug(f"检测到倾斜 {angle:.1f}°，执行纠偏")

    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)

    matrix[0, 2] += new_w / 2 - center[0]
    matrix[1, 2] += new_h / 2 - center[1]

    rotated = cv2.warpAffine(
        image,
        matrix,
        (new_w, new_h),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )

    return rotated


def preprocess(image_path):
    """
    预处理入口：读取图片 → 纠偏 → V通道+OTSU二值化 → 返回 numpy array
    V通道自然削弱红色公章，OTSU 分离黑白，一步去章
    """
    image = cv2.imread(image_path)
    if image is None:
        logger.error(f"无法读取图像: {image_path}")
        return None

    logger.debug(f"开始预处理: {image_path}")

    # 1. 纠偏
    image = deskew(image)

    # 2. HSV V通道 + OTSU 二值化
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    _, _, v = cv2.split(hsv)
    _, binary = cv2.threshold(v, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    logger.debug(f"预处理完成: {image_path}")
    return binary
