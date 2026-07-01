"""
档案人员调转
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
    return render(request, "archivesSystem/archive_transfer.html")


@login_required
@admin_required
def person_detail_api(request):
    """获取人员当前信息"""
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少rsid"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT RS_INFO.RSID, RS_INFO.XM, RS_INFO.RYBH,
                   DEPART.BMMC, DEPART.BM,
                   YW_INFO.GH, YW_INFO.CH
            FROM RS_INFO
            LEFT JOIN USERS_DEPARTMENT ON RS_INFO.RSID = USERS_DEPARTMENT.RSID
            LEFT JOIN DEPART ON USERS_DEPARTMENT.DEPARTMENTID = DEPART.BM
            LEFT JOIN YW_INFO ON RS_INFO.RSID = YW_INFO.RSID
            WHERE RS_INFO.RSID = ?
        """, (int(rsid),))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return JsonResponse({"code": 404, "msg": "人员不存在"})

        cols = [c[0] for c in cursor.description]
        person = dict(zip(cols, row))

        # 姓氏编号
        xs = person.get("XM", "")[0] if person.get("XM") else ""
        xs_id = None
        if xs:
            cursor.execute("SELECT id FROM Z_XSBM WHERE xs LIKE ?", (xs + '%',))
            xs_row = cursor.fetchone()
            if xs_row:
                xs_id = xs_row[0]

        cursor.close()
        return JsonResponse({
            "code": 0,
            "data": {
                "rsid": person["RSID"],
                "xm": person["XM"],
                "rybh": person["RYBH"],
                "bmmc": person["BMMC"],
                "bm": person["BM"],
                "gh": person.get("GH") or "",
                "ch": person.get("CH") or "",
                "xs": xs,
                "xs_id": xs_id,
            }
        })
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@admin_required
def xs_table_api(request):
    """姓氏参考表：当前姓氏上下10行"""
    xs_id = request.GET.get("xs_id", "")
    if not xs_id:
        return JsonResponse({"code": 400, "msg": "缺少xs_id"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        _id = int(xs_id)
        low, high = _id - 10, _id + 10
        cursor.execute(
            "SELECT id, xs, jybm FROM Z_XSBM WHERE id BETWEEN ? AND ? ORDER BY id",
            (low, high)
        )
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows, "current_id": _id})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()

@login_required
@admin_required
def same_xs_list_api(request):
    """目标单位同姓人员列表，无同姓则显示该单位前10条"""
    new_bm = request.GET.get("new_bm", "")
    xs = request.GET.get("xs", "")
    if not new_bm:
        return JsonResponse({"code": 400, "msg": "缺少参数"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if xs:
            cursor.execute("""
                SELECT ROW_NUMBER() OVER(ORDER BY RS_INFO.RYBH) AS 序号,
                       RS_INFO.XM AS 姓名,
                       RS_INFO.RYBH AS 档案编号,
                       YW_INFO.GH AS 柜号,
                       YW_INFO.CH AS 层号
                FROM RS_INFO
                LEFT JOIN USERS_DEPARTMENT ON RS_INFO.RSID = USERS_DEPARTMENT.RSID
                LEFT JOIN YW_INFO ON RS_INFO.RSID = YW_INFO.RSID
                WHERE USERS_DEPARTMENT.DEPARTMENTID = ?
                  AND RS_INFO.XM LIKE ?
                ORDER BY RS_INFO.RYBH
            """, (new_bm, xs + '%'))
            cols = [c[0] for c in cursor.description]
            rows = [dict(zip(cols, r)) for r in cursor.fetchall()]

            if rows:
                cursor.close()
                return JsonResponse({"code": 0, "data": rows, "hasSameXs": True})

        # 无同姓人员，显示该单位前10条
        cursor.execute("""
            SELECT TOP 10
                   ROW_NUMBER() OVER(ORDER BY RS_INFO.RYBH) AS 序号,
                   RS_INFO.XM AS 姓名,
                   RS_INFO.RYBH AS 档案编号,
                   YW_INFO.GH AS 柜号,
                   YW_INFO.CH AS 层号
            FROM RS_INFO
            LEFT JOIN USERS_DEPARTMENT ON RS_INFO.RSID = USERS_DEPARTMENT.RSID
            LEFT JOIN YW_INFO ON RS_INFO.RSID = YW_INFO.RSID
            WHERE USERS_DEPARTMENT.DEPARTMENTID = ?
            ORDER BY RS_INFO.RYBH
        """, (new_bm,))
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows, "hasSameXs": False})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()

@login_required
@admin_required
@csrf_exempt
def save_api(request):
    """保存调转"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400, "msg": "参数格式错误"})

    rsid = data.get("rsid")
    new_rybh = str(data.get("new_rybh", "")).strip()
    new_bm = str(data.get("new_bm", "")).strip()
    gh = str(data.get("gh", "")).strip()
    ch = str(data.get("ch", "")).strip()

    if not rsid or not new_rybh or not new_bm:
        return JsonResponse({"code": 400, "msg": "参数不完整"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute("UPDATE RS_INFO SET RYBH=? WHERE RSID=?", (new_rybh, int(rsid)))
        cursor.execute(
            "UPDATE USERS_DEPARTMENT SET DEPARTMENTID=? WHERE RSID=?",
            (new_bm, int(rsid))
        )
        cursor.execute("SELECT COUNT(*) FROM YW_INFO WHERE RSID=?", (int(rsid),))
        if cursor.fetchone()[0] > 0:
            cursor.execute(
                "UPDATE YW_INFO SET GH=?, CH=?, DABH=? WHERE RSID=?",
                (gh, ch, new_rybh, int(rsid))
            )
        else:
            cursor.execute(
                "INSERT INTO YW_INFO (RSID, GH, CH, DABH) VALUES (?, ?, ?, ?)",
                (int(rsid), gh, ch, new_rybh)
            )

        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "调转成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
