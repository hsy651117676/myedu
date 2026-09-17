"""
扫描统计 API
"""

import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from main.utils import _get_conn

logger = logging.getLogger(__name__)


@login_required
def scan_stats_api(request):
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # 1. 目录数统计
        cursor.execute("SELECT COUNT(*) FROM RS_ARCHINFO WHERE RSID=?", (int(rsid),))
        total = cursor.fetchone()[0]

        table_name = f"RS_DESCRIPT_{rsid}"
        cursor.execute(
            f"""
            SELECT COUNT(DISTINCT a.ARCHID) FROM RS_ARCHINFO a
            INNER JOIN {table_name} d ON a.ARCHID = d.Archid
            WHERE a.RSID = ?
        """,
            (int(rsid),),
        )
        scanned = cursor.fetchone()[0] if total > 0 else 0

        unscanned = total - scanned
        rate = round(scanned / total * 100, 1) if total > 0 else 0

        # 2. 页数统计
        # 总页数 = RS_ARCHINFO.YS 求和
        cursor.execute(
            "SELECT ISNULL(SUM(YS), 0) FROM RS_ARCHINFO WHERE RSID=?", (int(rsid),)
        )
        total_pages = cursor.fetchone()[0] or 0

        # 已扫描页数 = RS_DESCRIPT 记录数（图片张数）
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        scanned_pages = cursor.fetchone()[0] or 0

        unscanned_pages = max(0, total_pages - scanned_pages)
        page_rate = (
            round(scanned_pages / total_pages * 100, 1) if total_pages > 0 else 0
        )

        cursor.close()
        return JsonResponse(
            {
                "code": 0,
                "total": total,
                "scanned": scanned,
                "unscanned": unscanned,
                "rate": rate,
                "total_pages": total_pages,
                "scanned_pages": scanned_pages,
                "unscanned_pages": unscanned_pages,
                "page_rate": page_rate,
            }
        )
    except Exception as e:
        logger.error(f"scan_stats error: {e}")
        return JsonResponse(
            {
                "code": 0,
                "total": 0,
                "scanned": 0,
                "unscanned": 0,
                "rate": 0,
                "total_pages": 0,
                "scanned_pages": 0,
                "unscanned_pages": 0,
                "page_rate": 0,
            }
        )
    finally:
        if conn:
            conn.close()
