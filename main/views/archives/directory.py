from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.db_utils import _get_conn
import json
import logging

logger = logging.getLogger(__name__)


def _get_yhbh(request):
    try:
        return request.user.profile.yhbh or 0
    except:
        return 0


@login_required
def person_directory_view(request):
    return render(request, "archives/person_directory.html")


@login_required
def directory_tree_api(request):
    """获取分类树"""
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT FL, JBBH + '、' + FLSM AS name, PID FROM CATETREE WHERE PID=-1 ORDER BY FL"
        )
        rows = [{"fl": r[0], "name": r[1], "pid": r[2]} for r in cursor.fetchall()]

        # 子类
        cursor.execute(
            "SELECT FL, JBBH + '、' + FLSM AS name, PID FROM CATETREE WHERE PID=4 ORDER BY FL"
        )
        sub4 = [{"fl": r[0], "name": r[1]} for r in cursor.fetchall()]

        cursor.execute(
            "SELECT FL, JBBH + '、' + FLSM AS name, PID FROM CATETREE WHERE PID=9 ORDER BY FL"
        )
        sub9 = [{"fl": r[0], "name": r[1]} for r in cursor.fetchall()]

        cursor.close()
        return JsonResponse({"code": 0, "tree": rows, "sub4": sub4, "sub9": sub9})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def directory_list_api(request):
    """获取档案目录列表"""
    rsid = request.GET.get("rsid", "")
    fl = request.GET.get("fl", "1")
    if not rsid:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ARCHID, RSID, XH, CLTM, FYEAR, FMONTH, FDAY, YS, BZ, FL
            FROM RS_ARCHINFO WHERE RSID=? AND FL=? ORDER BY XH
        """,
            (int(rsid), int(fl)),
        )
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@csrf_exempt
def directory_save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    rsid = data.get("rsid")
    batch = data.get("batch", [])
    single_action = data.get("action", "")
    single_row = data.get("row", {})

    if not rsid:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # 如果有批量操作
        if batch:
            for item in batch:
                action = item.get("action", "UPDATE")
                row = item.get("row", {})

                if action == "UPDATE":
                    cursor.execute(
                        "UPDATE RS_ARCHINFO SET CLTM=?, FYEAR=?, FMONTH=?, FDAY=?, YS=?, BZ=? WHERE ARCHID=?",
                        (
                            row.get("CLTM", ""),
                            row.get("FYEAR", ""),
                            row.get("FMONTH", ""),
                            row.get("FDAY", ""),
                            row.get("YS", ""),
                            row.get("BZ", ""),
                            row.get("ARCHID"),
                        ),
                    )
                elif action == "DELETE":
                    cursor.execute(
                        "SELECT FL, XH FROM RS_ARCHINFO WHERE ARCHID=?",
                        (row.get("ARCHID"),),
                    )
                    del_info = cursor.fetchone()
                    if del_info:
                        fl, xh = del_info
                        cursor.execute(
                            "DELETE FROM RS_ARCHINFO WHERE ARCHID=?",
                            (row.get("ARCHID"),),
                        )
                        cursor.execute(
                            "UPDATE RS_ARCHINFO SET XH=XH-1 WHERE RSID=? AND FL=? AND XH>?",
                            (int(rsid), fl, xh),
                        )
        elif single_action:
            if single_action == "UPDATE":
                cursor.execute(
                    "UPDATE RS_ARCHINFO SET CLTM=?, FYEAR=?, FMONTH=?, FDAY=?, YS=?, BZ=? WHERE ARCHID=?",
                    (
                        single_row.get("CLTM", ""),
                        single_row.get("FYEAR", ""),
                        single_row.get("FMONTH", ""),
                        single_row.get("FDAY", ""),
                        single_row.get("YS", ""),
                        single_row.get("BZ", ""),
                        single_row.get("ARCHID"),
                    ),
                )
            elif single_action == "DELETE":
                cursor.execute(
                    "SELECT FL, XH FROM RS_ARCHINFO WHERE ARCHID=?",
                    (single_row.get("ARCHID"),),
                )
                del_info = cursor.fetchone()
                if del_info:
                    fl, xh = del_info
                    cursor.execute(
                        "DELETE FROM RS_ARCHINFO WHERE ARCHID=?",
                        (single_row.get("ARCHID"),),
                    )
                    cursor.execute(
                        "UPDATE RS_ARCHINFO SET XH=XH-1 WHERE RSID=? AND FL=? AND XH>?",
                        (int(rsid), fl, xh),
                    )
            elif single_action == "InsertUp":
                xh = int(single_row.get("XH", 1))
                fl = int(single_row.get("FL", 1))
                cursor.execute(
                    "UPDATE RS_ARCHINFO SET XH=XH+1 WHERE RSID=? AND FL=? AND XH>=?",
                    (int(rsid), fl, xh),
                )
                cursor.execute(
                    "INSERT INTO RS_ARCHINFO (RSID, XH, FL, ADDTIME) VALUES (?,?,?,GETDATE())",
                    (int(rsid), xh, fl),
                )
            elif single_action == "InsertDown":
                xh = int(single_row.get("XH", 1))
                fl = int(single_row.get("FL", 1))
                cursor.execute(
                    "UPDATE RS_ARCHINFO SET XH=XH+1 WHERE RSID=? AND FL=? AND XH>?",
                    (int(rsid), fl, xh),
                )
                cursor.execute(
                    "INSERT INTO RS_ARCHINFO (RSID, XH, FL, ADDTIME) VALUES (?,?,?,GETDATE())",
                    (int(rsid), xh + 1, fl),
                )
            elif single_action == "NEWROW":
                xh = int(single_row.get("XH", 1))
                fl = int(single_row.get("FL", 1))
                cursor.execute(
                    "INSERT INTO RS_ARCHINFO (RSID, XH, FL, CLTM, ADDTIME) VALUES (?,?,?,?,GETDATE())",
                    (int(rsid), xh, fl, single_row.get("CLTM", "")),
                )
            elif single_action == "CHANGENUM":
                cursor.execute(
                    "UPDATE RS_ARCHINFO SET XH=? WHERE ARCHID=?",
                    (int(single_row.get("XH", 1)), single_row.get("ARCHID")),
                )

        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "操作成功"})
    except Exception as e:
        logger.error(f"directory_save error: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def directory_print_api(request):
    """打印档案目录"""
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT JBBH + '-' + CAST(XH AS VARCHAR(5)) AS 编号, CLTM AS 材料名称,
                   FYEAR AS 年, FMONTH AS 月, FDAY AS 日, YS AS 页数, BZ AS 备注
            FROM RS_ARCHINFO a LEFT JOIN CATETREE b ON a.FL = b.FL
            WHERE a.RSID = ? ORDER BY a.FL, a.XH
        """,
            (int(rsid),),
        )
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
