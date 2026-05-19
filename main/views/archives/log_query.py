from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from django.core.cache import cache
import logging
from main.db_utils import _get_conn
from main.decorators import archive_perm_required
#@archive_perm_required

logger = logging.getLogger(__name__)


@login_required
@archive_perm_required
def log_query_view(request):
    return render(request, 'archives/log_query.html')


@login_required
def log_types_api(request):
    """获取查询类型列表"""
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("{CALL logQuery('selectType', '', 0, '', 0, '', '', 0, 0)}")
        rows = cursor.fetchall()
        data = [{"value": str(r[0]), "text": r[1]} for r in rows if r[0] != 0]
        cursor.close()
        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def log_query_api(request):
    """日志查询"""
    control_type = request.GET.get('controlType', '1')
    time_begin = request.GET.get('timeBegin', '')
    time_end = request.GET.get('timeEnd', '')
    name = request.GET.get('name', '')
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('pageSize', 20))

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("{CALL logQuery('Query', '', 0, ?, ?, ?, ?, ?, ?)}",
                       (name, int(control_type), time_begin, time_end, page_size, page))
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]

        cursor.nextset()
        total_row = cursor.fetchone()
        total = total_row[0] if total_row else 0
        cursor.close()

        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
