"""
档案扫描查看 - 视图层
"""

import os
import json
import zipfile
import logging
from io import BytesIO
from datetime import datetime
from urllib.parse import quote

from django.http import (
    JsonResponse,
    HttpResponse,
    FileResponse,
    Http404,
    StreamingHttpResponse,
)
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings

from main.utils import _get_conn
from main.views.archives.image.scan_service import (
    get_or_generate_pdf,
    check_scan_exists,
    build_pdf_path,
    IMAGE_TYPES,
)
from main.utils.decorators import archive_perm_required

logger = logging.getLogger(__name__)


@login_required
@archive_perm_required
def scan_page(request):
    """档案扫描查看页面入口"""
    return render(request, "archives/image/scan_viewer.html")


@login_required
def api_check_scan(request):
    """检查是否已扫描"""
    image_type = request.GET.get("image_type", "YS")
    rsid = request.GET.get("rsid", "")
    fl = request.GET.get("fl", "")
    archid = request.GET.get("archid", "")

    if image_type not in IMAGE_TYPES:
        return JsonResponse({"code": 400, "msg": f"不支持的图像类型: {image_type}"})

    is_scanned, count = check_scan_exists(image_type, rsid, fl, archid)
    return JsonResponse({"code": 0, "is_scanned": is_scanned, "image_count": count})


@login_required
def api_generate_pdf(request):
    """生成/获取PDF"""
    image_type = request.GET.get("image_type", "YS")
    rsid = request.GET.get("rsid", "")
    fl = request.GET.get("fl", "")
    archid = request.GET.get("archid", "")
    force = request.GET.get("force", "0") == "1"
    page_size = request.GET.get("page_size", settings.SCAN_PDF_PAGE_SIZE)
    vertical = request.GET.get("vertical", "1") == "1"

    if image_type not in IMAGE_TYPES:
        return JsonResponse({"code": 400, "msg": f"不支持的图像类型: {image_type}"})

    success, result = get_or_generate_pdf(
        image_type=image_type,
        rsid=rsid,
        fl=fl,
        archid=archid,
        page_size=page_size,
        vertical=vertical,
        force_regenerate=force,
    )

    if success:
        return JsonResponse(
            {
                "code": 0,
                "success": True,
                "pdf_url": f"/archives/image/api/scan-pdf/?image_type={image_type}&rsid={rsid}&fl={fl}&archid={archid}",
            }
        )
    else:
        return JsonResponse({"code": 0, "success": False, "message": result})


@login_required
def serve_pdf(request):
    rsid = request.GET.get("rsid", "")
    archid = request.GET.get("archid", "")

    if "?" in archid:
        archid = archid.split("?")[0]
    if "&" in archid:
        archid = archid.split("&")[0]

    if not rsid or not archid:
        raise Http404

    pdf_path = build_pdf_path(rsid, archid)

    if not os.path.exists(pdf_path):
        raise Http404("PDF不存在")

    response = FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
    response["Content-Disposition"] = "inline"
    response["Cache-Control"] = "public, max-age=3600"
    return response


@login_required
@csrf_exempt
def api_batch_generate_pdf(request):
    """批量生成某人员所有已扫描材料的PDF（SSE 流式返回进度）"""
    if request.method != "POST":
        return JsonResponse({"code": 405})

    try:
        data = json.loads(request.body)
        rsid = str(data.get("rsid", "")).strip()
    except:
        return JsonResponse({"code": 400, "msg": "参数格式错误"})

    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少rsid"})

    def event_stream():
        conn = None
        try:
            conn = _get_conn()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT ARCHID, FL FROM RS_ARCHINFO WHERE RSID = ? ORDER BY FL, XH",
                (int(rsid),),
            )
            rows = cursor.fetchall()
            cursor.close()

            if not rows:
                yield f"data: {json.dumps({'done': True, 'total': 0, 'success': 0, 'skipped': 0, 'failed': 0, 'msg': '该人员无档案材料'})}\n\n"
                return

            # 先过滤出"已扫描"的材料
            scanned_items = []
            for archid, fl in rows:
                archid = str(archid)
                fl = str(fl) if fl else ""
                is_scanned, _ = check_scan_exists("YS", rsid, fl, archid)
                if is_scanned:
                    scanned_items.append((archid, fl))

            total = len(scanned_items)
            if total == 0:
                yield f"data: {json.dumps({'done': True, 'total': 0, 'success': 0, 'skipped': 0, 'failed': 0, 'msg': '该人员无已扫描材料'})}\n\n"
                return

            yield f"data: {json.dumps({'start': True, 'total': total})}\n\n"

            success = 0
            skipped = 0
            failed = 0
            current = 0

            for archid, fl in scanned_items:
                current += 1

                # 检查PDF是否已存在
                pdf_path = build_pdf_path(rsid, archid)
                if os.path.exists(pdf_path):
                    skipped += 1
                    yield f"data: {json.dumps({'current': current, 'total': total, 'archid': archid, 'status': 'skipped'})}\n\n"
                    continue

                ok, result = get_or_generate_pdf(
                    image_type="YS",
                    rsid=rsid,
                    fl=fl,
                    archid=archid,
                    force_regenerate=False,
                )
                if ok:
                    success += 1
                    yield f"data: {json.dumps({'current': current, 'total': total, 'archid': archid, 'status': 'success'})}\n\n"
                else:
                    failed += 1
                    yield f"data: {json.dumps({'current': current, 'total': total, 'archid': archid, 'status': 'failed', 'msg': result})}\n\n"

            yield f"data: {json.dumps({'done': True, 'total': total, 'success': success, 'skipped': skipped, 'failed': failed})}\n\n"

        except Exception as e:
            logger.error(f"批量生成PDF失败: {e}")
            yield f"data: {json.dumps({'done': True, 'error': str(e)})}\n\n"
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# ==================== ZIP 打包下载 ====================

