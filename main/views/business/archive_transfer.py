"""
档案转递
"""
import json
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from main.db_utils import _get_conn
from main.decorators import archive_perm_required

logger = logging.getLogger(__name__)

FIELD_MAP = {
    "transferDate": "ZDSJ",
    "transferUnit": "ZWDW",
    "transferReason": "ZDYY",
    "handler": "JBR",
    "fileNo": "WJH",
    "original": "ZB",
    "personName": "FB",
    "receiptPerson": "HZR",
    "receiptDate": "HZSJ",
    "remark": "BZ",
    "personCount": "num",
    "personRsid": "RSID",
}
REVERSE_MAP = {v: k for k, v in FIELD_MAP.items()}


@login_required
@archive_perm_required
def page(request):
    return render(request, "business/archive_transfer.html")


@login_required
@archive_perm_required
def list_api(request):
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 20))

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM YW_DAZD")
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor.execute(f"""
            SELECT ID, RSID, ZDSJ, WJH, ZWDW, ZDYY, JBR, ZB, FB, HZR, HZSJ, BZ, num
            FROM YW_DAZD ORDER BY ZDSJ DESC, WJH DESC
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """)

        cols = [col[0] for col in cursor.description]
        rows = []
        for r in cursor.fetchall():
            d = dict(zip(cols, r))
            rows.append({REVERSE_MAP.get(k, k): v for k, v in d.items()})

        cursor.close()
        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
@csrf_exempt
def save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    action = data.get("action")
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if action == "save":
            rid = data.get("id", "")
            if rid:
                cursor.execute("""
                    UPDATE YW_DAZD SET RSID=?, ZDSJ=?, WJH=?, ZWDW=?, ZDYY=?,
                    JBR=?, ZB=?, FB=?, HZR=?, HZSJ=?, BZ=?, num=?
                    WHERE ID=?
                """, (
                    data.get("personRsid", ""), data.get("transferDate", ""),
                    data.get("fileNo", ""), data.get("transferUnit", ""),
                    data.get("transferReason", ""), data.get("handler", ""),
                    data.get("original", ""), data.get("personName", ""),
                    data.get("receiptPerson", ""), data.get("receiptDate", ""),
                    data.get("remark", ""), data.get("personCount", 0), rid
                ))
            else:
                cursor.execute("SELECT ISNULL(MAX(ID),0)+1 FROM YW_DAZD")
                new_id = cursor.fetchone()[0]
                cursor.execute("""
                    INSERT INTO YW_DAZD (ID, RSID, ZDSJ, WJH, ZWDW, ZDYY, JBR, ZB, FB, HZR, HZSJ, BZ, num)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_id, data.get("personRsid", ""), data.get("transferDate", ""),
                    data.get("fileNo", ""), data.get("transferUnit", ""),
                    data.get("transferReason", ""), data.get("handler", ""),
                    data.get("original", ""), data.get("personName", ""),
                    data.get("receiptPerson", ""), data.get("receiptDate", ""),
                    data.get("remark", ""), data.get("personCount", 0)
                ))
        elif action == "delete":
            cursor.execute("DELETE FROM YW_DAZD WHERE ID=?", (data.get("id"),))

        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "操作成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
def persons_api(request):
    rsids = request.GET.get("rsids", "")
    if not rsids:
        return JsonResponse({"code": 0, "data": []})
    ids = [x.strip() for x in rsids.split(",") if x.strip()]
    if not ids:
        return JsonResponse({"code": 0, "data": []})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(ids))
        cursor.execute(f"""
            SELECT RSID, XM AS 姓名, XB AS 性别, CSNY AS 出生年月,
                   WORKTIME AS 参加工作时间, MZ AS 民族, RYBH AS 档案编号,
                   ZZMM AS 政治面貌, JOINTIME AS 入党时间,
                   JOBUNIT AS 单位及职务, APPOINTTIME AS 任现职时间,
                   IDCARD AS 身份证号, QUANRIZIXUELI AS 全日制学历,
                   QUANRIZIXUEWEI AS 全日制学位, QUANRIZIYUANXIAO AS 全日制院校,
                   QUANRIZIZHUANYE AS 全日制专业, ZAIZHIXUELI AS 在职学历,
                   ZAIZHIXUEWEI AS 在职学位, ZAIZHIYUANXIAO AS 在职院校,
                   ZAIZHIZHUANYE AS 在职专业
            FROM RS_INFO WHERE RSID IN ({placeholders})
        """, ids)
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
