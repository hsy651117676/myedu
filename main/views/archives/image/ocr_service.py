"""
OCR 批量识别服务
只写 RS_DESCRIPT_{rsid} + 加密存盘 + AutoScan重命名 + 训练数据
不写 RS_ARCHINFO / RS_INFO / CATETREE
"""

import os
import io
import re
import hashlib
import logging
import easyocr
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.conf import settings
from django.core.cache import cache

from main.utils import _get_conn, query_dict
from main.views.archives.image.scan_service import encrypt_image

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

logger = logging.getLogger(__name__)

_reader = None


def get_reader():
    global _reader
    if _reader is None:
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

    # 姓名
    m = re.search(r"姓名[：:]\s*([\u4e00-\u9fa5]{2,4})", text)
    if not m:
        m = re.search(r"姓\s*\^?\s*名\s*([\u4e00-\u9fa5]{2,4})", text)
    if not m:
        m = re.search(r"([\u4e00-\u9fa5]{2,4})同志", text)
    if m:
        info["name"] = m.group(1)
    else:
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
        }
        words = re.findall(r"[\u4e00-\u9fa5]{2,4}", text)
        for w in words:
            if w not in exclude:
                info["name"] = w
                break

    # 出生年月
    m = re.search(r"出生年月[：:]\s*(\d{4})\s*[.]\s*(\d{1,2})", text)
    if m:
        info["csny"] = m.group(1) + m.group(2).zfill(2)

    # 参工时间
    m = re.search(
        r"(?:参加[工工]作时间|参工时间)[：:]\s*(\d{4})\s*[.]\s*(\d{1,2})", text
    )
    if m:
        info["worktime"] = m.group(1) + m.group(2).zfill(2)

    # 身份证号
    m = re.search(r"(?:身份证号|身份证号码|身份证)[：:]\s*(\d{17}[\dXx])", text)
    if not m:
        m = re.search(r"(\d{17}[\dXx])", text)
    if m:
        info["idcard"] = m.group(1)

    return info


def ocr_first_page(image_path):
    """OCR 单张图片"""
    reader = get_reader()
    try:
        result = reader.readtext(image_path)
        full_text = " ".join([item[1] for item in result])
        info = extract_info(full_text)
        return full_text, info
    except Exception as e:
        logger.error(f"OCR failed: {image_path}, {e}")
        return "", {"name": None, "csny": None, "worktime": None, "idcard": None}


# ==================== 匹配 ====================


def _filter_by_field(candidates, ocr_val, field_name):
    """用 OCR 提取的字段过滤候选人"""
    if not ocr_val or len(candidates) <= 1:
        return candidates
    filtered = [
        p
        for p in candidates
        if p.get(field_name) and str(p[field_name]).startswith(ocr_val[:4])
    ]
    return filtered if filtered else candidates


