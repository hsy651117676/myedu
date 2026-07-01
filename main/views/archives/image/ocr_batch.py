"""
OCR 批量扫描 - API 接口
纯调用 ocr_service，不写业务逻辑
"""

import json
import os
import logging

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from main.utils.decorators import archive_perm_required
from .ocr_service import (
    get_cached_unit_persons,
    get_cached_arch_info,
    ocr_verify,
    generate_preview_pdf,
    generate_existing_pdf,
    batch_write,
)

logger = logging.getLogger(__name__)

AUTO_SCAN_DIR = "/mnt/work/AutoScan"


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


# ==================== OCR ====================


@login_required
def ocr_verify_api(request):
    pages_per_person = int(request.GET.get("pages", "1"))
    unit_id = int(request.GET.get("unit_id", "0"))

    if not os.path.exists(AUTO_SCAN_DIR):
        return JsonResponse({"code": 400, "msg": "AutoScan 目录不存在"})

    person_list = get_cached_unit_persons(unit_id)
    results = ocr_verify(AUTO_SCAN_DIR, pages_per_person, person_list)

    matched = sum(1 for r in results if r["match_status"] == "matched")
    conflict = sum(1 for r in results if r["match_status"] == "conflict")
    not_found = sum(1 for r in results if r["match_status"] == "not_found")

    matched_rsids = {
        r["matched_person"]["RSID"] for r in results if r["matched_person"]
    }
    unmatched_persons = [p for p in person_list if p["RSID"] not in matched_rsids]

    return JsonResponse(
        {
            "code": 0,
            "data": {
                "items": results,
                "stats": {
                    "matched": matched,
                    "conflict": conflict,
                    "not_found": not_found,
                },
                "unmatched_persons": unmatched_persons,
                "total_files": sum(len(r["files"]) for r in results),
            },
        }
    )


# ==================== PDF 预览 ====================


@login_required
def preview_pdf_api(request):
    files_json = request.GET.get("files", "")
    rsid = request.GET.get("rsid", "")
    archid = request.GET.get("archid", "")

    if rsid and archid:
        fl = request.GET.get("fl", "")
        pdf_bytes = generate_existing_pdf(rsid, fl, archid)
    else:
        files = json.loads(files_json) if files_json else []
        pdf_bytes = generate_preview_pdf(AUTO_SCAN_DIR, files)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="preview.pdf"'
    return response


# ==================== 写入 ====================


@login_required
@csrf_exempt
def batch_write_api(request):
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

    for item in items:
        item["auto_scan_dir"] = AUTO_SCAN_DIR

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
