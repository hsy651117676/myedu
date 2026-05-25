"""
查询统计
"""
import json
import logging
from datetime import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.db_utils import _get_conn
from main.decorators import archive_perm_required

logger = logging.getLogger(__name__)

# 四个业务表配置
TABLE_CONFIG = {
    "borrow": {
        "table": "YW_DAJY",
        "date_field": "JYRQ",
        "unit_field": "JYDW",
        "reason_field": "JYLY",
        "count_field": "XH",
        "person_name_field": "BJYRXM",
        "person_id_field": "DHHM",
        "columns": ["ID", "JYRQ", "JYR", "JYDW", "JYLY", "JYJBR", "PZR", "GHRQ", "GHJBR", "BZ", "BJYRXM", "XH"],
        "col_names": ["ID", "借阅日期", "借阅人", "借阅单位", "借阅理由", "经办人", "批准人", "归还日期", "归还经办人", "备注", "被借阅人", "人数"],
    },
    "look": {
        "table": "YW_CYDA",
        "date_field": "LCRQ",
        "unit_field": "CYDW",
        "reason_field": "CYLY",
        "count_field": "XH",
        "person_name_field": "BCYRXM",
        "person_id_field": "BCYRRSID",
        "columns": ["ID", "LCRQ", "CYR", "CYDW", "CYLY", "JBR", "PZR", "ZCFW", "ZCR", "BZ", "BCYRXM", "XH"],
        "col_names": ["ID", "查阅日期", "查阅人", "查阅单位", "查阅理由", "经办人", "批准人", "摘抄范围", "摘抄人", "备注", "被查阅人", "人数"],
    },
    "receive": {
        "table": "YW_JSDA",
        "date_field": "SJSJ",
        "unit_field": "LJBM",
        "reason_field": "AJZL",
        "count_field": "num",
        "person_name_field": "TXM",
        "person_id_field": "RSID",
        "columns": ["ID", "SJSJ", "SJWH", "JSR", "LJBM", "DABH", "ZB", "FB", "GH", "CH", "XH", "SHR", "SHRQ", "HZRQ", "RKRQ", "RKSPR", "TXM", "AJZL", "BZ", "num"],
        "col_names": ["ID", "收件时间", "收件文号", "接收人", "来件部门", "档案编号", "正本", "副本", "柜号", "层号", "序号", "送交人", "送交日期", "回执日期", "入库日期", "入库审批人", "被接收人", "案卷种类", "备注", "人数"],
    },
    "transfer": {
        "table": "YW_DAZD",
        "date_field": "ZDSJ",
        "unit_field": "ZWDW",
        "reason_field": "ZDYY",
        "count_field": "num",
        "person_name_field": "FB",
        "person_id_field": "RSID",
        "columns": ["ID", "ZDSJ", "WJH", "ZWDW", "ZDYY", "JBR", "ZB", "FB", "HZR", "HZSJ", "BZ", "num"],
        "col_names": ["ID", "转递时间", "文件号", "转往单位", "转递原因", "经办人", "正本", "被转递人", "回执人", "回执时间", "备注", "人数"],
    },
}


@login_required
@archive_perm_required
def page(request):
    return render(request, "business/query_stats.html")


def _build_where(config, params):
    """构建 WHERE 条件"""
    where = "WHERE 1=1"
    sql_params = []

    year = params.get("year", "").strip()
    unit = params.get("unit", "").strip()
    reason = params.get("reason", "").strip()
    keyword = params.get("keyword", "").strip()

    if year:
        where += f" AND {config['date_field']} LIKE ?"
        sql_params.append(f"{year}%")
    if unit:
        where += f" AND {config['unit_field']} LIKE ?"
        sql_params.append(f"%{unit}%")
    if reason:
        where += f" AND {config['reason_field']} LIKE ?"
        sql_params.append(f"%{reason}%")
    if keyword:
        where += f" AND ({config['person_name_field']} LIKE ? OR {config['unit_field']} LIKE ?)"
        kw = f"%{keyword}%"
        sql_params.extend([kw, kw])

    return where, sql_params


