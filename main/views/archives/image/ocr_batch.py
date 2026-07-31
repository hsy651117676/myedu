"""
OCR 批量扫描 - API 接口
纯调用 ocr_service，不写业务逻辑
"""

import json
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt

from main.utils.decorators import archive_perm_required
from .ocr_service import (
    get_cached_unit_persons,
    get_cached_arch_info,
    ocr_first_page,
    process_one,
    split_files,
    generate_preview_pdf,
    generate_existing_pdf,
    batch_write,
)

logger = logging.getLogger(__name__)

AUTO_SCAN_DIR = "/mnt/work/AutoScan"


def _get_channel_dir(channel):
    """获取通道对应的扫描目录"""
    channel = str(channel).strip()
    if not channel:
        channel = "01"
    return f"{AUTO_SCAN_DIR}_{channel}"


@login_required
@archive_perm_required
def page(request):
    return render(request, "archives/image/ocr_batch.html")


# ==================== 下拉数据 ====================


@login_required
def unit_list_api(request):
    from main.utils import _get_conn

    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("{CALL z_selectname(0, '')}")
    cols = [c[0] for c in cursor.description]
    rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return JsonResponse({"code": 0, "data": rows})


@login_required
def category_tree_api(request):
    from main.utils import _get_conn

    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT FL, JBBH, FLSM, PID FROM CATETREE ORDER BY PID, FL")
    rows = [
        {"fl": r[0], "jbbh": r[1], "flsm": r[2], "pid": r[3]} for r in cursor.fetchall()
    ]
    cursor.close()
    conn.close()
    top = [r for r in rows if r["pid"] == -1]
    children = {}
    for r in rows:
        if r["pid"] > 0:
            children.setdefault(r["pid"], []).append(r)
    return JsonResponse({"code": 0, "top": top, "children": children})


# ==================== 人员与档案（带缓存） ====================


@login_required
def unit_persons_api(request):
    unit_id = request.GET.get("unit_id", "")
    if not unit_id:
        return JsonResponse({"code": 400, "msg": "缺少单位ID"})
    persons = get_cached_unit_persons(int(unit_id))
    return JsonResponse({"code": 0, "data": persons})


@login_required
def existing_count_api(request):
    rsids = request.GET.get("rsids", "")
    fl = request.GET.get("fl", "")
    fyear = request.GET.get("fyear", "")
    fmonth = request.GET.get("fmonth", "")
    fday = request.GET.get("fday", "")
    ys = request.GET.get("ys", "")
    cltm = request.GET.get("cltm", "")

    if not all([rsids, fl, fyear, ys]):
        return JsonResponse({"code": 400, "msg": "参数不完整"})

    ids = [x.strip() for x in rsids.split(",") if x.strip()]
    from main.utils import _get_conn

    conn = _get_conn()
    cursor = conn.cursor()
    result = {}
    for rsid in ids:
        cursor.execute(
            "SELECT XM, IDCARD, CSNY, WORKTIME FROM RS_INFO WHERE RSID=?", (int(rsid),)
        )
        info_row = cursor.fetchone()
        person_info = {
            "name": info_row[0] if info_row else "",
            "idcard": info_row[1] if info_row else "",
            "csny": info_row[2] if info_row else "",
            "worktime": info_row[3] if info_row else "",
        }

        arch = get_cached_arch_info(rsid, fl, fyear, fmonth, fday, ys, cltm)
        arch["person"] = person_info
        result[rsid] = arch

    cursor.close()
    conn.close()
    return JsonResponse({"code": 0, "data": result})


# ==================== 文件结构检测 ====================


