"""
数据导出
"""

import json
import time
import hashlib
from io import BytesIO
from urllib.parse import quote
from datetime import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
from main.utils import _get_conn
from main.utils.decorators import archive_perm_required
import logging

logger = logging.getLogger(__name__)


# ==================== 查询类型 ====================

QUERY_TYPES = [
    {"value": "专审认定及差缺材料查询", "label": "专审认定及差缺材料查询"},
    {"value": "单位汇总", "label": "单位汇总"},
    {"value": "档案数字化情况统计", "label": "档案数字化情况统计"},
    {"value": "三龄两历情况查询", "label": "三龄两历情况查询"},
    {"value": "人员信息总表", "label": "人员信息总表"},
]


def _is_admin(request):
    if request.user.is_superuser:
        return True
    try:
        if request.user.profile.group and request.user.profile.group.code == "admin":
            return True
    except:
        pass
    archive_user = request.session.get("archive_user", {})
    if archive_user.get("is_admin"):
        return True
    return False


def _get_user_depart(request):
    info = request.session.get("archive_user", {})
    return info.get("depart_id")


def _safe_int_list(tids):
    result = []
    for t in tids:
        if t is None:
            continue
        s = str(t).strip()
        if s and s.isdigit():
            result.append(s)
    return result


def _expand_tids(cursor, tids):
    tids = _safe_int_list(tids)
    if not tids:
        return []
    placeholders = ",".join(["?"] * len(tids))
    cursor.execute(
        f"SELECT TID FROM BMGL WHERE TID IN ({placeholders}) AND PID = -1", tids
    )
    group_tids = set(str(r[0]) for r in cursor.fetchall() if r[0] is not None)

    expanded = []
    for tid in tids:
        if str(tid) in group_tids:
            cursor.execute("SELECT TID FROM BMGL WHERE PID = ? AND PID > 0", (tid,))
            expanded.extend(str(r[0]) for r in cursor.fetchall() if r[0] is not None)
        else:
            expanded.append(str(tid))

    seen = set()
    result = []
    for t in expanded:
        if t not in seen and t.isdigit():
            seen.add(t)
            result.append(t)
    return result


def _is_all_units(cursor, unit_tids):
    cursor.execute("SELECT COUNT(*) FROM BMGL WHERE PID > 0")
    total = cursor.fetchone()[0]
    return len(unit_tids) >= total


def _build_where(cursor, unit_tids):
    if not unit_tids:
        return "", []
    if _is_all_units(cursor, unit_tids):
        return "", []
    placeholders = ",".join(["?"] * len(unit_tids))
    return f"WHERE USERS_DEPARTMENT.DEPARTMENTID IN ({placeholders})", list(unit_tids)