# 中文数字映射
CN_NUM_MAP = {
    "一": "1",
    "二": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "六": "6",
    "七": "7",
    "八": "8",
    "九": "9",
    "十": "10",
}


def _normalize_jbbh(jbbh):
    """把 JBBH 的中文数字转成阿拉伯数字：一→1，十→10"""
    if not jbbh:
        return ""
    s = str(jbbh).strip()
    # 先处理 "十" 开头的（十、十一...）
    if s.startswith("十"):
        if len(s) == 1:
            s = "10"
        else:
            s = "1" + CN_NUM_MAP.get(s[1], s[1])
    else:
        s = CN_NUM_MAP.get(s, s)
    return s


@login_required
def api_download_zip(request):
    """下载该人员档案 PDF 压缩包"""
    rsid = request.GET.get("rsid", "").strip()
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少rsid"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # 1. 查姓名
        cursor.execute("SELECT XM FROM RS_INFO WHERE RSID = ?", (int(rsid),))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return JsonResponse({"code": 404, "msg": "人员不存在"})
        person_name = (row[0] or rsid).strip()
        for ch in ["\\", "/", ":", "*", "?", '"', "<", ">", "|"]:
            person_name = person_name.replace(ch, "_")

        # 2. 查该人员所有材料 + JBBH
        cursor.execute(
            """
            SELECT a.ARCHID, a.CLTM, a.XH, c.JBBH
            FROM RS_ARCHINFO a
            LEFT JOIN CATETREE c ON a.FL = c.FL
            WHERE a.RSID = ?
            ORDER BY a.FL, a.XH
        """,
            (int(rsid),),
        )
        materials = cursor.fetchall()
        cursor.close()

        if not materials:
            return JsonResponse({"code": 400, "msg": "该人员无档案材料"})

        # 3. 打包
        buffer = BytesIO()
        added = 0
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for archid, cltm, xh, jbbh in materials:
                pdf_path = build_pdf_path(rsid, str(archid))
                if not os.path.exists(pdf_path):
                    continue

                # 拼接文件名：{JBBH}_{XH}_{CLTM}.pdf
                jbbh_str = _normalize_jbbh(jbbh)
                cltm_str = (cltm or str(archid)).strip()
                xh_str = str(xh) if xh is not None else ""

                # 清理非法字符
                for ch in ["\\", "/", ":", "*", "?", '"', "<", ">", "|"]:
                    cltm_str = cltm_str.replace(ch, "_")

                # 拼前缀
                prefix_parts = []
                if jbbh_str:
                    prefix_parts.append(jbbh_str)
                if xh_str:
                    prefix_parts.append(xh_str)
                prefix = "-".join(prefix_parts)

                if prefix:
                    filename = f"{prefix}_{cltm_str}.pdf"
                else:
                    filename = f"{cltm_str}.pdf"

                # ZIP 内路径：张三/xxx.pdf
                arcname = f"{person_name}/{filename}"

                # 处理同名冲突
                base_name = arcname
                counter = 1
                while arcname in zf.namelist():
                    name_part, ext = os.path.splitext(base_name)
                    arcname = f"{name_part}({counter}){ext}"
                    counter += 1

                zf.write(pdf_path, arcname)
                added += 1

        if added == 0:
            return JsonResponse({"code": 400, "msg": "该人员无已生成的PDF"})

        buffer.seek(0)

        # 4. 返回
        zip_filename = f"{person_name}_档案_{datetime.now().strftime('%Y%m%d')}.zip"
        resp = HttpResponse(buffer.read(), content_type="application/zip")
        resp["Content-Disposition"] = (
            f"attachment; filename*=UTF-8''{quote(zip_filename)}"
        )
        return resp

    except Exception as e:
        logger.error(f"打包下载失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