@login_required
def detect_structure_api(request):
    """检测通道目录的文件结构"""
    channel = request.GET.get("channel", "01")
    scan_dir = _get_channel_dir(channel)

    if not os.path.exists(scan_dir):
        return JsonResponse(
            {
                "code": 0,
                "data": {
                    "structure": "empty",
                    "count": 0,
                    "folder_count": 0,
                    "file_count": 0,
                },
            }
        )

    items = os.listdir(scan_dir)
    folders = [i for i in items if os.path.isdir(os.path.join(scan_dir, i))]
    files = [
        i
        for i in items
        if os.path.isfile(os.path.join(scan_dir, i))
        and i.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if folders and not files:
        structure = "folder"
        count = len(folders)
    elif files and not folders:
        structure = "flat"
        count = len(files)
    elif folders and files:
        structure = "mixed"
        count = len(files) + len(folders)
    else:
        structure = "empty"
        count = 0

    return JsonResponse(
        {
            "code": 0,
            "data": {
                "structure": structure,
                "count": count,
                "folder_count": len(folders),
                "file_count": len(files),
            },
        }
    )


# ==================== OCR 识别 ====================


@login_required
def ocr_verify_api(request):
    """批量 OCR 识别（SSE 流式返回）"""
    pages_per_person = int(request.GET.get("pages", "1"))
    unit_id = int(request.GET.get("unit_id", "0"))
    channel = request.GET.get("channel", "01")

    scan_dir = _get_channel_dir(channel)

    if not os.path.exists(scan_dir):
        return JsonResponse({"code": 400, "msg": f"通道目录不存在: {scan_dir}"})

    person_list = get_cached_unit_persons(unit_id)

    def generate():
        groups = split_files(scan_dir, pages_per_person)
        total = len(groups)
        matched_rsids = set()

        # 先发总数
        yield f"data: {json.dumps({'type': 'total', 'total': total})}\n\n"

        done_count = 0

        with ThreadPoolExecutor(max_workers=32) as executor:
            futures = {}
            for i, g in enumerate(groups):
                futures[
                    executor.submit(
                        process_one, i, g, scan_dir, person_list, matched_rsids
                    )
                ] = i

            for future in as_completed(futures):
                idx, data = future.result()
                done_count += 1

                if data.get("matched_person"):
                    matched_rsids.add(data["matched_person"]["RSID"])

                yield f"data: {json.dumps({'type': 'result', 'item': data, 'done': done_count, 'total': total})}\n\n"

        # 全部完成
        unmatched = [p for p in person_list if p["RSID"] not in matched_rsids]
        yield f"data: {json.dumps({'type': 'all_done', 'unmatched_persons': unmatched})}\n\n"

    response = StreamingHttpResponse(generate(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@login_required
def retry_ocr_api(request):
    """单张图片重新 OCR"""
    file_name = request.GET.get("file", "")
    channel = request.GET.get("channel", "01")
    scan_dir = _get_channel_dir(channel)
    file_path = os.path.join(scan_dir, file_name)

    if not os.path.exists(file_path):
        return JsonResponse({"code": 400, "msg": "文件不存在"})

    full_text, ocr_info = ocr_first_page(file_path)

    return JsonResponse(
        {
            "code": 0,
            "data": {
                "ocr_text": full_text[:500],
                "ocr_name": ocr_info.get("name") or "",
                "ocr_csny": ocr_info.get("csny") or "",
                "ocr_worktime": ocr_info.get("worktime") or "",
                "ocr_idcard": ocr_info.get("idcard") or "",
            },
        }
    )


# ==================== PDF 预览 ====================


@login_required
def preview_pdf_api(request):
    files_json = request.GET.get("files", "")
    rsid = request.GET.get("rsid", "")
    archid = request.GET.get("archid", "")
    channel = request.GET.get("channel", "01")

    if rsid and archid:
        fl = request.GET.get("fl", "")
        pdf_bytes = generate_existing_pdf(rsid, fl, archid)
    else:
        files = json.loads(files_json) if files_json else []
        scan_dir = _get_channel_dir(channel)
        pdf_bytes = generate_preview_pdf(scan_dir, files)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="preview.pdf"'
    return response


# ==================== 写入 ====================


@login_required
@csrf_exempt
def single_write_api(request):
    """单条写入"""
    if request.method != "POST":
        return JsonResponse({"code": 405})

    data = json.loads(request.body)
    item = data.get("item", {})
    fl = int(data.get("fl", 0))
    cltm = data.get("cltm", "")
    fyear = int(data.get("fyear", 0))
    fmonth = int(data.get("fmonth") or 0)
    fday = int(data.get("fday") or 0)
    ys = int(data.get("ys", 0))
    channel = data.get("channel", "01")

    scan_dir = _get_channel_dir(channel)
    item["auto_scan_dir"] = scan_dir
    item["match_by"] = item.get("match_by", "")

    results = batch_write([item], fl, cltm, fyear, fmonth, fday, ys)

    if results and results[0]["status"] == "success":
        return JsonResponse({"code": 0, "success": True})
    else:
        msg = results[0].get("msg", "写入失败") if results else "未知错误"
        return JsonResponse({"code": 1, "success": False, "msg": msg})


@login_required
@csrf_exempt
def batch_write_api(request):
    """批量写入"""
    if request.method != "POST":
        return JsonResponse({"code": 405})

    data = json.loads(request.body)
    items = data.get("items", [])
    fl = int(data.get("fl", 0))
    cltm = data.get("cltm", "")
    fyear = int(data.get("fyear", 0))
    fmonth = int(data.get("fmonth") or 0)
    fday = int(data.get("fday") or 0)
    ys = int(data.get("ys", 0))
    channel = data.get("channel", "01")

    scan_dir = _get_channel_dir(channel)

    for item in items:
        item["auto_scan_dir"] = scan_dir
        item["match_by"] = item.get("match_by", "")

    results = batch_write(items, fl, cltm, fyear, fmonth, fday, ys)

    success = [r for r in results if r["status"] == "success"]
    errors = [r for r in results if r["status"] == "error"]

    return JsonResponse(
        {
            "code": 0,
            "msg": f"成功 {len(success)} 人，失败 {len(errors)} 人",
            "success": len(success),
            "errors": len(errors),
            "data": results,
        }
    )
