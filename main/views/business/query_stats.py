"""
查询统计
"""
import json
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from main.db_utils import _get_conn
from main.decorators import archive_perm_required

logger = logging.getLogger(__name__)

TABLE_MAP = {
    "look": {"table": "YW_CYDA", "dateCol": "LCRQ", "reasonCol": "CYLY", "unitCol": "CYDW", "countCol": "XH", "name": "查阅"},
    "borrow": {"table": "YW_DAJY", "dateCol": "JYRQ", "reasonCol": "JYLY", "unitCol": "JYDW", "countCol": "XH", "name": "借阅"},
    "transfer": {"table": "YW_DAZD", "dateCol": "ZDSJ", "reasonCol": "ZDYY", "unitCol": "ZWDW", "countCol": "num", "name": "转递"},
    "receive": {"table": "YW_JSDA", "dateCol": "SJSJ", "reasonCol": "SJWH", "unitCol": "LJBM", "countCol": "num", "name": "接收"},
}


@login_required
@archive_perm_required
def stats_page(request):
    return render(request, "business/query_stats.html")


@login_required
@archive_perm_required
def stats_api(request):
    tables = request.GET.getlist("tables")
    method = request.GET.get("method", "year")

    if not tables:
        return JsonResponse({"code": 400, "msg": "请选择统计表"})

    results = []
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        for t in tables:
            cfg = TABLE_MAP.get(t)
            if not cfg:
                continue
            tbl = cfg["table"]
            dateCol = cfg["dateCol"]
            reasonCol = cfg["reasonCol"]
            unitCol = cfg["unitCol"]
            countCol = cfg["countCol"]

            if method == "year":
                sql = f"SELECT substring([{dateCol}],1,4) AS 年份, SUM({countCol}) AS 人次 FROM {tbl} GROUP BY substring([{dateCol}],1,4) ORDER BY 年份"
            elif method == "month":
                sql = f"SELECT substring([{dateCol}],1,6) AS 月份, SUM({countCol}) AS 人次 FROM {tbl} GROUP BY substring([{dateCol}],1,6) ORDER BY 月份"
            elif method == "reason":
                sql = f"SELECT [{reasonCol}] AS 理由, SUM({countCol}) AS 人次 FROM {tbl} WHERE [{reasonCol}] IS NOT NULL AND [{reasonCol}] != '' GROUP BY [{reasonCol}] ORDER BY 人次 DESC"
            elif method == "unit":
                sql = f"SELECT [{unitCol}] AS 单位, SUM({countCol}) AS 人次 FROM {tbl} WHERE [{unitCol}] IS NOT NULL AND [{unitCol}] != '' GROUP BY [{unitCol}] ORDER BY 人次 DESC"
            elif method == "summary":
                years = ["2020","2021","2022","2023","2024","2025","2026"]
                cases = ",".join([f"sum(case when substring([{dateCol}],1,4)={y} then {countCol} else 0 end) AS '{y}年'" for y in years])
                sql = f"SELECT [{reasonCol}] AS 理由, SUM({countCol}) AS 合计, {cases} FROM {tbl} WHERE [{reasonCol}] IS NOT NULL AND [{reasonCol}] != '' GROUP BY [{reasonCol}] ORDER BY 合计 DESC"
            else:
                continue

            cursor.execute(sql)
            cols = [col[0] for col in cursor.description]
            rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
            results.append({"table": t, "name": cfg["name"], "columns": cols, "data": rows})

        cursor.close()
        return JsonResponse({"code": 0, "data": results})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
