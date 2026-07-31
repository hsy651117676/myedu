"""
OCR 批量识别服务
写 RS_DESCRIPT_{rsid} + RS_ARCHINFO + 加密存盘 + 删除源文件 + 训练数据
"""

import os
import io
import re
import hashlib
import time
import threading
import logging
import easyocr
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.conf import settings
from django.core.cache import cache

from main.utils import _get_conn, query_dict
from main.views.archives.image.scan_service import encrypt_image
from .ocr_preprocess import preprocess

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

logger = logging.getLogger(__name__)

_reader = None
_gpu_lock = threading.Lock()


def get_reader():
    global _reader
    if _reader is None:
        try:
            _reader = easyocr.Reader(["ch_sim", "en"], gpu=True, verbose=False)
            logger.info("easyocr 已启用 GPU 加速")
        except Exception as e:
            logger.warning(f"GPU 初始化失败，降级为 CPU: {e}")
            _reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
    return _reader


# ==================== 缓存 ====================


def get_cached_unit_persons(unit_id):
    """带缓存的单位人员列表"""
    cache_key = f"ocr:unit_persons:{unit_id}"
    persons = cache.get(cache_key)
    if persons is None:
        sql = """
            SELECT RS_INFO.RSID, RS_INFO.XM AS name, RS_INFO.CSNY, RS_INFO.WORKTIME,
                   RS_INFO.IDCARD, DEPART.BMMC AS unit
            FROM USERS_DEPARTMENT
            LEFT JOIN RS_INFO ON USERS_DEPARTMENT.RSID = RS_INFO.RSID
            LEFT JOIN DEPART ON USERS_DEPARTMENT.DEPARTMENTID = DEPART.BM
            WHERE USERS_DEPARTMENT.DEPARTMENTID = ?
            ORDER BY RS_INFO.RYBH
        """
        persons = query_dict(sql, (unit_id,))
        cache.set(cache_key, persons, 1800)
    return persons


def get_cached_arch_info(rsid, fl, fyear, fmonth, fday, ys, cltm=""):
    """带缓存的 ARCHID 查询"""
    cache_key = f"ocr:archinfo:{rsid}:{fl}:{fyear}:{fmonth}:{fday}:{ys}:{cltm}"
    info = cache.get(cache_key)
    if info is None:
        sql = """SELECT ARCHID, XH, YS, CLTM, FYEAR, FMONTH, FDAY 
                 FROM RS_ARCHINFO 
                 WHERE RSID=? AND FL=? AND FYEAR=? AND YS=?"""
        params = [int(rsid), int(fl), int(fyear), int(ys)]
        if fmonth:
            sql += " AND FMONTH=?"
            params.append(int(fmonth))
        if fday:
            sql += " AND FDAY=?"
            params.append(int(fday))
        if cltm:
            sql += " AND CLTM=?"
            params.append(cltm)
        rows = query_dict(sql, params)
        if rows:
            records = []
            for r in rows:
                table_name = f"RS_DESCRIPT_{rsid}"
                uploaded = query_dict(
                    f"SELECT COUNT(*) AS cnt FROM {table_name} WHERE Archid=?",
                    (r["ARCHID"],),
                )
                r["uploaded"] = uploaded[0]["cnt"] if uploaded else 0
                records.append(r)
            info = {"exists": True, "records": records}
        else:
            info = {"exists": False, "records": []}
        cache.set(cache_key, info, 1800)
    return info


# ==================== OCR 提取 ====================