def _build_sql(cursor, query_type, unit_tids):
    """返回 (sql, params, order_by)"""
    unit_tids = _safe_int_list(unit_tids)

    if query_type == "单位汇总":
        sql = """
            WITH page_stats AS (
                SELECT RSID, SUM(ISNULL(YS, 0)) AS 总页数
                FROM RS_ARCHINFO
                GROUP BY RSID
            ),
            scan_stats AS (
                SELECT 
                    CAST(REPLACE(t.name, 'RS_DESCRIPT_', '') AS INT) AS RSID,
                    SUM(p.rows) AS 已扫描
                FROM sys.tables t
                INNER JOIN sys.partitions p ON t.object_id = p.object_id
                WHERE t.name LIKE 'RS_DESCRIPT_%'
                AND p.index_id IN (0, 1)
                GROUP BY t.name
            )
            SELECT 
                d.BM AS 序号,
                d.BMMC AS 单位,
                d.BM AS 单位ID,
                COUNT(DISTINCT r.RSID) AS 总人数,
                SUM(CASE WHEN r.XB = '男' THEN 1 ELSE 0 END) AS 男,
                SUM(CASE WHEN r.XB = '女' THEN 1 ELSE 0 END) AS 女,
                SUM(CASE WHEN r.XB IS NULL OR r.XB NOT IN ('男', '女') THEN 1 ELSE 0 END) AS 性别未知,
                ISNULL(SUM(ps.总页数), 0) AS 档案总页数,
                ISNULL(SUM(ss.已扫描), 0) AS 已扫描页数,
                CASE 
                    WHEN ISNULL(SUM(ss.已扫描), 0) > ISNULL(SUM(ps.总页数), 0) THEN 0
                    ELSE ISNULL(SUM(ps.总页数), 0) - ISNULL(SUM(ss.已扫描), 0)
                END AS 未扫描页数,
                CASE 
                    WHEN ISNULL(SUM(ps.总页数), 0) = 0 THEN 0
                    WHEN ISNULL(SUM(ss.已扫描), 0) >= ISNULL(SUM(ps.总页数), 0) THEN 100.00
                    ELSE CAST(ISNULL(SUM(ss.已扫描), 0) * 1.0 / ISNULL(SUM(ps.总页数), 0) * 100 AS NUMERIC(10, 2))
                END AS 完成率
            FROM DEPART d
            INNER JOIN USERS_DEPARTMENT ud ON ud.DEPARTMENTID = d.BM
            INNER JOIN RS_INFO r ON r.RSID = ud.RSID
            LEFT JOIN page_stats ps ON ps.RSID = r.RSID
            LEFT JOIN scan_stats ss ON ss.RSID = r.RSID
            GROUP BY d.BM, d.BMMC
            ORDER BY d.BM
        """
        return sql, [], ""

    if not unit_tids:
        return None, None, None

    where, params = _build_where(cursor, unit_tids)

    if query_type == "专审认定及差缺材料查询":
        sql = f"""
            SELECT rs_info.rsid as 人员标识
                ,rs_info.xm as 姓名
                ,rs_info.IDCARD as 身份证号
                ,RS_INFO.RYBH as 档案编号
                ,gh as 柜号, ch as 层号
                ,DEPART.BMMC as 单位
                ,rs_info.XB as 性别
                ,rs_info.JG as 籍贯
                ,(CASE WHEN YW_ZXSHDJ.cssj1A = 0 THEN '否' ELSE '是' END) AS 出生记载是否一致
                ,YW_ZXSHDJ.cssj2B AS 出生最早材料类号
                ,YW_ZXSHDJ.cssj2C AS 出生最早材料名称
                ,YW_ZXSHDJ.cssj2D AS 出生最早材料形成时间
                ,YW_ZXSHDJ.cssj5A AS 出生是否有涂改
                ,YW_ZXSHDJ.cssj AS 出现的出生时间罗列
                ,rs_info.CSNY as 认定出生年月
                ,(CASE WHEN YW_ZXSHDJ.cjgz1A = 0 THEN '否' ELSE '是' END) AS 参工记载一致
                ,YW_ZXSHDJ.cjgz3B AS 参工起薪材料类号
                ,YW_ZXSHDJ.cjgz3C AS 参工起薪材料名称
                ,YW_ZXSHDJ.cjgz3D AS 参工起薪材料形成时间
                ,YW_ZXSHDJ.cjgz AS 参工的时间罗列
                ,RS_INFO.DJYY AS 工龄间断情况或工龄文件内容
                ,rs_info.WORKTIME as 认定参加工作时间
                ,rs_info.ZZMM as 政治面貌
                ,YW_ZXSHDJ.rdsj AS 政治面貌时间罗列
                ,rs_info.JOINTIME as 入党团或群团组织时间
                ,rs_info.MZ as 民族
                ,YW_ZXSHDJ.mc AS 出现的民族罗列
                ,rs_info.QUANRIZIXUELI as 全日制学历
                ,rs_info.ZAIZHIXUELI as 在职学历
                ,YW_ZXSHDJ.zyjs1A AS 最高职称
                ,(CASE WHEN YW_ZXSHDJ.zyjs2A = 0 THEN '否' ELSE '是' END) AS 最高职称是否被聘
                ,rs_info.DCDW AS 专审认定初审人
                ,rs_info.DCSJ AS 专审认定初审时间
                ,rs_info.DJDW AS 专审认定复审人
                ,rs_info.DJSJ AS 专审认定复审时间
                ,rs_info.AR AS 专审认定党组会时间
                ,rs_info.WYZ AS 专审认定本人签字时间
                ,rs_info.DCYY AS 专审认定本人意见
                ,rs_info.QINGKUANSHUOMI as 档案存在问题
            FROM RS_INFO
            LEFT JOIN USERS_DEPARTMENT ON rs_info.RSID = USERS_DEPARTMENT.rsid
            LEFT JOIN DEPART ON USERS_DEPARTMENT.DEPARTMENTID = DEPART.BM
            LEFT JOIN YW_INFO ON rs_info.RSID = YW_INFO.rsid
            LEFT JOIN YW_ZXSHDJ ON YW_ZXSHDJ.RSID = RS_INFO.RSID
            {where}
            ORDER BY RS_INFO.RYBH, rs_info.xm
        """
        return sql, params, "ORDER BY RS_INFO.RYBH, rs_info.xm"

    elif query_type == "档案数字化情况统计":
        sql = f"""
            SELECT RS_INFO.RSID AS 人员标识
                ,DEPART.BMMC AS 单位
                ,XM AS 姓名
                ,rs_info.IDCARD AS 身份证号
                ,ISNULL(ar.总页数, 0) AS 档案页数
                ,NULL AS 已扫描
                ,NULL AS 未扫描
            FROM RS_INFO
            LEFT JOIN USERS_DEPARTMENT ON rs_info.RSID = USERS_DEPARTMENT.rsid
            LEFT JOIN DEPART ON USERS_DEPARTMENT.DEPARTMENTID = DEPART.BM
            LEFT JOIN (
                SELECT RSID, SUM(ys) AS 总页数 FROM RS_ARCHINFO GROUP BY RSID
            ) ar ON ar.RSID = RS_INFO.RSID
            {where}
            ORDER BY RS_INFO.RYBH, rs_info.xm
        """
        return sql, params, "ORDER BY RS_INFO.RYBH, rs_info.xm"

    elif query_type == "三龄两历情况查询":
        sql = f"""
            SELECT rs_info.rsid as 人员标识
                ,rs_info.xm as 姓名
                ,rs_info.IDCARD as 身份证号
                ,rs_info.JOBUNIT as 单位及职务
                ,rs_info.APPOINTTIME as 任现职时间
                ,rs_info.CSNY as 出生年月
                ,rs_info.WORKTIME as 参加工作时间
                ,rs_info.ZZMM as 政治面貌
                ,rs_info.JOINTIME as 入党时间
                ,rs_info.QUANRIZIXUELI as 全日制学历
                ,rs_info.QUANRIZIYUANXIAO as 全日制学校
                ,rs_info.QUANRIZIZHUANYE as 全日制专业
                ,rs_info.RMSJ AS 全日制入学时间
                ,rs_info.BYSJ AS 全日制毕业时间
                ,rs_info.QUANRIZIXUEWEI as 全日制学位
                ,rs_info.ZAIZHIXUELI as 在职教育学历
                ,rs_info.ZAIZHIYUANXIAO as 在职教育学校
                ,rs_info.ZAIZHIZHUANYE as 在职教育专业
                ,rs_info.PPSJ as 在职教育入学时间
                ,rs_info.YGXZ as 在职教育毕业时间
                ,rs_info.ZAIZHIXUEWEI as 在职教育学位
                ,Z_supplement.assessmentResults AS 历年年度考核结果
                ,Z_supplement.reward AS 奖励情况
                ,rs_info.DUANQUECAILIAO AS 处分情况
                ,Z_supplement.resume AS 简历
            FROM RS_INFO
            LEFT JOIN USERS_DEPARTMENT ON rs_info.RSID = USERS_DEPARTMENT.rsid
            LEFT JOIN Z_supplement ON rs_info.RSID = Z_supplement.rsid
            {where}
            ORDER BY RS_INFO.RYBH, rs_info.xm
        """
        return sql, params, "ORDER BY RS_INFO.RYBH, rs_info.xm"

    elif query_type == "人员信息总表":
        sql = f"""
            SELECT rs_info.rsid
                ,rs_info.xm as 姓名
                ,RS_INFO.RYBH as 档案编号
                ,gh as 柜号, ch as 层号
                ,DEPART.BMMC as 单位
                ,rs_info.XB as 性别
                ,rs_info.JG as 籍贯
                ,rs_info.CSNY as 出生年月
                ,rs_info.WORKTIME as 参加工作时间
                ,rs_info.ZZMM as 政治面貌
                ,rs_info.JOINTIME as 入党时间
                ,rs_info.JOBUNIT as 现任职称
                ,rs_info.APPOINTTIME as 现职时间
                ,rs_info.IDCARD as 身份证号
                ,rs_info.QUANRIZIXUELI as 全日制学历
                ,rs_info.QUANRIZIXUEWEI as 全日制时间
                ,rs_info.QUANRIZIYUANXIAO as 全日制学校
                ,rs_info.QUANRIZIZHUANYE as 全日制专业
                ,rs_info.ZAIZHIXUELI as 在职教育学历
                ,rs_info.ZAIZHIXUEWEI as 在职教育时间
                ,rs_info.ZAIZHIYUANXIAO as 在职教育学校
                ,rs_info.ZAIZHIZHUANYE as 在职教育专业
                ,rs_info.QINGKUANSHUOMI as 档案存在问题
                ,rs_info.DANGANZHENGLIREN as 档案整理人
                ,rs_info.DANGANSHENHEREN as 档案审核人
                ,rs_info.SHUZIHUACAIJIREN as 数字档案采集人
                ,rs_info.SHUZIHUASHENHEREN as 数字档案审核人
                ,rs_info.ARCHFILE as 档案是否数字化
            FROM RS_INFO
            LEFT JOIN USERS_DEPARTMENT ON rs_info.RSID = USERS_DEPARTMENT.rsid
            LEFT JOIN DEPART ON USERS_DEPARTMENT.DEPARTMENTID = DEPART.BM
            LEFT JOIN YW_INFO ON rs_info.RSID = YW_INFO.rsid
            {where}
        """
        return sql, params, ""

    return None, None, None


