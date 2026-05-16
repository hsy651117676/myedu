from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from django.conf import settings
import json
import logging
import pyodbc
from contextlib import contextmanager
from main.field_maps import RS_INFO_MAP, to_frontend, to_backend
from main.db_utils import _get_conn

logger = logging.getLogger(__name__)


@contextmanager
def db():
    conn = cursor = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        logger.error(f"DB Error: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise
    finally:
        if cursor:
            cursor.close()


# ==================== 权限 ====================


def _get_yhbh(request):
    try:
        return request.user.profile.yhbh
    except:
        return None


def _check_perm(request):
    return _get_yhbh(request) is not None


# ==================== 页面 ====================


@login_required
def person_view(request):
    if not _check_perm(request):
        return render(request, "archives/no_permission.html")
    return render(request, "archives/person.html")


# ==================== 树 ====================


@login_required
def tree_root_api(request):
    cache_key = "archives_tree_root_v2"
    data = cache.get(cache_key)
    if data:
        return JsonResponse({"code": 0, "data": data})
    try:
        with db() as c:
            c.execute(
                "SELECT TID, TNAME, PID, '' AS RSID, 0 AS isPerson, '' AS sex FROM BMGL WHERE PID = -1 ORDER BY DABH"
            )
            rows = c.fetchall()
            data = [
                {
                    "tid": str(r[0]),
                    "tname": r[1],
                    "pid": str(r[2]),
                    "rsid": "",
                    "isPerson": False,
                    "sex": "",
                }
                for r in rows
            ]
        cache.set(cache_key, data, 60)
        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
def tree_children_api(request):
    tid = request.GET.get("tid", "")
    if not tid:
        return JsonResponse({"code": 400, "msg": "缺少tid"})

    cache_key = f"archives_tree_children_{tid}_v2"
    data = cache.get(cache_key)
    if data:
        return JsonResponse({"code": 0, "data": data})

    try:
        with db() as c:
            c.execute("SELECT COUNT(*) FROM BMGL WHERE PID = ?", (tid,))
            has_children = c.fetchone()[0] > 0
            if has_children:
                c.execute(
                    """
                    SELECT TID, TNAME, PID,
                           CASE WHEN PID='0' THEN RSID ELSE '' END AS RSID,
                           CASE WHEN PID='0' THEN 1 ELSE 0 END AS isPerson, sex
                    FROM BMGL WHERE PID=? OR (TID=? AND PID='0')
                    ORDER BY DABH, TID
                """,
                    (tid, tid),
                )
            else:
                c.execute(
                    "SELECT TID, TNAME, PID, RSID, 1 AS isPerson, sex FROM BMGL WHERE PID='0' AND TID=? ORDER BY DABH",
                    (tid,),
                )
            rows = c.fetchall()
            data = [
                {
                    "tid": str(r[0]),
                    "tname": r[1],
                    "pid": str(r[2]),
                    "rsid": str(r[3]) if r[3] else "",
                    "isPerson": bool(r[4]),
                    "sex": r[5] if r[5] else "",
                }
                for r in rows
            ]
        cache.set(cache_key, data, 60)
        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})


# ==================== 搜索人员 ====================


@login_required
def person_search_api(request):
    """
    搜索人员：支持姓名、拼音全拼、拼音首字母。
    返回格式符合前端 person.html 要求。
    """
    keyword = request.GET.get("keyword", "").strip()
    if not keyword:
        return JsonResponse({"code": 400, "msg": "缺少关键词"})

    # 限制最大返回条数，防止性能问题
    MAX_RESULTS = 200

    # 判断是否为纯字母（拼音搜索）
    is_pinyin = keyword.isalpha()

    # 参数化查询，防止注入
    sql = """
        SELECT 
            r.RSID,
            r.XM AS 姓名,
            r.XMPY,
            r.STRXMPY,
            COALESCE(d.BMMC, '未分配单位') AS 单位名称
        FROM RS_INFO r
        LEFT JOIN USERS_DEPARTMENT ud ON r.RSID = ud.RSID
        LEFT JOIN DEPART d ON ud.DEPARTMENTID = d.BM
        WHERE 1=1
    """
    params = []

    if is_pinyin:
        # 拼音搜索：匹配全拼或首字母
        sql += """ AND (r.XMPY LIKE ? OR r.STRXMPY LIKE ?) """
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    else:
        # 汉字姓名搜索
        sql += """ AND r.XM LIKE ? """
        params.append(f"%{keyword}%")

    # 限制数量
    sql += f" ORDER BY r.RYBH OFFSET 0 ROWS FETCH NEXT {MAX_RESULTS} ROWS ONLY"

    try:
        with db() as cursor:
            cursor.execute(sql, params)
            cols = [col[0] for col in cursor.description]
            rows = [dict(zip(cols, row)) for row in cursor.fetchall()]

        # 转换为前端期望格式
        results = []
        for row in rows:
            display_name = row.get("姓名", "未知姓名")
            unit_name = row.get("单位名称", "未知单位")
            match_type = ""
            if is_pinyin:
                match_type = "拼音匹配"
            results.append(
                {
                    "rsid": str(row["RSID"]),
                    "displayName": display_name,
                    "unitName": unit_name,
                    "matchType": match_type,
                }
            )

        return JsonResponse({"code": 0, "data": results, "total": len(results)})
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return JsonResponse({"code": 500, "msg": f"搜索失败: {str(e)}"})


