"""
档案图像扫描服务层
- 业务SQL查询
- 图片解密
- PDF合成
"""

import os
import io
import glob
import logging
from reportlab.lib.pagesizes import A4, A5, A3, B5
from reportlab.pdfgen import canvas
from PIL import Image
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from django.conf import settings
from main.db_utils import query_dict
from reportlab.lib.utils import ImageReader

logger = logging.getLogger(__name__)


# ==================== 常量 ====================

PAGE_SIZE_MAP = {
    'A4': A4,
    'A5': A5,
    'A3': A3,
    'B5': B5,
}

IMAGE_TYPES = {
    'YS': '原始图像',
    'GQ': '高清图像',
}

_AES_KEY = b"3yj8jbvx" + b'\x00' * 8


# ==================== 业务SQL查询 ====================

def get_latest_uptime(rsid, archid, image_type='YS'):
    """
    获取指定档案材料的最新扫描时间
    取 MAX(uptime)，只要有一张图更新就算过期
    
    返回:
        (uptime: str 或 None, image_count: int)
        uptime 格式: '20250326163419'
    """
    table_name = f"RS_DESCRIPT_{rsid}"

    if image_type == 'YS':
        sql = f"""SELECT MAX(uptime) AS max_uptime, COUNT(*) AS img_count
                  FROM {table_name}
                  WHERE Archid='{archid}'"""
    else:
        sql = f"""SELECT MAX(uptime) AS max_uptime, COUNT(*) AS img_count
                  FROM {table_name}
                  WHERE Archid='{archid}' AND GaoQingLength IS NOT NULL"""

    result = query_dict(sql)
    if result and result[0]['max_uptime']:
        raw = str(result[0]['max_uptime'])
        uptime = raw.replace('-', '').replace(':', '').replace(' ', '')
        count = result[0]['img_count']
        return uptime, count
    return None, 0


# ==================== PDF辅助 ====================

def get_pdf_page_size(size_name, vertical=True):
    """获取PDF页面尺寸"""
    width, height = PAGE_SIZE_MAP.get(size_name.upper(), A4)
    if not vertical:
        width, height = height, width
    return width, height


# ==================== 图片解密 ====================

def decrypt_image(encrypted_path):
    """
    解密FTS加密的图片文件
    算法: AES-128-ECB, 密钥: "3yj8jbvx" + \x00*8
    头部: 8/12/16/20字节，自动检测
    """
    with open(encrypted_path, 'rb') as f:
        data = f.read()

    plain_bytes = None

    for head_size in [8, 12, 16, 20]:
        enc = data[head_size:]
        if len(enc) % 16 != 0:
            continue

        try:
            cipher = AES.new(_AES_KEY, AES.MODE_ECB)
            decrypted = cipher.decrypt(enc)

            try:
                plain = unpad(decrypted, 16)
            except ValueError:
                end = decrypted.find(b'\xff\xd9')
                if end > 0:
                    plain = decrypted[:end + 2]
                else:
                    continue

            if plain[:2] == b'\xff\xd8' or plain[:4] == b'\x89PNG':
                plain_bytes = plain
                break
        except Exception:
            continue

    if plain_bytes is None:
        raise ValueError(f"解密失败，无法识别文件格式: {encrypted_path}")

    return Image.open(io.BytesIO(plain_bytes))


# ==================== 路径构建 ====================

def build_image_dir(image_type, rsid, fl, archid):
    """
    构建图片源目录路径
    /mnt/data/das_image_file/{YS|GQ}/{rsid_zfill8}/{fl}/{archid}/
    """
    rsid_padded = str(rsid).zfill(8)
    return os.path.join(
        settings.SCAN_IMAGE_BASE_DIR,
        image_type,
        rsid_padded,
        str(fl),
        str(archid)
    )


def build_pdf_dir(image_type, rsid, fl, archid):
    """
    构建PDF存放目录路径
    /mnt/data/das_pdf/{YS|GQ}/{rsid_zfill8}/{fl}/{archid}/
    """
    rsid_padded = str(rsid).zfill(8)
    return os.path.join(
        settings.SCAN_PDF_OUTPUT_DIR,
        image_type,
        rsid_padded,
        str(fl),
        str(archid)
    )


def build_pdf_path(image_type, rsid, fl, archid, uptime):
    """
    构建PDF完整路径
    /mnt/data/das_pdf/{YS|GQ}/{rsid_zfill8}/{fl}/{archid}/{fl}_{uptime}.pdf
    """
    pdf_dir = build_pdf_dir(image_type, rsid, fl, archid)
    pdf_filename = f"{fl}_{uptime}.pdf"
    return os.path.join(pdf_dir, pdf_filename)