def extract_info(text):
    """从 OCR 文本提取：姓名、出生年月、参工时间、身份证号"""
    if not text:
        return {"name": None, "csny": None, "worktime": None, "idcard": None}

    info = {"name": None, "csny": None, "worktime": None, "idcard": None}

    # ====== 姓名 ======
    name = None
    field_chars = {
        "性",
        "别",
        "出",
        "政",
        "职",
        "文",
        "岗",
        "身",
        "民",
        "年",
        "学",
        "专",
        "技",
        "务",
        "位",
        "类",
        "度",
        "号",
        "科",
        "级",
    }
    field_words = {
        "政治",
        "出生",
        "身份",
        "民族",
        "文化",
        "职务",
        "岗位",
        "专业",
        "年度",
        "学历",
        "面貌",
        "类别",
        "等级",
    }

    # 1. 标准格式：姓名：张三
    m = re.search(r"姓名\s*[：:]\s*([\u4e00-\u9fa5]{2,4})", text)
    if m:
        name = m.group(1)

    # 2. "姓 名" 拆开，跳过所有非汉字字符：姓 ^名 | 王萍
    if not name:
        m = re.search(
            r"姓[^\u4e00-\u9fa5]*名[^\u4e00-\u9fa5]*([\u4e00-\u9fa5]{2,4})", text
        )
        if m:
            candidate = m.group(1)
            if len(candidate) == 3:
                if candidate[-1] in field_chars:
                    candidate = candidate[:2]
            elif len(candidate) == 4:
                if candidate[-2:] in field_words:
                    candidate = candidate[:2]
                elif candidate[-1] in field_chars:
                    candidate = candidate[:3]
            name = candidate

    # 3. "同志" 后缀：张三同志
    if not name:
        m = re.search(r"([\u4e00-\u9fa5]{2,4})同志", text)
        if m:
            name = m.group(1)

    # 4. 兜底：抓 2-4 个连续汉字，排除常见非姓名词
    if not name:
        exclude = {
            "关于",
            "根据",
            "按照",
            "现将",
            "同意",
            "批准",
            "以上",
            "以下",
            "第一",
            "第二",
            "第三",
            "本表",
            "材料",
            "档案",
            "干部",
            "人事",
            "单位",
            "部门",
            "职务",
            "职称",
            "学历",
            "学位",
            "毕业",
            "工作",
            "年度",
            "考核",
            "登记",
            "志愿",
            "申请",
            "审批",
            "报告",
            "通知",
            "团结",
            "政治",
            "党员",
            "团员",
            "群众",
            "中共",
            "民族",
            "汉族",
            "文化",
            "程度",
            "大学",
            "本科",
            "大专",
            "中专",
            "高中",
            "初中",
            "小学",
            "出生",
            "年月",
            "参加",
            "身份",
            "号码",
            "性别",
            "男女",
            "贵州",
            "贵州省",
            "贵州省事",
            "盘州",
            "柏果",
            "洒基",
            "事业单位",
            "工作人员",
            "特岗教师",
            "二级教师",
            "教师",
            "班主任",
            "数学",
            "语文",
            "英语",
            "教育教学",
        }
        words = re.findall(r"[\u4e00-\u9fa5]{2,4}", text)
        for w in words:
            if w not in exclude:
                name = w
                break

    info["name"] = name

    # ====== 出生年月 ======
    m = re.search(
        r"(?:出生年月|出生日期|出生时间)\s*[：:，,\s]*\s*(\d{4})\s*[.年、,\s]*\s*(\d{1,2})",
        text,
    )
    if m:
        info["csny"] = m.group(1) + m.group(2).zfill(2)

    # ====== 参工时间 ======
    m = re.search(
        r"(?:参加工作|参工时间|参加工作时间|参加革命工作|入伍时间|工龄起算)\s*[：:，,\s]*\s*(\d{4})\s*[.年、,\s]*\s*(\d{1,2})",
        text,
    )
    if m:
        info["worktime"] = m.group(1) + m.group(2).zfill(2)

    # ====== 身份证号 ======
    m = re.search(
        r"(?:身份证号|身份证号码|身份证编号|公民身份号码|证件号码)\s*[：:，,\s]*\s*(\d{17}[\dXx])",
        text,
    )
    if not m:
        m = re.search(r"(\d{17}[\dXx])", text)
    if m:
        info["idcard"] = m.group(1)

    return info


# ==================== OCR 单张图片 ====================