@login_required
def person_list_api(request):
    unit_id = request.GET.get("unit_id", "0")
    name = request.GET.get("name", "").strip()
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 30))

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        where = "1=1"
        params = []
        if unit_id and unit_id != "0":
            where += " AND d.DEPARTMENTID = ?"
            params.append(int(unit_id))
        if name:
            where += " AND b.XM LIKE ?"
            params.append(f"%{name}%")

        # 总数
        cursor.execute(
            f"SELECT COUNT(*) FROM USERS_DEPARTMENT d JOIN RS_INFO b ON d.RSID=b.RSID WHERE {where}",
            params,
        )
        total = cursor.fetchone()[0]

        # 分页
        cursor.execute(
            f"""
            SELECT b.RSID AS rsid, b.XM AS 姓名, b.XB AS 性别, c.BMMC AS 单位,
                   b.RYBH AS 档案编号, y.GH AS 柜号, y.CH AS 层号
            FROM USERS_DEPARTMENT d
            JOIN RS_INFO b ON d.RSID=b.RSID
            LEFT JOIN DEPART c ON d.DEPARTMENTID=c.BM
            LEFT JOIN YW_INFO y ON b.RSID=y.RSID
            WHERE {where}
            ORDER BY b.RYBH
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """,
            params + [(page - 1) * page_size, page_size],
        )

        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()

        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


# ==================== 单位列表 ====================


@login_required
def unit_list_api(request):
    try:
        with db() as c:
            c.execute("{CALL z_selectname(0, '')}")
            cols = [col[0] for col in c.description]
            rows = [dict(zip(cols, r)) for r in c.fetchall()]
            data = [
                {"id": r.get("序号"), "name": r.get("单位"), "total": r.get("总人数")}
                for r in rows
            ]
        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})


# ==================== 人员详情 ====================


