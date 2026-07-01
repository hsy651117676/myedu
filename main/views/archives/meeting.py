"""
meeting.py
党组会认定
"""

import hashlib
import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from main.utils import _get_conn
from main.utils.decorators import archive_perm_required

logger = logging.getLogger(__name__)


@login_required
@archive_perm_required
def person_meeting_view(request):
    return render(request, "archives/person_meeting.html")


@login_required
@archive_perm_required
def person_meeting_form_view(request):
    return render(request, "archives/person_meeting_form.html")


@login_required
def batch_list_api(request):
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT batch_id, batch_name, batch_date, leader, editable FROM z_meeting_batch ORDER BY batch_date DESC"
        )
        data = [
            {
                "batch_id": r[0],
                "batch_name": r[1],
                "batch_date": r[2],
                "leader": r[3],
                "editable": r[4],
            }
            for r in cursor.fetchall()
        ]
        cursor.close()
        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def meeting_list_api(request):
    batch_id = request.GET.get("batch_id", "")
    name = request.GET.get("name", "")
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 30))

    cache_key = f"meeting:list:{hashlib.md5(f'{batch_id}{name}{page}{page_size}'.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse(
            {"code": 0, "data": cached.get("data", []), "total": cached.get("total", 0)}
        )

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        where = "WHERE 1=1"
        params = []

        if batch_id == "null":
            where += " AND z.batch_id IS NULL"
        elif batch_id:
            where += " AND z.batch_id = ?"
            params.append(int(batch_id))
        if name:
            where += " AND z.rsid IN (SELECT RSID FROM RS_INFO WHERE XM LIKE ?)"
            params.append(f"%{name}%")

        cursor.execute(f"SELECT COUNT(*) FROM z_meeting z {where}", params)
        row = cursor.fetchone()
        total = row[0] if row else 0

        offset = (page - 1) * page_size
        cursor.execute(
            f"""
            SELECT z.*, 
                   (SELECT XM FROM RS_INFO WHERE RSID = z.rsid) AS XM,
                   (SELECT batch_name FROM z_meeting_batch WHERE batch_id = z.batch_id) AS batch_name,
                   (SELECT editable FROM z_meeting_batch WHERE batch_id = z.batch_id) AS editable
            FROM z_meeting z
            {where}
            ORDER BY z.rsid
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """,
            params,
        )
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()

        result = {"data": rows, "total": total}
        cache.set(cache_key, result, 1800)
        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def meeting_detail_api(request):
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT z.*, r.XM, b.batch_name, b.editable, b.batch_date, b.leader, b.applicant, b.batch_status
            FROM z_meeting z
            LEFT JOIN z_meeting_batch b ON z.batch_id = b.batch_id
            LEFT JOIN RS_INFO r ON z.rsid = r.RSID
            WHERE z.rsid = ?
                    """,
            (int(rsid),),
        )
        cols = [c[0] for c in cursor.description]
        row = cursor.fetchone()
        data = dict(zip(cols, row)) if row else {}
        cursor.close()
        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
@csrf_exempt
def meeting_save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"code": 400})
    rsid = data.get("rsid")
    if not rsid:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT z.batch_id, b.editable FROM z_meeting z LEFT JOIN z_meeting_batch b ON z.batch_id=b.batch_id WHERE z.rsid=?",
            (int(rsid),),
        )
        row = cursor.fetchone()
        if row and row[1] is not None and not row[1]:
            cursor.close()
            return JsonResponse({"code": 400, "msg": "已备案记录不可修改"})

        fields = [
            "school_name",
            "identification_type",
            "birth_summary",
            "birth_material_name",
            "birth_material_time",
            "birth_material_date",
            "birth_alteration",
            "birth_decision_date",
            "work_summary",
            "work_material_name",
            "work_material_time",
            "work_material_date",
            "work_alteration",
            "work_decision_date",
            "party_join_time",
            "party_material_date",
            "party_decision_date",
            "meeting_type",
            "remark",
        ]
        values = [data.get(f, "") for f in fields]

        if row:
            set_clause = ",".join([f"{f}=?" for f in fields])
            cursor.execute(
                f"UPDATE z_meeting SET {set_clause} WHERE rsid=?", values + [int(rsid)]
            )
        else:
            placeholders = ",".join(["?"] * len(fields))
            cursor.execute(
                f"INSERT INTO z_meeting (rsid,{','.join(fields)}) VALUES (?,{placeholders})",
                [int(rsid)] + values,
            )
        conn.commit()
        cursor.close()
        cache.delete_pattern("meeting:list:*")
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
def meeting_extract_api(request):
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                r.JOBUNIT AS school_name,
                z.cssj AS birth_summary,
                r.CSNY AS birth_material_time,
                z.cssj2C AS birth_material_name,
                z.cssj2D AS birth_material_date,
                r.CSNY AS birth_decision_date,
                z.cjgz AS work_summary,
                r.WORKTIME AS work_material_time,
                z.cjgz3C AS work_material_name,
                z.cjgz3D AS work_material_date,
                r.WORKTIME AS work_decision_date,
                r.JOINTIME AS party_join_time,
                z.rdsj6D AS party_material_date,
                r.JOINTIME AS party_decision_date
            FROM RS_INFO r
            LEFT JOIN YW_ZXSHDJ z ON r.RSID = z.RSID
            WHERE r.RSID = ?
        """,
            (int(rsid),),
        )
        cols = [c[0] for c in cursor.description]
        row = cursor.fetchone()
        extracted = dict(zip(cols, row)) if row else {}

        cursor.execute("SELECT * FROM z_meeting WHERE rsid=?", (int(rsid),))
        existing_cols = [c[0] for c in cursor.description]
        existing_row = cursor.fetchone()
        existing = dict(zip(existing_cols, existing_row)) if existing_row else {}

        for key in extracted:
            val = extracted[key]
            if val and isinstance(val, str) and len(str(val).strip()) > 2:
                existing[key] = val

        existing.pop("rsid", None)
        cursor.close()
        return JsonResponse({"code": 0, "data": existing})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
@csrf_exempt
def meeting_delete_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"code": 400})
    rsid = data.get("rsid")
    if not rsid:
        return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT b.editable FROM z_meeting z LEFT JOIN z_meeting_batch b ON z.batch_id=b.batch_id WHERE z.rsid=?",
            (int(rsid),),
        )
        row = cursor.fetchone()
        if row and row[0] is not None and not row[0]:
            cursor.close()
            return JsonResponse({"code": 400, "msg": "已备案记录不可删除"})
        cursor.execute("DELETE FROM z_meeting WHERE rsid=?", (int(rsid),))
        conn.commit()
        cursor.close()
        cache.delete_pattern("meeting:list:*")
        return JsonResponse({"code": 0, "msg": "删除成功"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
