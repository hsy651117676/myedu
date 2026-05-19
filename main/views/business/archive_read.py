"""
档案查阅
"""
import json
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.db_utils import _get_conn
from main.decorators import archive_perm_required
from django.core.cache import cache

logger = logging.getLogger(__name__)

# 前端参数 → 数据库字段
FIELD_MAP = {
    "cyr": "CYR", "cydw": "CYDW", "pzr": "PZR", "cyly": "CYLY",
    "lcrq": "LCRQ", "jbr": "JBR", "bz": "BZ", "zcfw": "ZCFW",
    "zcr": "ZCR", "bcyrxm": "BCYRXM", "bcyrrsid": "BCYRRSID", "xh": "XH",
}
REVERSE_MAP = {v: k for k, v in FIELD_MAP.items()}


@login_required
@archive_perm_required
def page(request):
    return render(request, "business/archive_read.html")


@login_required
@archive_perm_required
def list_api(request):
    """历史查阅记录（真分页）"""
    keyword = request.GET.get("keyword", "").strip()
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 20))

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        where = "WHERE 1=1"
        params = []
        if keyword:
            where += " AND (CYDW LIKE ? OR CYLY LIKE ? OR BCYRXM LIKE ? OR CYR LIKE ?)"
            kw = f"%{keyword}%"
            params = [kw, kw, kw, kw]

        cursor.execute(f"SELECT COUNT(*) FROM YW_CYDA {where}", params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor.execute(f"""
            SELECT ID, XH, BCYRXM, CYLY, LCRQ, CYDW, CYR, PZR, ZCFW, ZCR, JBR, BZ, BCYRRSID
            FROM YW_CYDA {where}
            ORDER BY LCRQ DESC, ID DESC
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """, params)

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
    """保存/删除"""
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
                    UPDATE YW_CYDA SET XH=?, PZR=?, CYDW=?, CYLY=?, BCYRRSID=?,
                    LCRQ=?, CYR=?, ZCFW=?, ZCR=?, JBR=?, BZ=?, BCYRXM=?
                    WHERE ID=?
                """, (
                    data.get("xh", 0), data.get("pzr", ""), data.get("cydw", ""),
                    data.get("cyly", ""), data.get("bcyrrsid", ""), data.get("lcrq", ""),
                    data.get("cyr", ""), data.get("zcfw", ""), data.get("zcr", ""),
                    data.get("jbr", ""), data.get("bz", ""), data.get("bcyrxm", ""),
                    rid
                ))
            else:
                cursor.execute("SELECT ISNULL(MAX(ID),0)+1 FROM YW_CYDA")
                new_id = cursor.fetchone()[0]
                cursor.execute("""
                    INSERT INTO YW_CYDA (ID, RSID, XH, PZR, CYDW, CYLY, BCYRRSID,
                    LCRQ, CYR, ZCFW, ZCR, JBR, BZ, BCYRXM)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_id, new_id, data.get("xh", 0), data.get("pzr", ""),
                    data.get("cydw", ""), data.get("cyly", ""), data.get("bcyrrsid", ""),
                    data.get("lcrq", ""), data.get("cyr", ""), data.get("zcfw", ""),
                    data.get("zcr", ""), data.get("jbr", ""), data.get("bz", ""),
                    data.get("bcyrxm", "")
                ))
        elif action == "delete":
            cursor.execute("DELETE FROM YW_CYDA WHERE ID=?", (data.get("id"),))

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
    """被查阅人信息"""
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

@login_required
@archive_perm_required
def suggest_api(request):
    """下拉提示数据（Redis缓存30分钟）"""
    field = request.GET.get("field", "")
    if field not in ("CYDW", "PZR", "CYLY", "JBR"):
        return JsonResponse({"code": 0, "data": []})

    cache_key = f"look_suggest:{field}"
    data = cache.get(cache_key)
    if data:
        return JsonResponse({"code": 0, "data": data})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(f"SELECT DISTINCT {field} FROM YW_CYDA WHERE {field} IS NOT NULL AND {field} != '' ORDER BY {field}")
        data = [r[0] for r in cursor.fetchall()]
        cursor.close()
        cache.set(cache_key, data, 1800)
        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