@login_required
def person_detail_api(request):
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少RSID"})

    try:
        with db() as c:
            c.execute("SELECT * FROM RS_INFO WHERE RSID = ?", (int(rsid),))
            cols = [col[0] for col in c.description]
            row = c.fetchone()
            if not row:
                return JsonResponse({"code": 404, "msg": "人员不存在"})
            row_dict = dict(zip(cols, row))

            c.execute("SELECT GH, CH FROM YW_INFO WHERE RSID = ?", (int(rsid),))
            yw = c.fetchone()

        data = to_frontend(row_dict, RS_INFO_MAP)
        data["柜号"] = yw[0] or "" if yw else ""
        data["层号"] = yw[1] or "" if yw else ""
        data["rsid"] = rsid

        # 年龄
        csny = data.get("出生年月", "")
        if csny and len(csny) >= 6:
            from datetime import datetime

            now = datetime.now()
            age = now.year - int(csny[:4])
            if now.month < int(csny[4:6]):
                age -= 1
            data["年龄"] = str(age)

        # 工龄
        worktime = data.get("参工时间", "")
        tzsj = data.get("退休时间", "")
        if worktime and len(worktime) >= 6:
            from datetime import datetime

            now = datetime.now()
            end_y, end_m = now.year, now.month
            if tzsj and len(tzsj) >= 6:
                end_y, end_m = int(tzsj[:4]), int(tzsj[4:6])
            years = end_y - int(worktime[:4])
            months = end_m - int(worktime[4:6])
            if months < 0:
                years -= 1
                months += 12
            data["工龄"] = f"{years}年{months}个月"

        # 退休时间
        if not data.get("退休时间") and csny and len(csny) >= 6:
            y, m = int(csny[:4]), csny[4:6]
            data["退休时间"] = f"{y + (60 if data.get('性别') == '男' else 55)}{m}"

        # 照片
        try:
            if row_dict.get("DQZP"):
                import base64

                data["照片"] = (
                    "data:image/jpeg;base64,"
                    + base64.b64encode(row_dict["DQZP"]).decode()
                )
            else:
                data["照片"] = None
        except:
            data["照片"] = None

        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        logger.error(f"详情失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})


# ==================== 保存 ====================


@login_required
@csrf_exempt
def person_save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST"})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400, "msg": "JSON格式错误"})

    rsid = data.get("rsid")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少RSID"})

    db_data = to_backend(data, RS_INFO_MAP)
    yhbh = _get_yhbh(request) or 0

    try:
        with db() as c:
            c.execute(
                """
                EXEC rs_info_EDIT
                    @RSID=?, @userid=?, @XM=?, @XB=?, @MZ=?, @CHUSHENGDI=?, @JG=?, @RYLB=?,
                    @CSNY=?, @WORKTIME=?, @ZZMM=?, @JOINTIME=?, @JOBUNIT=?, @APPOINTTIME=?,
                    @ZW=?, @HSJS=?, @ZYZC=?, @IDCARD=?, @JRSJ=?, @WHCD=?, @SFZH=?, @RYBH=?,
                    @HSGZ=?, @ZN=?, @TZSJ=?, @QSSJ=?, @DUANQUECAILIAO=?,
                    @QUANRIZIXUELI=?, @QUANRIZIYUANXIAO=?, @QUANRIZIZHUANYE=?, @RMSJ=?, @BYSJ=?, @QUANRIZIXUEWEI=?,
                    @ZAIZHIXUELI=?, @ZAIZHIYUANXIAO=?, @ZAIZHIZHUANYE=?, @PPSJ=?, @YGXZ=?, @ZAIZHIXUEWEI=?,
                    @DANGANZHENGLIREN=?, @SHUZIHUACAIJIREN=?, @DANGANJUANSHU=?, @BAOSONGRIQI=?,
                    @DANGANSHENHEREN=?, @SHUZIHUASHENHEREN=?, @BAOSONGDANWEI=?,
                    @QINGKUANSHUOMI=?, @CS=?, @DJYY=?,
                    @GH=?, @CH=?
            """,
                (
                    rsid,
                    yhbh,
                    db_data.get("XM"),
                    db_data.get("XB"),
                    db_data.get("MZ"),
                    db_data.get("CHUSHENGDI"),
                    db_data.get("JG"),
                    db_data.get("RYLB"),
                    db_data.get("CSNY"),
                    db_data.get("WORKTIME"),
                    db_data.get("ZZMM"),
                    db_data.get("JOINTIME"),
                    db_data.get("JOBUNIT"),
                    db_data.get("APPOINTTIME"),
                    db_data.get("ZW"),
                    db_data.get("HSJS"),
                    db_data.get("ZYZC"),
                    db_data.get("IDCARD"),
                    db_data.get("JRSJ"),
                    db_data.get("WHCD"),
                    db_data.get("SFZH"),
                    db_data.get("RYBH"),
                    db_data.get("HSGZ"),
                    db_data.get("ZN"),
                    db_data.get("TZSJ"),
                    db_data.get("QSSJ"),
                    db_data.get("DUANQUECAILIAO"),
                    db_data.get("QUANRIZIXUELI"),
                    db_data.get("QUANRIZIYUANXIAO"),
                    db_data.get("QUANRIZIZHUANYE"),
                    db_data.get("RMSJ"),
                    db_data.get("BYSJ"),
                    db_data.get("QUANRIZIXUEWEI"),
                    db_data.get("ZAIZHIXUELI"),
                    db_data.get("ZAIZHIYUANXIAO"),
                    db_data.get("ZAIZHIZHUANYE"),
                    db_data.get("PPSJ"),
                    db_data.get("YGXZ"),
                    db_data.get("ZAIZHIXUEWEI"),
                    db_data.get("DANGANZHENGLIREN"),
                    db_data.get("SHUZIHUACAIJIREN"),
                    db_data.get("DANGANJUANSHU"),
                    db_data.get("BAOSONGRIQI"),
                    db_data.get("DANGANSHENHEREN"),
                    db_data.get("SHUZIHUASHENHEREN"),
                    db_data.get("BAOSONGDANWEI"),
                    db_data.get("QINGKUANSHUOMI"),
                    db_data.get("CS"),
                    db_data.get("DJYY"),
                    data.get("柜号"),
                    data.get("层号"),
                ),
            )
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        logger.error(f"保存失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
def person_basic_view(request):
    return render(request, "archives/person_basic.html")


@login_required
def person_salary_view(request):
    return render(request, "archives/person_salary.html")