def _query_data(cursor, query_type, unit_tids, page=1, page_size=50, paginate=True):
    """执行查询，返回 (columns, rows, total)。结果缓存 10 分钟"""

    # ========== 缓存 key ==========
    tids_key = hashlib.md5(",".join(map(str, sorted(unit_tids))).encode()).hexdigest()[
        :16
    ]
    cache_key = f"data_export:{query_type}:{tids_key}:{page}:{page_size}:{paginate}"

    cached = cache.get(cache_key)
    if cached:
        logger.info(f"[缓存命中] {cache_key}")
        return cached["cols"], cached["rows"], cached["total"]

    sql, params, order_by = _build_sql(cursor, query_type, unit_tids)
    if not sql:
        return [], [], 0

    if paginate:
        # 去掉 ORDER BY 后查总数
        sql_no_order = sql
        idx = sql_no_order.upper().rfind("ORDER BY")
        if idx != -1:
            sql_no_order = sql_no_order[:idx]
        count_sql = f"SELECT COUNT(*) FROM ({sql_no_order}) t"
        cursor.execute(count_sql, params or [])
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        sql_final = f"{sql} OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY"
    else:
        sql_final = sql
        total = None  # 稍后用 len(rows) 赋值

    t0 = time.time()
    cursor.execute(sql_final, params or [])
    cols = [c[0] for c in cursor.description]
    rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
    if total is None:
        total = len(rows)

    # ========== 补充：档案数字化情况统计 ==========
    if query_type == "档案数字化情况统计" and rows:
        rsids = [r["人员标识"] for r in rows]
        scan_map = {}
        batch_size = 500
        for i in range(0, len(rsids), batch_size):
            batch = rsids[i : i + batch_size]
            placeholders = ",".join(["?"] * len(batch))
            cursor.execute(
                f"""
                SELECT 
                    CAST(REPLACE(t.name, 'RS_DESCRIPT_', '') AS INT) AS RSID,
                    SUM(p.rows) AS cnt
                FROM sys.tables t
                INNER JOIN sys.partitions p ON t.object_id = p.object_id
                WHERE t.name LIKE 'RS_DESCRIPT_%'
                  AND p.index_id IN (0, 1)
                  AND CAST(REPLACE(t.name, 'RS_DESCRIPT_', '') AS INT) IN ({placeholders})
                GROUP BY t.name
            """,
                batch,
            )
            for r in cursor.fetchall():
                scan_map[r[0]] = r[1]

        for row in rows:
            rsid = row["人员标识"]
            scanned = scan_map.get(rsid, 0)
            total_pages = row["档案页数"] or 0
            row["已扫描"] = scanned
            row["未扫描"] = max(0, total_pages - scanned)

    logger.info(
        f"[查询] {query_type} 耗时 {time.time() - t0:.2f}s，返回 {len(rows)} 条，总数 {total}"
    )

    # ========== 写入缓存（10 分钟）==========
    cache.set(cache_key, {"cols": cols, "rows": rows, "total": total}, 600)

    return cols, rows, total


