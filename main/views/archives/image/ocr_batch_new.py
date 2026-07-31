"""
OCR 批量扫描并建目录 - API 接口
支持：按人分文件夹 / 平铺文件
写入时自动建 RS_ARCHINFO（XH 按日期排序）+ RS_DESCRIPT + 加密存盘
查重：同年月日+同页数唯一匹配直接返回，多条时材料名称模糊区分
"""

import json
import os
import logging

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from concurrent.futures import ThreadPoolExecutor, as_completed

from main.utils.decorators import archive_perm_required, _is_admin
from .ocr_service import (
    get_cached_unit_persons,
    get_cached_arch_info,
    ocr_first_page,
    match_person,
    generate_preview_pdf,
    generate_existing_pdf,
    batch_write as bw_write,
)
from main.utils import _get_conn, query_dict, execute_sql

logger = logging.getLogger(__name__)

AUTO_SCAN_DIR = "/mnt/work/AutoScan"


@login_required
@archive_perm_required
def page(request):
    return render(request, "archives/image/ocr_batch_new.html")


@login_required
def unit_list_api(request):
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("{CALL z_selectname(0, '')}")
    cols = [c[0] for c in cursor.description]
    rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
    cursor.close()
    conn.close()

    if not _is_admin(request):
        archive_user = request.session.get("archive_user", {})
        depart_id = int(archive_user.get("depart_id", 0))
        rows = [r for r in rows if r.get("序号") == depart_id]

    return JsonResponse({"code": 0, "data": rows})


@login_required
def category_tree_api(request):
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


@login_required
def unit_persons_api(request):
    unit_id = request.GET.get("unit_id", "")
    if not unit_id:
        return JsonResponse({"code": 400, "msg": "缺少单位ID"})

    if not _is_admin(request):
        archive_user = request.session.get("archive_user", {})
        allowed_depart = str(archive_user.get("depart_id", ""))
        if unit_id != allowed_depart:
            return JsonResponse({"code": 403, "msg": "无权访问其他单位"})

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
        arch = get_cached_arch_info(
            rsid, int(fl), int(fyear), fmonth, fday, int(ys), cltm
        )
        arch["person"] = person_info
        result[rsid] = arch
    cursor.close()
    conn.close()
    return JsonResponse({"code": 0, "data": result})


