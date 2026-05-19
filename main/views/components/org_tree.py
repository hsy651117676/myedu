"""
组织树组件 API
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from main.db_utils import _get_conn

logger = logging.getLogger(__name__)


@login_required
def tree_root_api(request):
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT TID, TNAME, PID, RSID, DABH, GH, CH, SEX FROM BMGL WHERE PID = -1 ORDER BY DABH, TID"
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
def tree_children_api(request):
    tid = request.GET.get("tid", "")
    if not tid:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT TID, TNAME, PID, RSID, DABH, GH, CH, SEX
               FROM BMGL WHERE PID=? OR (TID=? AND PID=0) ORDER BY DABH, TID""",
            (tid, tid),
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
