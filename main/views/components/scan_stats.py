"""
扫描统计 API
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from main.db_utils import _get_conn

logger = logging.getLogger(__name__)


@login_required
def scan_stats_api(request):
    rsid = request.GET.get('rsid', '')
    if not rsid:
        return JsonResponse({'code': 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM RS_ARCHINFO WHERE RSID=?", (int(rsid),))
        total = cursor.fetchone()[0]

        table_name = f"RS_DESCRIPT_{rsid}"
        cursor.execute(f"""
            SELECT COUNT(DISTINCT a.ARCHID) FROM RS_ARCHINFO a
            INNER JOIN {table_name} d ON a.ARCHID = d.Archid
            WHERE a.RSID = ?
        """, (int(rsid),))
        scanned = cursor.fetchone()[0] if total > 0 else 0

        unscanned = total - scanned
        rate = round(scanned / total * 100, 1) if total > 0 else 0

        cursor.close()
        return JsonResponse({
            'code': 0, 'total': total, 'scanned': scanned,
            'unscanned': unscanned, 'rate': rate
        })
    except Exception as e:
        unscanned = total if 'total' in dir() else 0
        return JsonResponse({
            'code': 0, 'total': total if 'total' in dir() else 0,
            'scanned': 0, 'unscanned': unscanned, 'rate': 0
        })
    finally:
        if conn:
            conn.close()
