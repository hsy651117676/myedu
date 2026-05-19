"""
日志查询
"""
import json
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from main.db_utils import _get_conn
from main.decorators import archive_perm_required

logger = logging.getLogger(__name__)

LOG_TYPES = [
    {"value": 1, "label": "修改出生年月"},
    {"value": 2, "label": "修改参加工作时间"},
    {"value": 3, "label": "修改政治面貌"},
    {"value": 4, "label": "修改处分情况"},
    {"value": 5, "label": "修改工龄认定"},
]


@login_required
@archive_perm_required
def page(request):
    return render(request, "archivesSystem/log_query.html")


@login_required
@archive_perm_required
def types_api(request):
    return JsonResponse({"code": 0, "data": LOG_TYPES})


@login_required
@archive_perm_required
def query_api(request):
    control_type = int(request.GET.get("controlType", 1))
    time_begin = request.GET.get("timeBegin", "")
    time_end = request.GET.get("timeEnd", "")
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 20))

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        begin_rows = (page - 1) * page_size + 1
        end_rows = page * page_size

        type_map = {1: "出生年月", 2: "参工时间", 3: "政治面貌", 4: "处分情况", 5: "工龄文件"}
        class_name = type_map.get(control_type, "")

        sql_time = ""
        if time_begin and time_end:
            sql_time = f" AND (mtime >= '{time_begin}' AND mtime <= '{time_end}')"

        sql_type = f" AND classNumber = '{class_name}'" if class_name else ""

        base_from = """
            FROM Z_Log_rsinfo
            LEFT JOIN RS_INFO ON Z_Log_rsinfo.rsid = RS_INFO.RSID
            LEFT JOIN USERS ON Z_Log_rsinfo.userid = USERS.YHBH
            WHERE 1=1
        """ + sql_time + sql_type

        cursor.execute("SELECT COUNT(*) " + base_from)
        total = cursor.fetchone()[0]

        sql = f"""
            SELECT * FROM (
                SELECT ROW_NUMBER() OVER (ORDER BY mtime DESC) AS RowNum,
                    RS_INFO.RSID, RS_INFO.XM AS 姓名, RS_INFO.JOBUNIT AS 单位,
                    classNumber AS 类型, oldvalue AS 原值, newvalue AS 新值,
                    USERS.USERID AS 用户名, USERS.ZW AS 用户单位,
                    USERS.DOORSTR AS 联系方式, mtime AS 操作时间
                {base_from}
            ) AS TempTable
            WHERE RowNum BETWEEN {begin_rows} AND {end_rows}
        """
        cursor.execute(sql)
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]

        cursor.close()
        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