def ocr_first_page(image_path):
    """
    OCR 单张图片（带预处理 + 缓存 + GPU锁）
    缓存只存 OCR 原文，用文件 md5 做 key
    """
    # ---- 用文件 md5 做缓存 key ----
    try:
        with open(image_path, "rb") as f:
            file_md5 = hashlib.md5(f.read()).hexdigest()
        cache_key = f"ocr:text:{file_md5}"
    except OSError:
        cache_key = None

    if cache_key:
        cached_text = cache.get(cache_key)
        if cached_text:
            logger.debug(f"OCR 缓存命中: {image_path}")
            info = extract_info(cached_text)
            return cached_text, info

    # ---- 预处理（CPU，不加锁，可并发） ----
    start_time = time.time()
    processed = preprocess(image_path)

    if processed is None:
        return "", {"name": None, "csny": None, "worktime": None, "idcard": None}

    preprocess_time = time.time() - start_time

    # ---- OCR（GPU，加锁，串行） ----
    full_text = ""
    with _gpu_lock:
        reader = get_reader()
        try:
            result = reader.readtext(processed)
            full_text = " ".join([item[1] for item in result])
            ocr_time = time.time() - start_time - preprocess_time
            logger.debug(
                f"OCR 完成: {image_path} "
                f"(预处理 {preprocess_time:.2f}s, OCR {ocr_time:.2f}s)"
            )
        except Exception as e:
            logger.error(f"OCR failed: {image_path}, {e}")
            return "", {"name": None, "csny": None, "worktime": None, "idcard": None}

    # ---- 提取信息（每次都跑，不缓存） ----
    info = extract_info(full_text)

    # ---- 只缓存 OCR 原文 ----
    if cache_key:
        cache.set(cache_key, full_text, 1800)

    return full_text, info


# ==================== 匹配 ====================


def match_person(ocr_info, person_list, matched_rsids):
    """
    分层匹配：
    第一轮：身份证精确匹配（最高优先级）
    第二轮：姓名精确匹配 + 辅助字段过滤
    第三轮：姓名模糊匹配 + 辅助字段过滤
    """
    ocr_name = ocr_info.get("name")
    ocr_csny = ocr_info.get("csny")
    ocr_worktime = ocr_info.get("worktime")
    ocr_idcard = ocr_info.get("idcard")

    available = [p for p in person_list if p["RSID"] not in matched_rsids]

    # ====== 第一轮：身份证精确匹配 ======
    if ocr_idcard and len(ocr_idcard) == 18:
        idcard_match = [p for p in available if p.get("IDCARD") == ocr_idcard]
        if len(idcard_match) == 1:
            return {
                "status": "matched",
                "person": idcard_match[0],
                "candidates": [],
                "match_by": "身份证精确匹配",
            }
        elif len(idcard_match) > 1:
            return {
                "status": "conflict",
                "person": None,
                "candidates": idcard_match,
                "match_by": "身份证重号(数据异常)",
            }

    if not ocr_name:
        return {"status": "not_found", "person": None, "candidates": [], "match_by": ""}

    # ====== 第二轮：姓名精确匹配 ======
    exact = [p for p in available if p["name"] == ocr_name]

    if len(exact) == 1:
        return {
            "status": "matched",
            "person": exact[0],
            "candidates": [],
            "match_by": "姓名精确匹配",
        }

    if len(exact) > 1:
        filtered = _filter_by_fields(exact, ocr_csny, ocr_worktime)
        if len(filtered) == 1:
            return {
                "status": "matched",
                "person": filtered[0],
                "candidates": exact,
                "match_by": _build_match_by("姓名精确", ocr_csny, ocr_worktime),
            }
        return {
            "status": "conflict",
            "person": None,
            "candidates": filtered if filtered else exact,
            "match_by": "姓名重名(无法区分)",
        }

    # ====== 第三轮：姓名模糊匹配 ======
    fuzzy = [
        p
        for p in available
        if ocr_name in (p["name"] or "") or (p["name"] or "") in ocr_name
    ]

    if len(fuzzy) == 1:
        return {
            "status": "fuzzy",
            "person": fuzzy[0],
            "candidates": [],
            "match_by": "姓名模糊匹配",
        }

    if len(fuzzy) > 1:
        filtered = _filter_by_fields(fuzzy, ocr_csny, ocr_worktime)
        if len(filtered) == 1:
            return {
                "status": "fuzzy",
                "person": filtered[0],
                "candidates": fuzzy,
                "match_by": _build_match_by("模糊", ocr_csny, ocr_worktime),
            }
        return {
            "status": "conflict",
            "person": None,
            "candidates": filtered if filtered else fuzzy,
            "match_by": "姓名模糊重名",
        }

    # ====== 未匹配 ======
    return {"status": "not_found", "person": None, "candidates": [], "match_by": ""}


