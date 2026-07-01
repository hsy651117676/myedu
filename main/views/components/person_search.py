"""
人员搜索组件 API
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from main.utils import _get_conn

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

        # 总数
        if is_pinyin:
            cursor.execute(
                """SELECT COUNT(*) FROM RS_INFO r
                   LEFT JOIN USERS_DEPARTMENT ud ON r.RSID = ud.RSID
                   WHERE r.XMPY LIKE ? OR r.STRXMPY LIKE ?""",
                [f"%{keyword}%", f"%{keyword}%"]
            )
        else:
            keyword_safe = keyword.replace("'", "''")
            cursor.execute(f"""SELECT COUNT(*) FROM RS_INFO r
                              LEFT JOIN USERS_DEPARTMENT ud ON r.RSID = ud.RSID
                              WHERE r.XM LIKE N'%{keyword_safe}%'""")

        total = cursor.fetchone()[0]

        # 分页数据
        if is_pinyin:
            cursor.execute(
                """SELECT r.RSID, r.XM AS 姓名, r.RYBH AS 档案编号,
                          ISNULL(d.BMMC, '') AS 单位名称
                   FROM RS_INFO r
                   LEFT JOIN USERS_DEPARTMENT ud ON r.RSID = ud.RSID
                   LEFT JOIN DEPART d ON ud.DEPARTMENTID = d.BM
                   WHERE r.XMPY LIKE ? OR r.STRXMPY LIKE ?
                   ORDER BY r.RYBH
                   OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
                [f"%{keyword}%", f"%{keyword}%", offset, page_size]
            )
        else:
            cursor.execute(f"""SELECT r.RSID, r.XM AS 姓名, r.RYBH AS 档案编号,
                                      ISNULL(d.BMMC, '') AS 单位名称
                               FROM RS_INFO r
                               LEFT JOIN USERS_DEPARTMENT ud ON r.RSID = ud.RSID
                               LEFT JOIN DEPART d ON ud.DEPARTMENTID = d.BM
                               WHERE r.XM LIKE N'%{keyword_safe}%'
                               ORDER BY r.RYBH
                               OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY""")

        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()

        results = []
        for r in rows:
            results.append({
                "rsid": str(r["RSID"]),
                "displayName": r.get("姓名", "未知"),
                "unitName": r.get("单位名称", ""),
                "archiveNo": r.get("档案编号", ""),
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
