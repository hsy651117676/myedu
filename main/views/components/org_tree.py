"""
组织树组件 API
"""

import base64
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from main.utils import _get_conn

logger = logging.getLogger(__name__)


def _attach_photo(rows):
    """把 DQZP 二进制转成 dataURL，放回 PHOTO 字段"""
    for r in rows:
        zp = r.get("DQZP")
        if zp:
            try:
                r["PHOTO"] = "data:image/jpeg;base64," + base64.b64encode(zp).decode()
            except Exception:
                r["PHOTO"] = None
        else:
            r["PHOTO"] = None
        r.pop("DQZP", None)
    return rows


@login_required
def tree_root_api(request):
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT b.TID, b.TNAME, b.PID, b.RSID, b.DABH, b.GH, b.CH, b.SEX,
                      r.DQZP
               FROM BMGL b
               LEFT JOIN RS_INFO r ON b.RSID = r.RSID
               WHERE b.PID = -1 ORDER BY b.DABH, b.TID"""
        )
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": _attach_photo(rows)})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def tree_children_api(request):
    tid = request.GET.get("tid", "")
    if not tid:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT b.TID, b.TNAME, b.PID, b.RSID, b.DABH, b.GH, b.CH, b.SEX,
                      r.DQZP
               FROM BMGL b
               LEFT JOIN RS_INFO r ON b.RSID = r.RSID
               WHERE b.PID=? OR (b.TID=? AND b.PID=0) ORDER BY b.DABH, b.TID""",
            (tid, tid),
        )
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": _attach_photo(rows)})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