# ==================== API ====================


@login_required
@archive_perm_required
def page(request):
    return render(request, "archives/data_export.html")


@login_required
@archive_perm_required
def types_api(request):
    return JsonResponse({"code": 0, "data": QUERY_TYPES})


@login_required
@archive_perm_required
def tree_api(request):
    tid = request.GET.get("tid", "")
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if tid == "":
            cursor.execute("""
                SELECT p.TID, p.TNAME, COUNT(DISTINCT r.RSID) AS CNT
                FROM RS_INFO r
                INNER JOIN USERS_DEPARTMENT u ON r.RSID = u.RSID
                INNER JOIN BMGL c ON u.DEPARTMENTID = c.TID
                INNER JOIN BMGL p ON c.PID = p.TID
                WHERE p.PID = -1
                GROUP BY p.TID, p.TNAME
                ORDER BY CNT DESC
            """)
            rows = [
                {"tid": r[0], "tname": r[1], "count": r[2]} for r in cursor.fetchall()
            ]
            total = sum(r["count"] for r in rows)
            cursor.close()
            return JsonResponse({"code": 0, "groups": rows, "total": total})

        cursor.execute("SELECT PID FROM BMGL WHERE TID = ?", (tid,))
        row = cursor.fetchone()

        if row and row[0] == -1:
            cursor.execute(
                """
                SELECT c.TID, c.TNAME, COUNT(DISTINCT r.RSID) AS CNT
                FROM RS_INFO r
                INNER JOIN USERS_DEPARTMENT u ON r.RSID = u.RSID
                INNER JOIN BMGL c ON u.DEPARTMENTID = c.TID
                WHERE c.PID = ? AND c.PID > 0
                GROUP BY c.TID, c.TNAME
                ORDER BY CNT DESC
            """,
                (tid,),
            )
            rows = [
                {"tid": r[0], "tname": r[1], "count": r[2]} for r in cursor.fetchall()
            ]
            cursor.close()
            return JsonResponse({"code": 0, "children": rows})
        else:
            cursor.execute(
                """
                SELECT c.TID, c.TNAME, COUNT(DISTINCT r.RSID) AS CNT
                FROM RS_INFO r
                INNER JOIN USERS_DEPARTMENT u ON r.RSID = u.RSID
                INNER JOIN BMGL c ON u.DEPARTMENTID = c.TID
                WHERE c.TID = ? AND c.PID > 0
                GROUP BY c.TID, c.TNAME
            """,
                (tid,),
            )
            r = cursor.fetchone()
            row_data = [{"tid": r[0], "tname": r[1], "count": r[2]}] if r else []
            cursor.close()
            return JsonResponse({"code": 0, "children": row_data})

    except Exception as e:
        logger.error(f"tree error: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
def query_api(request):
    query_type = request.GET.get("type", "")
    tids_str = request.GET.get("tids", "")
    tids = _safe_int_list(tids_str.split(","))
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 50))

    if query_type not in [t["value"] for t in QUERY_TYPES]:
        return JsonResponse({"code": 400, "msg": "无效的查询类型"})

    is_admin = _is_admin(request)
    depart_id = _get_user_depart(request)

    if not is_admin:
        if not depart_id:
            return JsonResponse({"code": 403, "msg": "无法确定您的单位"})
        tids = [str(depart_id)]

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if query_type == "单位汇总":
            cols, rows, total = _query_data(cursor, query_type, [], paginate=False)
        else:
            unit_tids = _expand_tids(cursor, tids)
            if not unit_tids:
                cursor.close()
                return JsonResponse(
                    {
                        "code": 0,
                        "columns": [],
                        "data": [],
                        "total": 0,
                        "isAdmin": is_admin,
                    }
                )
            cols, rows, total = _query_data(
                cursor, query_type, unit_tids, page, page_size, paginate=True
            )

        cursor.close()

        columns = [{"prop": c, "label": c, "minWidth": 120} for c in cols]

        return JsonResponse(
            {
                "code": 0,
                "columns": columns,
                "data": rows,
                "total": total,
                "page": page,
                "pageSize": page_size,
                "isAdmin": is_admin,
            }
        )
    except Exception as e:
        logger.error(f"query error: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
def export_api(request):
    query_type = request.GET.get("type", "")
    tids_str = request.GET.get("tids", "")
    tids = _safe_int_list(tids_str.split(","))

    if query_type not in [t["value"] for t in QUERY_TYPES]:
        return JsonResponse({"code": 400, "msg": "无效的查询类型"})

    is_admin = _is_admin(request)
    depart_id = _get_user_depart(request)

    if not is_admin:
        if not depart_id:
            return JsonResponse({"code": 403, "msg": "无法确定您的单位"})
        tids = [str(depart_id)]

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if query_type == "单位汇总":
            cols, rows, _ = _query_data(cursor, query_type, [], paginate=False)
        else:
            unit_tids = _expand_tids(cursor, tids)
            if not unit_tids:
                cursor.close()
                return JsonResponse({"code": 400, "msg": "没有数据"})
            # 导出不分页
            cols, rows, _ = _query_data(cursor, query_type, unit_tids, paginate=False)

        cursor.close()

        import openpyxl
        from openpyxl.styles import Font, Alignment

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = query_type[:20]

        ws.append(cols)
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for row in rows:
            ws.append([str(row.get(c, "") or "") for c in cols])

        for i, c in enumerate(cols, 1):
            letter = ws.cell(row=1, column=i).column_letter
            ws.column_dimensions[letter].width = 18

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)

        filename = f"{query_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        resp = HttpResponse(
            buf.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        return resp

    except Exception as e:
        logger.error(f"export error: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
