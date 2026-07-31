from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.utils import _get_conn
import json
import logging
from main.utils.decorators import archive_perm_required
from main.utils import query_dict
from django.core.cache import cache

logger = logging.getLogger(__name__)


def _get_yhbh(request):
    try:
        return request.user.profile.yhbh or 0
    except:
        return 0


@login_required
@archive_perm_required
def person_directory_view(request):
    return render(request, "archives/person_directory.html")


@login_required
def directory_tree_api(request):
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT FL, JBBH + '、' + FLSM AS name, PID FROM CATETREE WHERE PID=-1 ORDER BY FL"
        )
        rows = [{"fl": r[0], "name": r[1], "pid": r[2]} for r in cursor.fetchall()]

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
            SELECT a.ARCHID, a.RSID, a.XH, a.CLTM, a.FYEAR, a.FMONTH, a.FDAY, a.YS, a.BZ, a.FL,
                b.JBBH + '-' + CAST(a.XH AS VARCHAR(5)) AS 编号
            FROM RS_ARCHINFO a
            LEFT JOIN CATETREE b ON a.FL = b.FL
            WHERE a.RSID=? AND a.FL=? ORDER BY a.XH
            """,
            (int(rsid), int(fl)),
        )
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()

        # 批量查扫描页数
        for row in rows:
            row["扫描页数"] = _get_scan_pages(row["RSID"], row["ARCHID"])

        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


def _get_scan_pages(rsid, archid):
    """查扫描页数，缓存30分钟"""
    cache_key = f"scan:pages:{rsid}:{archid}"
    pages = cache.get(cache_key)
    if pages is not None:
        return pages
    try:
        table_name = f"RS_DESCRIPT_{rsid}"
        rows = query_dict(
            f"SELECT COUNT(*) AS cnt FROM {table_name} WHERE Archid=?", (archid,)
        )
        pages = rows[0]["cnt"] if rows else 0
    except Exception:
        pages = 0
    cache.set(cache_key, pages, 1800)
    return pages


@login_required
@csrf_exempt
def directory_save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"code": 400})

    rsid = data.get("rsid")
    batch = data.get("batch", [])
    single_action = data.get("action", "")
    single_row = data.get("row", {})

    if not rsid:
        return JsonResponse({"code": 400})

    def v(val):
        """空字符串转None，避免写入0"""
        return val if val else None

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if batch:
            for item in batch:
                action = item.get("action", "UPDATE")
                row = item.get("row", {})

                if action == "UPDATE":
                    cursor.execute(
                        "UPDATE RS_ARCHINFO SET CLTM=?, FYEAR=?, FMONTH=?, FDAY=?, YS=?, BZ=? WHERE ARCHID=?",
                        (
                            row.get("CLTM", ""),
                            v(row.get("FYEAR", "")),
                            v(row.get("FMONTH", "")),
                            v(row.get("FDAY", "")),
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
                elif action == "NEWROW":
                    fl = int(row.get("FL", 0))
                    cursor.execute(
                        "SELECT ISNULL(MAX(XH),0) FROM RS_ARCHINFO WHERE RSID=? AND FL=?",
                        (int(rsid), fl),
                    )
                    xh = cursor.fetchone()[0] + 1
                    cursor.execute(
                        "INSERT INTO RS_ARCHINFO (RSID, XH, FL, CLTM, FYEAR, FMONTH, FDAY, YS, BZ, ADDTIME) VALUES (?,?,?,?,?,?,?,?,?,GETDATE())",
                        (
                            int(rsid),
                            xh,
                            fl,
                            row.get("CLTM", ""),
                            v(row.get("FYEAR", "")),
                            v(row.get("FMONTH", "")),
                            v(row.get("FDAY", "")),
                            row.get("YS", ""),
                            row.get("BZ", ""),
                        ),
                    )
                elif action == "CHANGENUM":
                    cursor.execute(
                        "UPDATE RS_ARCHINFO SET XH=? WHERE ARCHID=?",
                        (int(row.get("XH", 1)), row.get("ARCHID")),
                    )
        elif single_action:
            if single_action == "UPDATE":
                cursor.execute(
                    "UPDATE RS_ARCHINFO SET CLTM=?, FYEAR=?, FMONTH=?, FDAY=?, YS=?, BZ=? WHERE ARCHID=?",
                    (
                        single_row.get("CLTM", ""),
                        v(single_row.get("FYEAR", "")),
                        v(single_row.get("FMONTH", "")),
                        v(single_row.get("FDAY", "")),
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
                fl = int(single_row.get("FL", 0))
                cursor.execute(
                    "SELECT ISNULL(MAX(XH),0) FROM RS_ARCHINFO WHERE RSID=? AND FL=?",
                    (int(rsid), fl),
                )
                xh = cursor.fetchone()[0] + 1
                cursor.execute(
                    "INSERT INTO RS_ARCHINFO (RSID, XH, FL, CLTM, FYEAR, FMONTH, FDAY, YS, BZ, ADDTIME) VALUES (?,?,?,?,?,?,?,?,?,GETDATE())",
                    (
                        int(rsid),
                        xh,
                        fl,
                        single_row.get("CLTM", ""),
                        v(single_row.get("FYEAR", "")),
                        v(single_row.get("FMONTH", "")),
                        v(single_row.get("FDAY", "")),
                        single_row.get("YS", ""),
                        single_row.get("BZ", ""),
                    ),
                )
                cursor.execute("SELECT @@IDENTITY AS ARCHID")
                archid = cursor.fetchone()[0]
                cursor.execute(
                    """SELECT a.ARCHID, a.RSID, a.XH, a.CLTM, a.FYEAR, a.FMONTH, a.FDAY, a.YS, a.BZ, a.FL,
                              b.JBBH + '-' + CAST(a.XH AS VARCHAR(5)) AS 编号
                       FROM RS_ARCHINFO a LEFT JOIN CATETREE b ON a.FL = b.FL
                       WHERE a.ARCHID=?""",
                    (archid,),
                )
                cols = [c[0] for c in cursor.description]
                new_data = dict(zip(cols, cursor.fetchone()))
                conn.commit()
                cursor.close()
                return JsonResponse({"code": 0, "msg": "操作成功", "data": new_data})
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
def all_directory_api(request):
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少rsid"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.JBBH + '、' + c.FLSM + '-' + CAST(a.FL AS VARCHAR) + '-' + CAST(a.XH AS VARCHAR) AS 类别序号,
                   a.CLTM AS 材料名称, 
                   a.FYEAR AS 年, a.FMONTH AS 月, a.FDAY AS 日, a.YS AS 页数, a.BZ AS 备注
            FROM RS_ARCHINFO a
            LEFT JOIN CATETREE c ON a.FL = c.FL
            WHERE a.RSID = ?
              AND a.FL > 0
              AND a.CLTM IS NOT NULL AND a.CLTM != ''
            ORDER BY a.FL, a.XH
        """,
            (int(rsid),),
        )
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def all_directory_page(request):
    return render(request, "archives/person_directory_all.html")