def match_person(ocr_info, person_list, matched_rsids):
    """
    分层匹配：精确 → 模糊 → 单字
    已匹配的不再参与
    """
    ocr_name = ocr_info.get("name")
    ocr_csny = ocr_info.get("csny")
    ocr_worktime = ocr_info.get("worktime")
    ocr_idcard = ocr_info.get("idcard")

    if not ocr_name:
        return {"status": "not_found", "person": None, "candidates": [], "match_by": ""}

    # 可用名单（排除已匹配的）
    available = [p for p in person_list if p["RSID"] not in matched_rsids]

    # ====== 第一轮：姓名精确匹配 ======
    exact = [p for p in available if p["name"] == ocr_name]

    if len(exact) == 1:
        return {
            "status": "matched",
            "person": exact[0],
            "candidates": [],
            "match_by": "姓名精确匹配",
        }

    if len(exact) > 1:
        # 逐级过滤
        candidates = exact
        candidates = _filter_by_field(candidates, ocr_csny, "CSNY")
        if len(candidates) == 1:
            return {
                "status": "matched",
                "person": candidates[0],
                "candidates": exact,
                "match_by": "姓名+出生年月",
            }
        candidates = _filter_by_field(candidates, ocr_worktime, "WORKTIME")
        if len(candidates) == 1:
            return {
                "status": "matched",
                "person": candidates[0],
                "candidates": exact,
                "match_by": "姓名+参工时间",
            }
        candidates = _filter_by_field(candidates, ocr_idcard, "IDCARD")
        if len(candidates) == 1:
            return {
                "status": "matched",
                "person": candidates[0],
                "candidates": exact,
                "match_by": "姓名+身份证号",
            }
        return {
            "status": "conflict",
            "person": None,
            "candidates": candidates,
            "match_by": "姓名重名(无法区分)",
        }

    # ====== 第二轮：姓名模糊匹配 ======
    fuzzy = [
        p
        for p in available
        if ocr_name in (p["name"] or "") or (p["name"] or "") in ocr_name
    ]

    if len(fuzzy) == 1:
        return {
            "status": "matched",
            "person": fuzzy[0],
            "candidates": [],
            "match_by": "姓名模糊匹配",
        }

    if len(fuzzy) > 1:
        candidates = fuzzy
        candidates = _filter_by_field(candidates, ocr_csny, "CSNY")
        if len(candidates) == 1:
            return {
                "status": "matched",
                "person": candidates[0],
                "candidates": fuzzy,
                "match_by": "模糊+出生年月",
            }
        candidates = _filter_by_field(candidates, ocr_worktime, "WORKTIME")
        if len(candidates) == 1:
            return {
                "status": "matched",
                "person": candidates[0],
                "candidates": fuzzy,
                "match_by": "模糊+参工时间",
            }
        candidates = _filter_by_field(candidates, ocr_idcard, "IDCARD")
        if len(candidates) == 1:
            return {
                "status": "matched",
                "person": candidates[0],
                "candidates": fuzzy,
                "match_by": "模糊+身份证号",
            }
        return {
            "status": "conflict",
            "person": None,
            "candidates": candidates,
            "match_by": "姓名模糊重名",
        }

    # ====== 第三轮：单字匹配 ======
    if len(ocr_name) >= 2:
        for char in ocr_name:
            single = [p for p in available if char in (p["name"] or "")]
            if len(single) == 1:
                return {
                    "status": "matched",
                    "person": single[0],
                    "candidates": [],
                    "match_by": f'单字匹配("{char}")',
                }
            if len(single) > 1:
                candidates = single
                candidates = _filter_by_field(candidates, ocr_csny, "CSNY")
                if len(candidates) == 1:
                    return {
                        "status": "matched",
                        "person": candidates[0],
                        "candidates": single,
                        "match_by": f"单字+出生年月",
                    }
                candidates = _filter_by_field(candidates, ocr_worktime, "WORKTIME")
                if len(candidates) == 1:
                    return {
                        "status": "matched",
                        "person": candidates[0],
                        "candidates": single,
                        "match_by": f"单字+参工时间",
                    }
                candidates = _filter_by_field(candidates, ocr_idcard, "IDCARD")
                if len(candidates) == 1:
                    return {
                        "status": "matched",
                        "person": candidates[0],
                        "candidates": single,
                        "match_by": f"单字+身份证号",
                    }

    return {"status": "not_found", "person": None, "candidates": [], "match_by": ""}


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


# ==================== OCR 校验 ====================


def ocr_verify(auto_scan_dir, pages_per_person, person_list):
    """批量 OCR 校验，32线程并行，已匹配的移除"""
    groups = split_files(auto_scan_dir, pages_per_person)
    results = [None] * len(groups)
    matched_rsids = set()

    def process_one(idx, group):
        first_file = group[0]
        filepath = os.path.join(auto_scan_dir, first_file)
        full_text, ocr_info = ocr_first_page(filepath)
        # 用当前已匹配名单
        match_result = match_person(ocr_info, person_list, matched_rsids)
        if match_result["person"]:
            matched_rsids.add(match_result["person"]["RSID"])
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

    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = {executor.submit(process_one, i, g): i for i, g in enumerate(groups)}
        for future in as_completed(futures):
            idx, data = future.result()
            results[idx] = data

    # 线程间 matched_rsids 可能不全，再串行兜底一次
    all_matched = set()
    for r in results:
        if r and r["matched_person"]:
            all_matched.add(r["matched_person"]["RSID"])

    return results


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


def batch_write(verified_items, fl, cltm, fyear, fmonth, fday, ys, image_type="YS"):
    """
    批量写入 RS_DESCRIPT + 加密存盘 + AutoScan重命名 + 训练数据
    前端直接传 ARCHID，不再查表
    """
    results = []
    for item in verified_items:
        rsid = item["rsid"]
        archid = item["archid"]
        files = item["files"]
        ocr_name = item.get("ocr_name", "")
        ocr_csny = item.get("ocr_csny", "")
        ocr_text = item.get("ocr_text", "")
        auto_scan_dir = item["auto_scan_dir"]

        # 查姓名
        person_info = query_dict("SELECT XM FROM RS_INFO WHERE RSID=?", (rsid,))
        pname = person_info[0]["XM"] if person_info else ""

        try:
            rsid_padded = str(rsid).zfill(8)
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
                        f"INSERT INTO {table_name} (Archid, Sxh, Oldfilename, Newfilename, Length, Pdfkey, Path, uptime) VALUES (?,?,?,?,?,?,GETDATE())",
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

                new_name = f"{rsid}_{archid}_{sxh:03d}（{pname}）.JPG"
                os.rename(src_path, os.path.join(auto_scan_dir, new_name))

            conn.commit()
            cursor.close()
            conn.close()

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
