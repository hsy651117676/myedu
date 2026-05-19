"""
人员搜索组件 API
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from main.db_utils import _get_conn

logger = logging.getLogger(__name__)


@login_required
def person_search_api(request):
    keyword = request.GET.get("keyword", "").strip()
    if not keyword:
        return JsonResponse({"code": 400, "msg": "缺少关键词"})

    page = int(request.GET.get("page", 1))
    page_size = min(int(request.GET.get("pageSize", 30)), 200)
    offset = (page - 1) * page_size
    is_pinyin = keyword.isalpha() and all(ord(c) < 128 for c in keyword)

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if is_pinyin:
            cursor.execute(
                "SELECT COUNT(*) FROM RS_INFO WHERE XMPY LIKE ? OR STRXMPY LIKE ?",
                [f"%{keyword}%", f"%{keyword}%"]
            )
        else:
            keyword_safe = keyword.replace("'", "''")
            cursor.execute(f"SELECT COUNT(*) FROM RS_INFO WHERE XM LIKE N'%{keyword_safe}%'")

        total = cursor.fetchone()[0]

        if is_pinyin:
            cursor.execute(
                """SELECT RSID, XM AS 姓名 FROM RS_INFO
                   WHERE XMPY LIKE ? OR STRXMPY LIKE ?
                   ORDER BY RYBH OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
                [f"%{keyword}%", f"%{keyword}%", offset, page_size]
            )
        else:
            cursor.execute(f"""SELECT RSID, XM AS 姓名 FROM RS_INFO
                              WHERE XM LIKE N'%{keyword_safe}%'
                              ORDER BY RYBH OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY""")

        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()

        results = []
        for r in rows:
            results.append({
                "rsid": str(r["RSID"]),
                "displayName": r.get("姓名", "未知"),
                "unitName": "",
                "matchType": "拼音匹配" if is_pinyin else "",
            })

        return JsonResponse({
            "code": 0, "data": results, "total": total,
            "page": page, "pageSize": page_size
        })
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
