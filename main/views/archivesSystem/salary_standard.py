"""
工资标准维护
"""
import json
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.utils import _get_conn
from main.utils.decorators import admin_required

logger = logging.getLogger(__name__)


@login_required
@admin_required
def page(request):
    return render(request, "archivesSystem/salary_standard.html")


@login_required
@admin_required
def list_api(request):
    """标准列表"""
    rylb = request.GET.get("rylb", "")
    lb = request.GET.get("lb", "")
    sj = request.GET.get("sj", "")
    bz = request.GET.get("bz", "")
    keyword = request.GET.get("keyword", "")
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 30))

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        where = "WHERE 1=1"
        params = []

        if rylb:
            where += " AND RYLB = ?"
            params.append(rylb)
        if lb:
            where += " AND LB = ?"
            params.append(lb)
        if sj:
            where += " AND SJ = ?"
            params.append(int(sj))
        if bz:
            where += " AND ISNULL(bz,'') = ?"
            params.append(bz)
        if keyword:
            where += " AND (CAST(DC AS VARCHAR) LIKE ? OR CAST(JE AS VARCHAR) LIKE ?)"
            kw = f"%{keyword}%"
            params.extend([kw, kw])

        cursor.execute(f"SELECT COUNT(*) FROM Z_GZBZ {where}", params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor.execute(f"""
            SELECT id, RYLB, LB, SJ, DC, JE, bz
            FROM Z_GZBZ {where}
            ORDER BY RYLB, LB, SJ DESC, DC
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """, params)
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn: conn.close()


@login_required
@admin_required
def filters_api(request):
    """筛选下拉选项"""
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT RYLB FROM Z_GZBZ WHERE RYLB IS NOT NULL AND RYLB != '' ORDER BY RYLB")
        rylb = [r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT LB FROM Z_GZBZ WHERE LB IS NOT NULL AND LB != '' ORDER BY LB")
        lb = [r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT SJ FROM Z_GZBZ WHERE SJ IS NOT NULL AND SJ != '' ORDER BY SJ DESC")
        sj = [r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT ISNULL(bz,'') FROM Z_GZBZ ORDER BY ISNULL(bz,'')")
        bz = [r[0] for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": {"rylb": rylb, "lb": lb, "sj": sj, "bz": bz}})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn: conn.close()

@login_required
@admin_required
@csrf_exempt
def save_api(request):
    """新增/更新标准"""
    if request.method != "POST": return JsonResponse({"code": 405})
    try: data = json.loads(request.body)
    except: return JsonResponse({"code": 400})

    rid = data.get("id")
    rylb = data.get("RYLB", "")
    lb = data.get("LB", "")
    sj = data.get("SJ", "")
    dc = data.get("DC", "")
    je = data.get("JE", "")
    bz = data.get("bz", "")

    if not rylb or not lb or not sj or not dc or not je:
        return JsonResponse({"code": 400, "msg": "字段不能为空"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        if rid and int(rid) > 0:
            cursor.execute("UPDATE Z_GZBZ SET RYLB=?, LB=?, SJ=?, DC=?, JE=?, bz=? WHERE id=?",
                           (rylb, lb, int(sj), dc, int(je), bz, int(rid)))
        else:
            cursor.execute("SELECT ISNULL(MAX(id),0)+1 FROM Z_GZBZ")
            new_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO Z_GZBZ (id, RYLB, LB, SJ, DC, JE, bz) VALUES (?,?,?,?,?,?,?)",
                           (new_id, rylb, lb, int(sj), dc, int(je), bz))
        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        if conn: conn.rollback()
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn: conn.close()



@login_required
@admin_required
@csrf_exempt
def delete_api(request):
    """删除标准"""
    if request.method != "POST": return JsonResponse({"code": 405})
    try: data = json.loads(request.body)
    except: return JsonResponse({"code": 400})
    ids = data.get("ids", [])
    if not ids: return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(ids))
        cursor.execute(f"DELETE FROM Z_GZBZ WHERE id IN ({placeholders})", [int(x) for x in ids])
        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "删除成功"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn: conn.close()
