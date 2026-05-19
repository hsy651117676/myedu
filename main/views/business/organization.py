"""
机构维护 - 独立模块
"""

import json
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.db_utils import _get_conn

logger = logging.getLogger(__name__)


@login_required
def organization_view(request):
    """机构维护页面"""
    return render(request, "business/organization.html")


@login_required
def person_search_api(request):
    """搜索人员（姓名/档案编号）"""
    keyword = request.GET.get("keyword", "").strip()
    if not keyword:
        return JsonResponse({"code": 400, "msg": "缺少关键词"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        keyword_safe = keyword.replace("'", "''")

        sql = f"""
            SELECT TOP 100 b.RSID, b.XM AS 姓名, d.BMMC AS 单位, 
                   b.RYBH AS 档案编号, y.GH AS 柜号, y.CH AS 层号
            FROM RS_INFO b
            LEFT JOIN USERS_DEPARTMENT ud ON b.RSID = ud.RSID
            LEFT JOIN DEPART d ON ud.DEPARTMENTID = d.BM
            LEFT JOIN YW_INFO y ON b.RSID = y.RSID
            WHERE b.XM LIKE N'%{keyword_safe}%' OR b.RYBH LIKE N'%{keyword_safe}%'
            ORDER BY b.RYBH
        """
        cursor.execute(sql)
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def person_detail_api(request):
    """获取人员详情及本单位人员"""
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少rsid"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT b.RSID, b.XM AS 姓名, b.RYBH AS 档案编号,
                      d.BMMC AS 单位, d.BM AS 单位ID,
                      y.GH AS 柜号, y.CH AS 层号
               FROM RS_INFO b
               LEFT JOIN USERS_DEPARTMENT ud ON b.RSID = ud.RSID
               LEFT JOIN DEPART d ON ud.DEPARTMENTID = d.BM
               LEFT JOIN YW_INFO y ON b.RSID = y.RSID
               WHERE b.RSID = ?""", (int(rsid),))

        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        if not row:
            return JsonResponse({"code": 404, "msg": "人员不存在"})

        person = dict(zip(cols, row))

        # 本单位人员
        bm = person.get("单位ID")
        unit_persons = []
        if bm:
            cursor.execute(
                """SELECT b.RSID, b.XM AS 姓名, d.BMMC AS 单位,
                          b.RYBH AS 档案编号, y.GH AS 柜号, y.CH AS 层号
                   FROM RS_INFO b
                   LEFT JOIN USERS_DEPARTMENT ud ON b.RSID = ud.RSID
                   LEFT JOIN DEPART d ON ud.DEPARTMENTID = d.BM
                   LEFT JOIN YW_INFO y ON b.RSID = y.RSID
                   WHERE d.BM = ? ORDER BY b.RYBH, b.XM""", (bm,))

            cols2 = [col[0] for col in cursor.description]
            unit_persons = [dict(zip(cols2, r)) for r in cursor.fetchall()]

        # 所有单位列表（供调转选择）
        cursor.execute("SELECT BM AS id, BMMC AS name FROM DEPART ORDER BY BM")
        cols3 = [col[0] for col in cursor.description]
        depart_list = [dict(zip(cols3, r)) for r in cursor.fetchall()]

        cursor.close()

        return JsonResponse({
            "code": 0,
            "data": {
                "person": person,
                "unitPersons": unit_persons,
                "departList": depart_list
            }
        })
    except Exception as e:
        logger.error(f"获取详情失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@csrf_exempt
def person_save_api(request):
    """保存档案编号、柜号、层号"""
    if request.method != "POST":
        return JsonResponse({"code": 405})

    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    rsid = data.get("rsid")
    rybh = data.get("rybh", "")
    gh = data.get("gh", "")
    ch = data.get("ch", "")

    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少rsid"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute("UPDATE RS_INFO SET RYBH = ? WHERE RSID = ?", (rybh, int(rsid)))

        cursor.execute("SELECT COUNT(*) FROM YW_INFO WHERE RSID = ?", (int(rsid),))
        if cursor.fetchone()[0] > 0:
            cursor.execute("UPDATE YW_INFO SET GH = ?, CH = ? WHERE RSID = ?",
                           (gh, ch, int(rsid)))
        else:
            cursor.execute("INSERT INTO YW_INFO (RSID, GH, CH) VALUES (?, ?, ?)",
                           (int(rsid), gh, ch))

        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        logger.error(f"保存失败: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@csrf_exempt
def person_transfer_api(request):
    """人员调转单位"""
    if request.method != "POST":
        return JsonResponse({"code": 405})

    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    rsid = data.get("rsid")
    new_bm = data.get("newBm")

    if not rsid or not new_bm:
        return JsonResponse({"code": 400, "msg": "缺少参数"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE USERS_DEPARTMENT SET DEPARTMENTID = ? WHERE RSID = ?",
            (int(new_bm), int(rsid)))
        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "调转成功"})
    except Exception as e:
        logger.error(f"调转失败: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
@login_required
def org_tree_api(request):
    """组织树根节点"""
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT TID, TNAME, PID, RSID, DABH, GH, CH FROM BMGL WHERE PID = -1 ORDER BY DABH, TID")
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def org_tree_children_api(request):
    """组织树子节点"""
    tid = request.GET.get("tid", "")
    if not tid:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT TID, TNAME, PID, RSID, DABH, GH, CH 
               FROM BMGL WHERE PID=? OR (TID=? AND PID=0) ORDER BY DABH, TID""",
            (tid, tid))
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def person_detail_api(request):
    """获取人员详情及4张表"""
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # 人员信息
        cursor.execute(
            """SELECT b.RSID, b.XM AS 姓名, b.RYBH AS 档案编号,
                      d.BMMC AS 单位, d.BM AS 单位ID,
                      y.GH AS 柜号, y.CH AS 层号
               FROM RS_INFO b
               LEFT JOIN USERS_DEPARTMENT ud ON b.RSID = ud.RSID
               LEFT JOIN DEPART d ON ud.DEPARTMENTID = d.BM
               LEFT JOIN YW_INFO y ON b.RSID = y.RSID
               WHERE b.RSID = ?""", (int(rsid),))
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        if not row:
            return JsonResponse({"code": 404})
        person = dict(zip(cols, row))

        bm = person.get("单位ID")
        xm = person.get("姓名", "")

        # 表1：本单位人员
        unit_persons = []
        if bm:
            cursor.execute(
                """SELECT b.RSID, b.XM AS 姓名, b.RYBH AS 档案编号, y.GH AS 柜号, y.CH AS 层号
                   FROM RS_INFO b
                   LEFT JOIN USERS_DEPARTMENT ud ON b.RSID = ud.RSID
                   LEFT JOIN DEPART d ON ud.DEPARTMENTID = d.BM
                   LEFT JOIN YW_INFO y ON b.RSID = y.RSID
                   WHERE d.BM = ? ORDER BY b.RYBH""", (bm,))
            cols2 = [col[0] for col in cursor.description]
            unit_persons = [dict(zip(cols2, r)) for r in cursor.fetchall()]

        # 表2：同姓人员（本单位）
        same_name_list = []
        first_char = xm[0] if xm else ""
        if bm and first_char:
            cursor.execute(
                """SELECT b.RSID, b.XM AS 姓名, b.RYBH AS 档案编号, y.GH AS 柜号, y.CH AS 层号
                   FROM RS_INFO b
                   LEFT JOIN USERS_DEPARTMENT ud ON b.RSID = ud.RSID
                   LEFT JOIN DEPART d ON ud.DEPARTMENTID = d.BM
                   LEFT JOIN YW_INFO y ON b.RSID = y.RSID
                   WHERE d.BM = ? AND b.XM LIKE N'?%' ORDER BY b.RYBH""",
                (bm, first_char))
            cols3 = [col[0] for col in cursor.description]
            same_name_list = [dict(zip(cols3, r)) for r in cursor.fetchall()]

        # 表3：姓氏编码
        cursor.execute(f"SELECT id, xs FROM Z_xsbm WHERE xs = N'{first_char}'")
        cols4 = [col[0] for col in cursor.description]
        xsbm_list = [dict(zip(cols4, r)) for r in cursor.fetchall()]

        # 表4：相邻姓氏编码
        near_xsbm_list = []
        if xsbm_list:
            xs_id = xsbm_list[0].get("id", 0)
            cursor.execute(
                f"SELECT id, xs FROM Z_xsbm WHERE id < {xs_id + 200} AND id > {xs_id - 200} ORDER BY id")
            cols5 = [col[0] for col in cursor.description]
            near_xsbm_list = [dict(zip(cols5, r)) for r in cursor.fetchall()]

        cursor.close()
        return JsonResponse({
            "code": 0,
            "data": {
                "person": person,
                "unitPersons": unit_persons,
                "sameNameList": same_name_list,
                "xsbmList": xsbm_list,
                "nearXsbmList": near_xsbm_list
            }
        })
    except Exception as e:
        logger.error(f"详情失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@csrf_exempt
def save_and_transfer_api(request):
    """保存并调转"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    rsid = data.get("rsid")
    rybh = data.get("rybh", "")
    gh = data.get("gh", "")
    ch = data.get("ch", "")
    new_bm = data.get("newBm")

    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少rsid"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute("UPDATE RS_INFO SET RYBH = ? WHERE RSID = ?", (rybh, int(rsid)))

        cursor.execute("SELECT COUNT(*) FROM YW_INFO WHERE RSID = ?", (int(rsid),))
        if cursor.fetchone()[0] > 0:
            cursor.execute("UPDATE YW_INFO SET GH = ?, CH = ? WHERE RSID = ?", (gh, ch, int(rsid)))
        else:
            cursor.execute("INSERT INTO YW_INFO (RSID, GH, CH) VALUES (?, ?, ?)", (int(rsid), gh, ch))

        if new_bm:
            cursor.execute("UPDATE USERS_DEPARTMENT SET DEPARTMENTID = ? WHERE RSID = ?",
                           (int(new_bm), int(rsid)))

        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "保存并调转成功"})
    except Exception as e:
        logger.error(f"操作失败: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