@login_required
def detect_structure_api(request):
    if not os.path.exists(AUTO_SCAN_DIR):
        return JsonResponse({"code": 400, "msg": "AutoScan 目录不存在"})

    dirs = [
        d
        for d in os.listdir(AUTO_SCAN_DIR)
        if os.path.isdir(os.path.join(AUTO_SCAN_DIR, d))
        and d != "_processed"
        and not d.startswith(".")
    ]
    files = [
        f
        for f in os.listdir(AUTO_SCAN_DIR)
        if os.path.isfile(os.path.join(AUTO_SCAN_DIR, f))
        and f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if dirs and not files:
        return JsonResponse(
            {
                "code": 0,
                "structure": "folder",
                "folders": sorted(dirs),
                "count": len(dirs),
            }
        )
    elif files and not dirs:
        return JsonResponse(
            {
                "code": 0,
                "structure": "flat",
                "files": sorted(files),
                "count": len(files),
            }
        )
    elif dirs and files:
        return JsonResponse(
            {
                "code": 0,
                "structure": "mixed",
                "folders": sorted(dirs),
                "files": sorted(files),
                "folder_count": len(dirs),
                "file_count": len(files),
            }
        )
    else:
        return JsonResponse({"code": 0, "structure": "empty"})


@login_required
def ocr_verify_api(request):
    pages_per_person = int(request.GET.get("pages", "1"))
    unit_id = int(request.GET.get("unit_id", "0"))

    if not os.path.exists(AUTO_SCAN_DIR):
        return JsonResponse({"code": 400, "msg": "AutoScan 目录不存在"})

    person_list = get_cached_unit_persons(unit_id)

    def generate():
        dirs = sorted(
            [
                d
                for d in os.listdir(AUTO_SCAN_DIR)
                if os.path.isdir(os.path.join(AUTO_SCAN_DIR, d))
                and d != "_processed"
                and not d.startswith(".")
            ]
        )
        files = sorted(
            [
                f
                for f in os.listdir(AUTO_SCAN_DIR)
                if os.path.isfile(os.path.join(AUTO_SCAN_DIR, f))
                and f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
        )

        if dirs and not files:
            yield from _verify_folders(dirs, person_list)
        elif files and not dirs:
            yield from _verify_flat(files, pages_per_person, person_list)
        else:
            yield f"data: {json.dumps({'type': 'error', 'msg': '文件结构异常，请检查AutoScan'}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(generate(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _is_standard_names(files):
    import re

    for f in files:
        if not re.match(r"^\d{3}\.JPG$", f, re.IGNORECASE):
            return False
    return True


def _verify_folders(dirs, person_list):
    matched_rsids = set()
    total = len(dirs)
    all_results = [None] * total

    yield f"data: {json.dumps({'type': 'total', 'total': total}, ensure_ascii=False)}\n\n"

    def process_one(idx, dirname):
        folder_path = os.path.join(AUTO_SCAN_DIR, dirname)
        imgs = sorted(
            [
                f
                for f in os.listdir(folder_path)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
        )
        if not imgs:
            return idx, None
        if not _is_standard_names(imgs):
            imgs.sort(key=lambda f: os.path.getctime(os.path.join(folder_path, f)))
        first_file = imgs[0]
        first_path = os.path.join(folder_path, first_file)
        full_text, ocr_info = ocr_first_page(first_path)
        ocr_info["folder_name"] = dirname
        match_result = match_person(ocr_info, person_list, matched_rsids)
        if not match_result["person"]:
            exact = [
                p
                for p in person_list
                if p["name"] == dirname and p["RSID"] not in matched_rsids
            ]
            if len(exact) == 1:
                match_result = {
                    "status": "conflict",
                    "person": exact[0],
                    "candidates": [],
                    "match_by": "文件夹名匹配(待确认)",
                }
        item = {
            "index": idx + 1,
            "files": [os.path.join(dirname, f) for f in imgs],
            "first_file": f"{dirname}/{first_file}",
            "last_file": f"{dirname}/{imgs[-1]}",
            "folder_name": dirname,
            "is_folder": True,
            "ocr_text": full_text[:500],
            "ocr_name": ocr_info.get("name") or "",
            "ocr_csny": ocr_info.get("csny") or "",
            "ocr_worktime": ocr_info.get("worktime") or "",
            "ocr_idcard": ocr_info.get("idcard") or "",
            "ocr_gender": ocr_info.get("gender") or "",
            "match_status": match_result["status"],
            "matched_person": match_result["person"],
            "candidates": match_result["candidates"],
            "match_by": match_result["match_by"],
        }
        return idx, item

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process_one, i, d): i for i, d in enumerate(dirs)}
        for future in as_completed(futures):
            idx, item = future.result()
            if item is None:
                continue
            if item["matched_person"]:
                matched_rsids.add(item["matched_person"]["RSID"])
            all_results[idx] = item
            done = sum(1 for r in all_results if r is not None)
            yield f"data: {json.dumps({'type': 'result', 'item': item, 'done': done, 'total': total}, ensure_ascii=False)}\n\n"

    unmatched = [p for p in person_list if p["RSID"] not in matched_rsids]
    yield f"data: {json.dumps({'type': 'all_done', 'unmatched_persons': unmatched}, ensure_ascii=False)}\n\n"


def _verify_flat(files, pages_per_person, person_list):
    files = sorted(files)
    groups = []
    for i in range(0, len(files), pages_per_person):
        group = files[i : i + pages_per_person]
        if len(group) == pages_per_person:
            groups.append(group)

    matched_rsids = set()
    total = len(groups)
    all_results = [None] * total

    yield f"data: {json.dumps({'type': 'total', 'total': total}, ensure_ascii=False)}\n\n"

    def process_one(idx, group):
        first_file = group[0]
        filepath = os.path.join(AUTO_SCAN_DIR, first_file)
        full_text, ocr_info = ocr_first_page(filepath)
        match_result = match_person(ocr_info, person_list, matched_rsids)
        return idx, match_result, full_text, ocr_info

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process_one, i, g): i for i, g in enumerate(groups)}
        for future in as_completed(futures):
            idx, match_result, full_text, ocr_info = future.result()
            if match_result["person"]:
                matched_rsids.add(match_result["person"]["RSID"])
            item = {
                "index": idx + 1,
                "files": groups[idx],
                "first_file": groups[idx][0],
                "last_file": groups[idx][-1],
                "folder_name": "",
                "is_folder": False,
                "ocr_text": full_text[:500],
                "ocr_name": ocr_info.get("name") or "",
                "ocr_csny": ocr_info.get("csny") or "",
                "ocr_worktime": ocr_info.get("worktime") or "",
                "ocr_idcard": ocr_info.get("idcard") or "",
                "ocr_gender": ocr_info.get("gender") or "",
                "match_status": match_result["status"],
                "matched_person": match_result["person"],
                "candidates": match_result["candidates"],
                "match_by": match_result["match_by"],
            }
            all_results[idx] = item
            done = sum(1 for r in all_results if r is not None)
            yield f"data: {json.dumps({'type': 'result', 'item': item, 'done': done, 'total': total}, ensure_ascii=False)}\n\n"

    unmatched = [p for p in person_list if p["RSID"] not in matched_rsids]
    yield f"data: {json.dumps({'type': 'all_done', 'unmatched_persons': unmatched}, ensure_ascii=False)}\n\n"


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