def _filter_by_fields(candidates, ocr_csny, ocr_worktime):
    """用 OCR 提取的出生年月和参工时间过滤候选人列表。"""
    if not candidates or len(candidates) <= 1:
        return candidates

    result = candidates

    if ocr_csny and len(ocr_csny) >= 4:
        year = ocr_csny[:4]
        filtered = [
            p for p in result if p.get("CSNY") and str(p["CSNY"]).startswith(year)
        ]
        if len(filtered) == 1:
            return filtered
        if len(filtered) > 1:
            result = filtered

    if ocr_worktime and len(ocr_worktime) >= 4:
        year = ocr_worktime[:4]
        filtered = [
            p
            for p in result
            if p.get("WORKTIME") and str(p["WORKTIME"]).startswith(year)
        ]
        if len(filtered) >= 1:
            result = filtered

    return result


def _build_match_by(prefix, ocr_csny, ocr_worktime):
    """生成匹配依据描述"""
    parts = [prefix]
    if ocr_csny:
        parts.append("出生年月")
    if ocr_worktime:
        parts.append("参工时间")
    return "+".join(parts)


# ==================== 文件处理 ====================


def split_files(auto_scan_dir, pages_per_person):
    """按页数切割文件列表"""
    files = sorted(
        [
            f
            for f in os.listdir(auto_scan_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
    )
    groups = []
    for i in range(0, len(files), pages_per_person):
        group = files[i : i + pages_per_person]
        if len(group) == pages_per_person:
            groups.append(group)
    return groups


def process_one(idx, group, scan_dir, person_list, matched_rsids):
    """处理单个分组：OCR + 匹配"""
    first_file = group[0]
    filepath = os.path.join(scan_dir, first_file)
    full_text, ocr_info = ocr_first_page(filepath)

    match_result = match_person(ocr_info, person_list, matched_rsids)

    return idx, {
        "index": idx + 1,
        "files": group,
        "first_file": first_file,
        "last_file": group[-1],
        "ocr_text": full_text[:500],
        "ocr_name": ocr_info.get("name") or "",
        "ocr_csny": ocr_info.get("csny") or "",
        "ocr_worktime": ocr_info.get("worktime") or "",
        "ocr_idcard": ocr_info.get("idcard") or "",
        "match_status": match_result["status"],
        "matched_person": match_result["person"],
        "candidates": match_result["candidates"],
        "match_by": match_result["match_by"],
    }


# ==================== PDF ====================


def generate_preview_pdf(auto_scan_dir, files):
    """内存生成 PDF 预览（AutoScan 文件）"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    buffer = io.BytesIO()
    page_w, page_h = A4
    c = canvas.Canvas(buffer, pagesize=A4)

    for f in files:
        filepath = os.path.join(auto_scan_dir, f)
        try:
            img = Image.open(filepath)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            img_w, img_h = img.size
            scale = min(page_w / img_w, page_h / img_h) * 0.9
            new_w = img_w * scale
            new_h = img_h * scale
            x = (page_w - new_w) / 2
            y = (page_h - new_h) / 2
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            buf.seek(0)
            c.drawImage(ImageReader(buf), x, y, width=new_w, height=new_h)
            c.showPage()
        except Exception as e:
            logger.error(f"PDF preview error: {filepath}, {e}")
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def generate_existing_pdf(rsid, fl, archid, image_type="YS"):
    """内存生成已有扫描件 PDF"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from main.views.archives.image.scan_service import build_image_dir, decrypt_image

    image_dir = build_image_dir(image_type, rsid, fl, archid)
    buffer = io.BytesIO()
    page_w, page_h = A4
    c = canvas.Canvas(buffer, pagesize=A4)

    if os.path.exists(image_dir):
        image_files = sorted(
            [
                f
                for f in os.listdir(image_dir)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
        )
        for img_file in image_files:
            try:
                img = decrypt_image(os.path.join(image_dir, img_file))
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                img_w, img_h = img.size
                scale = min(page_w / img_w, page_h / img_h) * 0.9
                new_w = img_w * scale
                new_h = img_h * scale
                x = (page_w - new_w) / 2
                y = (page_h - new_h) / 2
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                buf.seek(0)
                c.drawImage(ImageReader(buf), x, y, width=new_w, height=new_h)
                c.showPage()
            except Exception as e:
                logger.error(f"PDF error: {img_file}, {e}")

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# ==================== 写入 ====================

ALLOWED_MATCH_BY = [
    "身份证精确匹配",
    "姓名精确匹配",
    "姓名精确+出生年月",
    "姓名精确+参工时间",
    "姓名精确+出生年月+参工时间",
    "人工修正",
]


def batch_write(
    verified_items, fl, cltm, fyear, fmonth, fday, ys, bz="", image_type="YS"
):
    """
    批量写入 RS_ARCHINFO + RS_DESCRIPT + 加密存盘 + 删除源文件 + 训练数据
    RS_ARCHINFO 按材料形成日期排序定 XH，已有则更新，无则插入
    校验 match_by，不在白名单内的拒绝写入
    全部成功后删除源文件，失败则保留
    """
    results = []
    for item in verified_items:
        rsid = item["rsid"]
        files = item["files"]
        ocr_name = item.get("ocr_name", "")
        ocr_csny = item.get("ocr_csny", "")
        ocr_text = item.get("ocr_text", "")
        match_by = item.get("match_by", "")
        auto_scan_dir = item["auto_scan_dir"]

        # 校验匹配方式
        if match_by not in ALLOWED_MATCH_BY:
            results.append(
                {
                    "rsid": rsid,
                    "status": "error",
                    "msg": f"匹配方式 '{match_by}' 不在白名单，请确认后再写入",
                }
            )
            continue

        # 查姓名
        person_info = query_dict("SELECT XM FROM RS_INFO WHERE RSID=?", (rsid,))
        pname = person_info[0]["XM"] if person_info else ""

        try:
            rsid_padded = str(rsid).zfill(8)

            # ========== 写入 RS_ARCHINFO ==========
            conn = _get_conn()
            cursor = conn.cursor()

            # 查是否已存在（同年月日 + 同材料名 + 同页数）
            cursor.execute(
                "SELECT ARCHID, XH FROM RS_ARCHINFO WHERE RSID=? AND FL=? AND FYEAR=? AND ISNULL(FMONTH,0)=? AND ISNULL(FDAY,0)=? AND CLTM=? AND YS=?",
                (
                    int(rsid),
                    int(fl),
                    int(fyear),
                    int(fmonth or 0),
                    int(fday or 0),
                    cltm,
                    int(ys),
                ),
            )
            existing = cursor.fetchone()

            if existing:
                # 已存在：更新 BZ
                archid, xh = existing
                cursor.execute(
                    "UPDATE RS_ARCHINFO SET BZ=? WHERE ARCHID=?",
                    (bz or "", archid),
                )
            else:
                # 不存在：按日期找插入位置
                cursor.execute(
                    """SELECT ISNULL(MIN(XH), 0) FROM RS_ARCHINFO 
                       WHERE RSID=? AND FL=? 
                         AND (FYEAR > ? OR (FYEAR = ? AND ISNULL(FMONTH,0) > ?) OR (FYEAR = ? AND ISNULL(FMONTH,0) = ? AND ISNULL(FDAY,0) >= ?))""",
                    (
                        int(rsid),
                        int(fl),
                        int(fyear),
                        int(fyear),
                        int(fmonth or 0),
                        int(fyear),
                        int(fmonth or 0),
                        int(fday or 0),
                    ),
                )
                row = cursor.fetchone()

                if row and row[0] > 0:
                    # 插入到该位置，后面的 XH 都 +1
                    xh = row[0]
                    cursor.execute(
                        "UPDATE RS_ARCHINFO SET XH = XH + 1 WHERE RSID=? AND FL=? AND XH >= ?",
                        (int(rsid), int(fl), xh),
                    )
                else:
                    # 追加到末尾
                    cursor.execute(
                        "SELECT ISNULL(MAX(XH), 0) + 1 FROM RS_ARCHINFO WHERE RSID=? AND FL=?",
                        (int(rsid), int(fl)),
                    )
                    xh = cursor.fetchone()[0]

                # 插入新记录
                cursor.execute(
                    "INSERT INTO RS_ARCHINFO (RSID, XH, FL, CLTM, FYEAR, FMONTH, FDAY, YS, BZ, ADDTIME) VALUES (?,?,?,?,?,?,?,?,?,GETDATE())",
                    (
                        int(rsid),
                        xh,
                        int(fl),
                        cltm,
                        int(fyear),
                        int(fmonth or 0),
                        int(fday or 0),
                        int(ys),
                        bz or "",
                    ),
                )
                cursor.execute("SELECT @@IDENTITY AS ARCHID")
                archid = cursor.fetchone()[0]

            conn.commit()
            cursor.close()
            conn.close()

            # ========== 加密存盘 + 写 RS_DESCRIPT ==========
            image_dir = os.path.join(
                settings.SCAN_IMAGE_BASE_DIR,
                image_type,
                rsid_padded,
                str(fl),
                str(archid),
            )
            os.makedirs(image_dir, exist_ok=True)

            conn = _get_conn()
            cursor = conn.cursor()
            table_name = f"RS_DESCRIPT_{rsid}"

            for sxh, src_filename in enumerate(files, 1):
                src_path = os.path.join(auto_scan_dir, src_filename)
                dst_filename = f"{sxh:03d}.JPG"
                dst_path = os.path.join(image_dir, dst_filename)

                with open(src_path, "rb") as f:
                    raw_data = f.read()

                encrypted_data = encrypt_image(raw_data)
                with open(dst_path, "wb") as f:
                    f.write(encrypted_data)

                pdfkey = hashlib.md5(raw_data).hexdigest()
                file_size = len(raw_data)
                path = f"{rsid_padded}\\{fl}\\{archid}\\"

                cursor.execute(
                    f"SELECT COUNT(*) FROM {table_name} WHERE Archid=? AND Sxh=?",
                    (archid, sxh),
                )
                exists = cursor.fetchone()[0]
                if exists:
                    cursor.execute(
                        f"UPDATE {table_name} SET Oldfilename=?, Newfilename=?, Length=?, Pdfkey=?, Path=?, uptime=GETDATE() WHERE Archid=? AND Sxh=?",
                        (
                            src_filename,
                            dst_filename,
                            file_size,
                            pdfkey,
                            path,
                            archid,
                            sxh,
                        ),
                    )
                else:
                    cursor.execute(
                        f"INSERT INTO {table_name} (Archid, Sxh, Oldfilename, Newfilename, Length, Pdfkey, Path, uptime) VALUES (?,?,?,?,?,?,?,GETDATE())",
                        (
                            archid,
                            sxh,
                            src_filename,
                            dst_filename,
                            file_size,
                            pdfkey,
                            path,
                        ),
                    )

            conn.commit()
            cursor.close()
            conn.close()

            # ---- 全部成功，删除源文件 ----
            for src_filename in files:
                src_path = os.path.join(auto_scan_dir, src_filename)
                try:
                    os.remove(src_path)
                except OSError as e:
                    logger.warning(f"删除源文件失败: {src_path}, {e}")

            # 训练数据
            try:
                from django.db import connection as mysql_conn

                with mysql_conn.cursor() as mc:
                    mc.execute(
                        "INSERT INTO ocr_train_data (ocr_text, correct_name, correct_csny, correct_rsid) VALUES (%s, %s, %s, %s)",
                        (ocr_text[:1000], pname, ocr_csny, rsid),
                    )
            except Exception as e:
                logger.warning(f"训练数据写入失败: {e}")

            # 清缓存
            cache.delete_pattern(f"ocr:archinfo:{rsid}:*")

            results.append(
                {
                    "rsid": rsid,
                    "archid": archid,
                    "status": "success",
                    "pages": len(files),
                }
            )

        except Exception as e:
            logger.error(f"写入失败: rsid={rsid}, {e}")
            results.append({"rsid": rsid, "status": "error", "msg": str(e)})

    return results
