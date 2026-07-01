"""档案扫描上传服务"""

import logging
import os
from datetime import datetime
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from main.utils import _get_conn
from main.views.archives.image.scan_service import (
    build_image_dir,
    encrypt_image,
)

logger = logging.getLogger(__name__)


@login_required
@csrf_exempt
def upload_scan_api(request):
    """档案扫描件上传（加密+写RS_DESCRIPT表）"""
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST"})

    image_type = request.POST.get("image_type", "YS")
    rsid = request.POST.get("rsid", "")
    fl = request.POST.get("fl", "")
    archid = request.POST.get("archid", "")
    filename = request.POST.get("filename", "")
    pdfkey = request.POST.get("pdfkey", "")

    if not all([rsid, fl, archid, filename]):
        return JsonResponse({"code": 400, "msg": "参数不完整"})

    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"code": 400, "msg": "缺少文件"})

    try:
        raw_data = uploaded_file.read()

        # ========== 解密 ==========
        import struct
        from Crypto.Cipher import AES

        aes_key = settings.SCAN_AES_KEY
        original_size = struct.unpack("<I", raw_data[:4])[0]
        enc = raw_data[8:]
        encrypted_size = ((original_size + 15) // 16) * 16
        enc = enc[:encrypted_size]

        cipher = AES.new(aes_key, AES.MODE_ECB)
        decrypted = cipher.decrypt(enc)
        plain = decrypted[:original_size]

        if plain[:2] != b"\xff\xd8" and plain[:4] != b"\x89PNG":
            return JsonResponse({"code": 400, "msg": "解密后不是有效图片"})

        # ========== MD5验证 ==========
        import hashlib

        decrypted_md5 = hashlib.md5(plain).hexdigest()
        if pdfkey and decrypted_md5 != pdfkey:
            return JsonResponse(
                {"code": 400, "msg": f"MD5不匹配: 期望{pdfkey}, 实际{decrypted_md5}"}
            )

        # ========== 文件名验证 ==========
        import re

        if not re.match(r"^\d{3}\.JPG$", filename, re.IGNORECASE):
            return JsonResponse(
                {"code": 400, "msg": "文件名格式错误，必须为001.JPG格式"}
            )

        sxh = int(filename[:3])

        # ========== 材料存在性 + 页数验证 ==========
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT YS FROM RS_ARCHINFO WHERE ARCHID=?", (archid,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return JsonResponse({"code": 400, "msg": "材料不存在"})

        max_pages = row[0] or 0
        if max_pages == 0:
            cursor.close()
            conn.close()
            return JsonResponse({"code": 400, "msg": "目录页数为0，无法上传"})

        if sxh > max_pages:
            cursor.close()
            conn.close()
            return JsonResponse(
                {
                    "code": 400,
                    "msg": f"超出目录页数限制: 目录{max_pages}页, 当前第{sxh}页",
                }
            )

        table_name = f"RS_DESCRIPT_{rsid}"
        cursor.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE Archid=? AND Oldfilename=?",
            (archid, filename),
        )
        row = cursor.fetchone()
        existing = row[0] if row else 0

        if existing == 0:
            cursor.execute(
                f"SELECT COUNT(DISTINCT Oldfilename) FROM {table_name} WHERE Archid=?",
                (archid,),
            )
            row = cursor.fetchone()
            uploaded_count = row[0] if row else 0
            if uploaded_count >= max_pages:
                cursor.close()
                conn.close()
                return JsonResponse(
                    {
                        "code": 400,
                        "msg": f"超出目录页数限制: 目录{max_pages}页, 已上传{uploaded_count}页",
                    }
                )

        cursor.close()
        conn.close()

        # ========== 先写数据库 ==========
        _update_descript(rsid, archid, filename, len(plain), pdfkey, fl)

        # ========== 再写磁盘 ==========
        try:
            encrypted_data = encrypt_image(plain)
            image_dir = build_image_dir(image_type, rsid, fl, archid)
            os.makedirs(image_dir, exist_ok=True)
            save_path = os.path.join(image_dir, filename)
            with open(save_path, "wb") as f:
                f.write(encrypted_data)
        except Exception:
            # 磁盘写失败，回滚数据库记录
            _delete_descript(rsid, archid, filename)
            raise

        return JsonResponse({"code": 0, "msg": "上传成功"})
    except Exception as e:
        logger.error(f"上传扫描件失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})


def _update_descript(rsid, archid, filename, length, pdfkey, fl):
    """更新RS_DESCRIPT表"""
    table_name = f"RS_DESCRIPT_{rsid}"
    uptime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE Archid=? AND Oldfilename=?",
            (archid, filename),
        )
        row = cursor.fetchone()
        if row and row[0] > 0:
            cursor.execute(
                f"UPDATE {table_name} SET Length=?, Pdfkey=?, uptime=? WHERE Archid=? AND Oldfilename=?",
                (length, pdfkey, uptime, archid, filename),
            )
        else:
            cursor.execute(
                f"SELECT ISNULL(MAX(Sxh),0) FROM {table_name} WHERE Archid=?", (archid,)
            )
            row = cursor.fetchone()
            sxh = (row[0] if row else 0) + 1
            rsid_padded = str(rsid).zfill(8)
            path = f"{rsid_padded}\\{fl}\\{archid}\\"
            cursor.execute(
                f"INSERT INTO {table_name} (Archid, Sxh, Oldfilename, Newfilename, Length, Pdfkey, Path, uptime) VALUES (?,?,?,?,?,?,?,?)",
                (archid, sxh, filename, filename, length, pdfkey, path, uptime),
            )
        conn.commit()
        cursor.close()
    except Exception as e:
        logger.error(f"更新RS_DESCRIPT失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


@login_required
def clean_orphans_api(request):
    """清理孤立扫描记录"""
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少RSID"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        table_name = f"RS_DESCRIPT_{rsid}"

        cursor.execute(
            f"""
            DELETE FROM {table_name}
            WHERE NOT EXISTS (
                SELECT 1 FROM RS_ARCHINFO a 
                WHERE a.RSID = ? AND a.ARCHID = {table_name}.Archid
            )
        """,
            (int(rsid),),
        )

        deleted = cursor.rowcount
        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": f"已清理 {deleted} 条孤立记录"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@csrf_exempt
def delete_scan_api(request):
    """删除单个扫描文件（磁盘+数据库）"""
    if request.method != "POST":
        return JsonResponse({"code": 405})

    data = json.loads(request.body)
    rsid = data.get("rsid", "")
    archid = data.get("archid", "")
    filename = data.get("filename", "")

    if not all([rsid, archid, filename]):
        return JsonResponse({"code": 400})

    try:
        table_name = f"RS_DESCRIPT_{rsid}"
        conn = _get_conn()
        cursor = conn.cursor()

        # 查Path
        cursor.execute(
            f"SELECT Path FROM {table_name} WHERE Archid=? AND Oldfilename=?",
            (archid, filename),
        )
        row = cursor.fetchone()
        if row:
            path = row[0] or ""
            full_path = os.path.join("/mnt/bigdata/das_images/YS", path, filename)
            if os.path.exists(full_path):
                os.remove(full_path)

        cursor.execute(
            f"DELETE FROM {table_name} WHERE Archid=? AND Oldfilename=?",
            (archid, filename),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return JsonResponse({"code": 0, "msg": "已删除"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
@csrf_exempt
def update_page_count_api(request):
    """修改材料目录的页数"""
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST"})

    try:
        data = json.loads(request.body)
        rsid = data.get("rsid", "")
        archid = data.get("archid", "")
        ys = data.get("ys", "")

        if not all([rsid, archid, ys]):
            return JsonResponse({"code": 400, "msg": "参数不完整"})

        try:
            new_ys = int(ys)
            if new_ys <= 0:
                return JsonResponse({"code": 400, "msg": "页数必须大于0"})
        except (ValueError, TypeError):
            return JsonResponse({"code": 400, "msg": "页数格式错误"})

        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT CLTM, YS FROM RS_ARCHINFO WHERE ARCHID=?", (archid,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return JsonResponse({"code": 400, "msg": "材料不存在"})

        old_ys = row[1] or 0
        cltm = row[0]

        # 检查已上传页数
        table_name = f"RS_DESCRIPT_{rsid}"
        cursor.execute(
            f"SELECT COUNT(DISTINCT Oldfilename) FROM {table_name} WHERE Archid=?",
            (archid,),
        )
        uploaded = cursor.fetchone()[0]

        if new_ys < uploaded:
            cursor.close()
            conn.close()
            return JsonResponse(
                {
                    "code": 400,
                    "msg": f"新页数({new_ys})不能小于已上传页数({uploaded})，请先删除多余扫描件",
                }
            )

        cursor.execute("UPDATE RS_ARCHINFO SET YS=? WHERE ARCHID=?", (new_ys, archid))
        conn.commit()
        cursor.close()
        conn.close()

        logger.info(
            f"修改页码: rsid={rsid}, archid={archid}, {cltm}, {old_ys}→{new_ys}"
        )
        return JsonResponse({"code": 0, "msg": f"页码已更新: {old_ys}→{new_ys}"})

    except Exception as e:
        logger.error(f"修改页码失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})


def _delete_descript(rsid, archid, filename):
    """回滚：删除RS_DESCRIPT记录"""
    table_name = f"RS_DESCRIPT_{rsid}"
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"DELETE FROM {table_name} WHERE Archid=? AND Oldfilename=?",
            (archid, filename),
        )
        conn.commit()
        cursor.close()
    except Exception as e:
        logger.error(f"回滚RS_DESCRIPT失败: {e}")
    finally:
        if conn:
            conn.close()