def find_existing_arch(rsid, fl, cltm, fyear, fmonth, fday, ys):
    rows = query_dict(
        "SELECT ARCHID, XH, CLTM FROM RS_ARCHINFO WHERE RSID=? AND FL=? AND FYEAR=? AND FMONTH=? AND FDAY=? AND YS=?",
        (rsid, fl, int(fyear), int(fmonth or 1), int(fday or 1), ys),
    )
    if len(rows) == 1:
        return rows[0]["ARCHID"], rows[0]["XH"], True
    if len(rows) > 1:
        for r in rows:
            if cltm and r["CLTM"] and (cltm in r["CLTM"] or r["CLTM"] in cltm):
                return r["ARCHID"], r["XH"], True
        return rows[0]["ARCHID"], rows[0]["XH"], True
    return None, None, False


def insert_archinfo_sorted(rsid, fl, cltm, fyear, fmonth, fday, ys, bz=""):
    rows = query_dict(
        "SELECT XH, FYEAR, FMONTH, FDAY FROM RS_ARCHINFO WHERE RSID=? AND FL=? ORDER BY FYEAR, FMONTH, FDAY, XH",
        (rsid, fl),
    )
    new_date = int(f"{int(fyear):04d}{int(fmonth or 1):02d}{int(fday or 1):02d}")
    insert_xh = 1
    for r in rows:
        cur_date = int(
            f"{int(r['FYEAR'] or 0):04d}{int(r['FMONTH'] or 1):02d}{int(r['FDAY'] or 1):02d}"
        )
        if new_date < cur_date:
            break
        insert_xh = r["XH"] + 1
    execute_sql(
        "UPDATE RS_ARCHINFO SET XH = XH + 1 WHERE RSID=? AND FL=? AND XH >= ?",
        (rsid, fl, insert_xh),
    )
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO RS_ARCHINFO (RSID, FL, CLTM, BZ, FYEAR, FMONTH, FDAY, YS, XH, ADDTIME) VALUES (?,?,?,?,?,?,?,?,?,GETDATE())",
        (
            rsid,
            fl,
            cltm,
            bz,
            int(fyear),
            int(fmonth or 1),
            int(fday or 1),
            ys,
            insert_xh,
        ),
    )
    conn.commit()
    cursor.execute("SELECT @@IDENTITY AS ARCHID")
    archid = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return archid, insert_xh


@login_required
@csrf_exempt
def single_write_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    data = json.loads(request.body)
    item = data.get("item", {})
    rsid = item.get("rsid")
    files = item.get("files", [])
    fl = int(data.get("fl", 0))
    cltm = data.get("cltm", "")
    bz = data.get("bz", "")
    fyear = int(data.get("fyear", 0))
    fmonth = int(data.get("fmonth") or 0)
    fday = int(data.get("fday") or 0)
    ys = int(data.get("ys", 0))
    try:
        archid, xh, existed = find_existing_arch(
            rsid, fl, cltm, fyear, fmonth, fday, ys
        )
        if not existed:
            archid, xh = insert_archinfo_sorted(
                rsid, fl, cltm, fyear, fmonth, fday, ys, bz
            )
    except Exception as e:
        return JsonResponse({"code": 500, "msg": f"建目录失败: {e}", "success": False})
    item["archid"] = archid
    item["auto_scan_dir"] = AUTO_SCAN_DIR
    results = bw_write([item], fl, cltm, fyear, fmonth, fday, ys)
    success = results[0] if results else {}
    return JsonResponse(
        {
            "code": 0,
            "msg": "扫描件已更新" if existed else "目录已建，扫描件已写入",
            "success": success.get("status") == "success",
        }
    )


@login_required
@csrf_exempt
def batch_write_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    data = json.loads(request.body)
    items = data.get("items", [])
    fl = int(data.get("fl", 0))
    cltm = data.get("cltm", "")
    bz = data.get("bz", "")
    fyear = int(data.get("fyear", 0))
    fmonth = int(data.get("fmonth") or 0)
    fday = int(data.get("fday") or 0)
    ys = int(data.get("ys", 0))
    for item in items:
        try:
            archid, xh, existed = find_existing_arch(
                item["rsid"], fl, cltm, fyear, fmonth, fday, ys
            )
            if not existed:
                archid, xh = insert_archinfo_sorted(
                    item["rsid"], fl, cltm, fyear, fmonth, fday, ys, bz
                )
            item["archid"] = archid
        except Exception as e:
            item["archid"] = None
            item["_error"] = str(e)
    valid_items = [it for it in items if it.get("archid")]
    for it in valid_items:
        it["auto_scan_dir"] = AUTO_SCAN_DIR
    results = bw_write(valid_items, fl, cltm, fyear, fmonth, fday, ys)
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