def find_existing_pdf(image_type, rsid, fl, archid):
    """
    查找该档案材料已有PDF（匹配 {fl}_*.pdf）
    返回: pdf_path 或 None
    """
    pdf_dir = build_pdf_dir(image_type, rsid, fl, archid)

    if not os.path.exists(pdf_dir):
        return None

    pattern = os.path.join(pdf_dir, f"{fl}_*.pdf")
    matches = sorted(glob.glob(pattern), reverse=True)

    return matches[0] if matches else None


def clean_old_pdfs(image_type, rsid, fl, archid, keep_uptime):
    """删除旧PDF，只保留指定 uptime 的"""
    pdf_dir = build_pdf_dir(image_type, rsid, fl, archid)

    if not os.path.exists(pdf_dir):
        return

    keep_name = f"{fl}_{keep_uptime}.pdf"
    pattern = os.path.join(pdf_dir, f"{fl}_*.pdf")

    for old_pdf in glob.glob(pattern):
        if os.path.basename(old_pdf) != keep_name:
            try:
                os.remove(old_pdf)
            except Exception as e:
                logger.warning(f"删除旧PDF失败: {old_pdf}, {e}")


# ==================== PDF生成 ====================
def images_to_pdf(image_dir, output_pdf_path,
                  page_size='A4', vertical=True,
                  margin_up=1, margin_down=1,
                  margin_left=1, margin_right=1,
                  dpi=150):
    """
    将目录下所有解密后的图片合成为一个多页PDF
    dpi: 图片分辨率，越小图片在PDF上越大越清晰
    """
    if not os.path.exists(image_dir):
        return False, f"图片目录不存在: {image_dir}"

    image_files = sorted([
        f for f in os.listdir(image_dir)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    ])

    if not image_files:
        return False, "目录下无图片文件"

    os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)

    page_width, page_height = get_pdf_page_size(page_size, vertical)
    usable_width = page_width - margin_left - margin_right
    usable_height = page_height - margin_up - margin_down

    c = canvas.Canvas(output_pdf_path, pagesize=(page_width, page_height))

    for img_file in image_files:
        encrypted_path = os.path.join(image_dir, img_file)

        try:
            img = decrypt_image(encrypted_path)
            img_w, img_h = img.size

            # 按 DPI 计算图片物理尺寸（磅）
            img_width_pt = img_w / dpi * 72
            img_height_pt = img_h / dpi * 72

            # 缩放到页面可用区域
            scale = min(usable_width / img_width_pt, usable_height / img_height_pt)
            new_w = img_width_pt * scale
            new_h = img_height_pt * scale

            x = margin_left + (usable_width - new_w) / 2
            y = margin_down + (usable_height - new_h) / 2

            # 转 RGB，JPEG 不支持透明通道
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG', quality=85, dpi=(dpi, dpi))
            img_buffer.seek(0)

            c.drawImage(ImageReader(img_buffer), x, y, width=new_w, height=new_h)
            c.showPage()

        except Exception as e:
            c.showPage()
            logger.warning(f"图片处理失败: {encrypted_path}, 错误: {e}")

    c.save()
    return True, output_pdf_path

def get_or_generate_pdf(image_type, rsid, fl, archid,
                        page_size='A4', vertical=True,
                        margin_up=1, margin_down=1,
                        margin_left=1, margin_right=1,
                        force_regenerate=False):
    """
    获取或生成PDF文件
    
    逻辑:
    1. 查 MAX(uptime) → 只要有一张图更新就算过期
    2. PDF文件名: {fl}_{uptime}.pdf
    3. 文件存在且不强制 → 直接返回
    4. 不存在或强制 → 解密所有图生成新PDF，删旧PDF
    
    返回: (success: bool, result: str)
    """
    latest_uptime, image_count = get_latest_uptime(rsid, archid, image_type)

    if latest_uptime is None:
        return False, "未扫描或扫描未上传"

    pdf_path = build_pdf_path(image_type, rsid, fl, archid, latest_uptime)

    if os.path.exists(pdf_path) and not force_regenerate:
        return True, pdf_path

    clean_old_pdfs(image_type, rsid, fl, archid, latest_uptime)

    image_dir = build_image_dir(image_type, rsid, fl, archid)

    return images_to_pdf(
        image_dir=image_dir,
        output_pdf_path=pdf_path,
        page_size=page_size,
        vertical=vertical,
        margin_up=margin_up,
        margin_down=margin_down,
        margin_left=margin_left,
        margin_right=margin_right
    )


def check_scan_exists(image_type, rsid, fl, archid):
    """
    检查是否已扫描
    返回: (is_scanned: bool, image_count: int)
    """
    _, count = get_latest_uptime(rsid, archid, image_type)
    return count > 0, count