@login_required
@archive_perm_required
def stats_api(request):
    """统计数据"""
    biz = request.GET.get("biz", "borrow")
    if biz not in TABLE_CONFIG:
        return JsonResponse({"code": 400, "msg": "无效业务类型"})

    config = TABLE_CONFIG[biz]
    where, sql_params = _build_where(config, request.GET)

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # 总览
        cursor.execute(f"SELECT COUNT(*), ISNULL(SUM({config['count_field']}),0) FROM {config['table']} {where}", sql_params)
        total_count, total_persons = cursor.fetchone()

        cursor.execute(f"SELECT COUNT(DISTINCT {config['unit_field']}) FROM {config['table']} {where} AND {config['unit_field']} IS NOT NULL AND {config['unit_field']} != ''", sql_params)
        unit_count = cursor.fetchone()[0]

        cursor.execute(f"SELECT COUNT(DISTINCT {config['reason_field']}) FROM {config['table']} {where} AND {config['reason_field']} IS NOT NULL AND {config['reason_field']} != ''", sql_params)
        reason_count = cursor.fetchone()[0]

        # 年度分布
        cursor.execute(f"""
            SELECT SUBSTRING({config['date_field']},1,4) AS yr, COUNT(*) AS cnt, ISNULL(SUM({config['count_field']}),0) AS psum
            FROM {config['table']} {where}
            GROUP BY SUBSTRING({config['date_field']},1,4)
            ORDER BY yr DESC
        """, sql_params)
        year_stats = [{"name": r[0], "count": r[1], "persons": r[2]} for r in cursor.fetchall()]

        # 单位分布 Top 10
        cursor.execute(f"""
            SELECT TOP 10 {config['unit_field']} AS nm, COUNT(*) AS cnt, ISNULL(SUM({config['count_field']}),0) AS psum
            FROM {config['table']} {where} AND {config['unit_field']} IS NOT NULL AND {config['unit_field']} != ''
            GROUP BY {config['unit_field']}
            ORDER BY cnt DESC
        """, sql_params)
        unit_stats = [{"name": r[0], "count": r[1], "persons": r[2]} for r in cursor.fetchall()]

        # 理由分布
        cursor.execute(f"""
            SELECT {config['reason_field']} AS nm, COUNT(*) AS cnt, ISNULL(SUM({config['count_field']}),0) AS psum
            FROM {config['table']} {where} AND {config['reason_field']} IS NOT NULL AND {config['reason_field']} != ''
            GROUP BY {config['reason_field']}
            ORDER BY cnt DESC
        """, sql_params)
        reason_stats = [{"name": r[0], "count": r[1], "persons": r[2]} for r in cursor.fetchall()]

        # 下拉选项
        cursor.execute(f"SELECT DISTINCT SUBSTRING({config['date_field']},1,4) FROM {config['table']} ORDER BY 1 DESC")
        years = [r[0] for r in cursor.fetchall() if r[0]]

        cursor.execute(f"SELECT DISTINCT {config['unit_field']} FROM {config['table']} WHERE {config['unit_field']} IS NOT NULL AND {config['unit_field']} != '' ORDER BY {config['unit_field']}")
        units = [r[0] for r in cursor.fetchall()]

        cursor.execute(f"SELECT DISTINCT {config['reason_field']} FROM {config['table']} WHERE {config['reason_field']} IS NOT NULL AND {config['reason_field']} != '' ORDER BY {config['reason_field']}")
        reasons = [r[0] for r in cursor.fetchall()]

        cursor.close()

        return JsonResponse({
            "code": 0,
            "data": {
                "overview": {"total_count": total_count, "total_persons": total_persons, "unit_count": unit_count, "reason_count": reason_count},
                "year_stats": year_stats,
                "unit_stats": unit_stats,
                "reason_stats": reason_stats,
                "years": years,
                "units": units,
                "reasons": reasons,
            }
        })
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
def detail_api(request):
    """明细列表"""
    biz = request.GET.get("biz", "borrow")
    if biz not in TABLE_CONFIG:
        return JsonResponse({"code": 400, "msg": "无效业务类型"})

    config = TABLE_CONFIG[biz]
    where, sql_params = _build_where(config, request.GET)

    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 20))

    # 明细下钻
    drill_unit = request.GET.get("drill_unit", "").strip()
    drill_reason = request.GET.get("drill_reason", "").strip()
    drill_year = request.GET.get("drill_year", "").strip()
    drill_month = request.GET.get("drill_month", "").strip()

    if drill_unit:
        where += f" AND {config['unit_field']} = ?"
        sql_params.append(drill_unit)
    if drill_reason:
        where += f" AND {config['reason_field']} = ?"
        sql_params.append(drill_reason)
    if drill_year:
        if drill_month:
            where += f" AND {config['date_field']} LIKE ?"
            sql_params.append(f"{drill_year}{drill_month.zfill(2)}%")
        else:
            where += f" AND {config['date_field']} LIKE ?"
            sql_params.append(f"{drill_year}%")

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute(f"SELECT COUNT(*) FROM {config['table']} {where}", sql_params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cols_str = ",".join(config["columns"])
        cursor.execute(f"""
            SELECT {cols_str} FROM {config['table']} {where}
            ORDER BY {config['date_field']} DESC, ID DESC
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """, sql_params)

        rows = [list(r) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({
            "code": 0,
            "data": {"columns": config["col_names"], "rows": rows, "total": total}
        })
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
