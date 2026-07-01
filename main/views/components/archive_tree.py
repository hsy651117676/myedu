"""
档案材料树组件 API
"""

import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from main.utils import _get_conn
from main.utils.decorators import archive_perm_required

logger = logging.getLogger(__name__)


@login_required
@archive_perm_required
def archive_tree_api(request):
    """档案材料树 - 三级联动"""
    pid = request.GET.get("pid", "-1")
    rsid = request.GET.get("rsid", "")

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if pid == "-1":
            cursor.execute(
                "SELECT FL, JBBH + '、' + FLSM AS name, PID FROM CATETREE WHERE PID=-1 ORDER BY FL"
            )
            tree = [{"fl": r[0], "name": r[1], "pid": r[2]} for r in cursor.fetchall()]

            cursor.execute(
                "SELECT FL, JBBH + '、' + FLSM AS name, PID FROM CATETREE WHERE PID=4 ORDER BY FL"
            )
            sub4 = [{"fl": r[0], "name": r[1]} for r in cursor.fetchall()]

            cursor.execute(
                "SELECT FL, JBBH + '、' + FLSM AS name, PID FROM CATETREE WHERE PID=9 ORDER BY FL"
            )
            sub9 = [{"fl": r[0], "name": r[1]} for r in cursor.fetchall()]

            cursor.close()
            return JsonResponse({"code": 0, "tree": tree, "sub4": sub4, "sub9": sub9})

        elif pid in ("4", "9"):
            cursor.execute(
                f"SELECT FL, JBBH + '、' + FLSM AS name, PID FROM CATETREE WHERE PID={pid} ORDER BY FL"
            )
            rows = [{"fl": r[0], "name": r[1]} for r in cursor.fetchall()]
            cursor.close()
            return JsonResponse({"code": 0, "data": rows})

        else:
            if not rsid:
                cursor.close()
                return JsonResponse({"code": 400, "msg": "缺少rsid"})

            cursor.execute(
                """SELECT ARCHID, RSID, XH, CLTM, FYEAR, FMONTH, FDAY, YS, BZ, FL
                   FROM RS_ARCHINFO WHERE RSID=? AND FL=? ORDER BY XH""",
                (int(rsid), int(pid)),
            )
            cols = [col[0] for col in cursor.description]
            rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
            cursor.close()
            return JsonResponse({"code": 0, "data": rows})

    except Exception as e:
        logger.error(f"archive_tree error: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
def archive_tree_all_api(request):
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # 材料目录
        cursor.execute(
            "SELECT ARCHID, FL, XH, CLTM, FYEAR, FMONTH, FDAY, YS, BZ FROM RS_ARCHINFO WHERE RSID=? ORDER BY FL, XH",
            (int(rsid),),
        )
        materials = {}
        for r in cursor.fetchall():
            fl = r[1]
            materials.setdefault(fl, []).append(
                {
                    "archid": r[0],
                    "fl": fl,
                    "xh": r[2],
                    "cltm": r[3],
                    "fyear": r[4],
                    "fmonth": r[5],
                    "fday": r[6],
                    "ys": r[7],
                    "bz": r[8],
                }
            )

        # 扫描记录
        try:
            table_name = f"RS_DESCRIPT_{rsid}"
            cursor.execute(
                f"SELECT Archid, Sxh, Length, uptime, Oldfilename, Pdfkey FROM {table_name} ORDER BY Archid, Sxh"
            )
            scans = {}
            for r in cursor.fetchall():
                archid = str(r[0])
                scans.setdefault(archid, []).append(
                    {
                        "sxh": r[1],
                        "length": r[2],
                        "uptime": str(r[3]) if r[3] else "",
                        "filename": r[4],
                        "pdfkey": r[5],
                    }
                )
        except:
            scans = {}

        cursor.close()
        return JsonResponse({"code": 0, "materials": materials, "scans": scans})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
