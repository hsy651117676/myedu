"""
机构与人员维护
"""

import json
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.utils import _get_conn
from main.utils.decorators import admin_required

logger = logging.getLogger(__name__)


@login_required
@admin_required
def page(request):
    return render(request, "archivesSystem/organization.html")


# ==================== 机构树 ====================


@login_required
@admin_required
def tree_api(request):
    """第一层：PID = -1，带子节点数和人员数"""
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.BM, d.BMMC, d.BMDM, d.SXH, d.PID,
                   (SELECT COUNT(*) FROM DEPART WHERE PID = d.BM) AS childCount,
                   (SELECT COUNT(*) FROM USERS_DEPARTMENT WHERE DEPARTMENTID = d.BM) AS personCount
            FROM DEPART d
            WHERE d.PID = -1
            ORDER BY d.SXH, d.BM
        """)
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        logger.error(f"获取机构树失败: {e}")
        return JsonResponse({"code": 500, "msg": "获取机构树失败"})
    finally:
        if conn:
            conn.close()


@login_required
@admin_required
def tree_children_api(request):
    """子节点，带子节点数和人员数"""
    pid = request.GET.get("pid")
    if pid is None:
        return JsonResponse({"code": 400, "msg": "缺少pid"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT d.BM, d.BMMC, d.BMDM, d.SXH, d.PID,
                   (SELECT COUNT(*) FROM DEPART WHERE PID = d.BM) AS childCount,
                   (SELECT COUNT(*) FROM USERS_DEPARTMENT WHERE DEPARTMENTID = d.BM) AS personCount
            FROM DEPART d
            WHERE d.PID = ?
            ORDER BY d.SXH, d.BM
        """,
            (int(pid),),
        )
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        logger.error(f"获取子节点失败: {e}")
        return JsonResponse({"code": 500, "msg": "获取子节点失败"})
    finally:
        if conn:
            conn.close()


# ==================== 机构操作 ====================


@login_required
@admin_required
@csrf_exempt
def save_api(request):
    """新增机构"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400, "msg": "参数格式错误"})

    bmmc = str(data.get("bmmc", "")).strip()
    bmdm = str(data.get("bmdm", "")).strip()
    pid = data.get("pid")
    sxh = data.get("sxh", 0)

    if not bmmc:
        return JsonResponse({"code": 400, "msg": "机构名称不能为空"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO DEPART (BMMC, BMDM, SXH, PID) VALUES (?, ?, ?, ?)",
            (bmmc, bmdm if bmdm else None, int(sxh) if sxh else 0, pid),
        )
        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "新增成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"新增机构失败: {e}")
        return JsonResponse({"code": 500, "msg": "新增机构失败"})
    finally:
        if conn:
            conn.close()


@login_required
@admin_required
@csrf_exempt
def delete_api(request):
    """删除机构"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400, "msg": "参数格式错误"})

    bm = data.get("bm")
    if bm is None:
        return JsonResponse({"code": 400, "msg": "缺少机构ID"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # 检查是否有子机构
        cursor.execute("SELECT COUNT(*) FROM DEPART WHERE PID = ?", (bm,))
        if cursor.fetchone()[0] > 0:
            cursor.close()
            return JsonResponse(
                {"code": 400, "msg": "该机构下有子机构，请先删除子机构"}
            )

        # 检查子树内是否有人
        all_dept_ids = set()
        _collect_sub_depts(conn, bm, all_dept_ids)
        if all_dept_ids:
            placeholders = ",".join("?" * len(all_dept_ids))
            cursor.execute(
                f"SELECT COUNT(*) FROM USERS_DEPARTMENT WHERE DEPARTMENTID IN ({placeholders})",
                tuple(all_dept_ids),
            )
            if cursor.fetchone()[0] > 0:
                cursor.close()
                return JsonResponse(
                    {"code": 400, "msg": "该机构或其子机构下有人员，无法删除"}
                )

        cursor.execute("DELETE FROM DEPART WHERE BM = ?", (bm,))
        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "删除成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"删除机构失败: {e}")
        return JsonResponse({"code": 500, "msg": "删除机构失败"})
    finally:
        if conn:
            conn.close()


def _collect_sub_depts(conn, bm, result_set):
    """递归收集所有子孙机构 BM"""
    result_set.add(bm)
    cursor = conn.cursor()
    cursor.execute("SELECT BM FROM DEPART WHERE PID = ?", (bm,))
    children = [row[0] for row in cursor.fetchall()]
    cursor.close()
    for child_bm in children:
        _collect_sub_depts(conn, child_bm, result_set)


# ==================== 人员操作 ====================


@login_required
@admin_required
def person_list_api(request):
    """获取机构下的人员列表"""
    bm = request.GET.get("bm")
    keyword = request.GET.get("keyword", "").strip()

    if bm is None:
        return JsonResponse({"code": 400, "msg": "缺少机构ID"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        sql = """
            SELECT r.RSID, r.XM, r.IDCARD, r.XB, r.CSNY
            FROM RS_INFO r
            INNER JOIN USERS_DEPARTMENT ud ON r.RSID = ud.RSID
            WHERE ud.DEPARTMENTID = ?
        """
        params = [int(bm)]

        if keyword:
            sql += " AND (r.XM LIKE ? OR r.IDCARD LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        sql += " ORDER BY ud.DEPARTMENTORDER, r.RSID"

        cursor.execute(sql, params)
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        logger.error(f"获取人员列表失败: {e}")
        return JsonResponse({"code": 500, "msg": "获取人员列表失败"})
    finally:
        if conn:
            conn.close()


@login_required
@admin_required
@csrf_exempt
def person_create_api(request):
    """新增人员"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400, "msg": "参数格式错误"})

    xm = str(data.get("xm", "")).strip()
    idcard = str(data.get("idcard", "")).strip()
    bm = data.get("bm")

    if not xm:
        return JsonResponse({"code": 400, "msg": "姓名不能为空"})
    if not idcard:
        return JsonResponse({"code": 400, "msg": "身份证号不能为空"})
    if len(idcard) != 18:
        return JsonResponse({"code": 400, "msg": "身份证号必须为18位"})
    if bm is None:
        return JsonResponse({"code": 400, "msg": "缺少所属机构"})

    # 解析性别和出生年月
    try:
        birth = idcard[6:14]
        csny = f"{birth[0:4]}-{birth[4:6]}-{birth[6:8]}"
        gender_code = int(idcard[16])
        xb = "男" if gender_code % 2 == 1 else "女"
    except:
        return JsonResponse({"code": 400, "msg": "身份证号格式不正确"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # 检查身份证号是否已存在
        cursor.execute("SELECT COUNT(*) FROM RS_INFO WHERE IDCARD = ?", (idcard,))
        if cursor.fetchone()[0] > 0:
            cursor.close()
            return JsonResponse({"code": 400, "msg": "该身份证号已存在"})

        # 插入人员
        cursor.execute(
            "INSERT INTO RS_INFO (XM, IDCARD, XB, CSNY) VALUES (?, ?, ?, ?)",
            (xm, idcard, xb, csny),
        )

        # 获取自增 RSID
        cursor.execute("SELECT @@IDENTITY")
        rsid = cursor.fetchone()[0]

        # 插入部门关联
        cursor.execute(
            "INSERT INTO USERS_DEPARTMENT (RSID, DEPARTMENTID, DEPARTMENTORDER) VALUES (?, ?, ?)",
            (rsid, bm, 0),
        )

        # 创建档案文件表
        cursor.execute(f"""
            CREATE TABLE RS_DESCRIPT_{rsid} (
                Archid int NULL,
                Length int NULL,
                Path varchar(50) NULL,
                Pdfkey varchar(64) NULL,
                Sxh int NULL,
                Oldfilename varchar(60) NULL,
                Newfilename varchar(60) NULL,
                uptime datetime NULL,
                GaoQingLength int NULL,
                GAOQINGPDFKEY varchar(100) NULL
            )
        """)

        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "新增成功", "rsid": rsid})
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"新增人员失败: {e}")
        return JsonResponse({"code": 500, "msg": "新增人员失败"})
    finally:
        if conn:
            conn.close()


@login_required
@admin_required
@csrf_exempt
def person_batch_create_api(request):
    """批量新增人员"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400, "msg": "参数格式错误"})

    bm = data.get("bm")
    rows = data.get("rows", [])  # [{xm, idcard}, ...]

    if bm is None:
        return JsonResponse({"code": 400, "msg": "缺少所属机构"})
    if not rows:
        return JsonResponse({"code": 400, "msg": "没有人员数据"})

    # 解析并校验
    persons = []
    seen_ids = set()
    errors = []

    for i, row in enumerate(rows):
        xm = str(row.get("xm", "")).strip()
        idcard = str(row.get("idcard", "")).strip()

        if not xm and not idcard:
            continue  # 空行跳过

        if not xm:
            errors.append(f"第{i + 1}行：姓名不能为空")
            continue
        if not idcard:
            errors.append(f"第{i + 1}行（{xm}）：身份证号不能为空")
            continue
        if len(idcard) != 18:
            errors.append(f"第{i + 1}行（{xm}）：身份证号必须为18位")
            continue
        if idcard in seen_ids:
            errors.append(f"第{i + 1}行（{xm}）：身份证号在本次批量数据中重复")
            continue

        # 解析性别和出生年月
        try:
            birth = idcard[6:14]
            csny = f"{birth[0:4]}-{birth[4:6]}-{birth[6:8]}"
            gender_code = int(idcard[16])
            xb = "男" if gender_code % 2 == 1 else "女"
        except:
            errors.append(f"第{i + 1}行（{xm}）：身份证号格式不正确")
            continue

        seen_ids.add(idcard)
        persons.append({"xm": xm, "idcard": idcard, "xb": xb, "csny": csny})

    if not persons:
        return JsonResponse({"code": 400, "msg": "没有有效的人员数据"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # 检查所有身份证号是否在数据库已存在
        duplicate_ids = []
        for p in persons:
            cursor.execute(
                "SELECT COUNT(*) FROM RS_INFO WHERE IDCARD = ?", (p["idcard"],)
            )
            if cursor.fetchone()[0] > 0:
                duplicate_ids.append(f"{p['xm']}({p['idcard']})")

        if duplicate_ids:
            cursor.close()
            return JsonResponse(
                {
                    "code": 400,
                    "msg": f"以下人员身份证号已存在：{', '.join(duplicate_ids)}",
                }
            )

        # 获取机构名称
        cursor.execute("SELECT BMMC FROM DEPART WHERE BM = ?", (bm,))
        dept_row = cursor.fetchone()
        bmmc = dept_row[0] if dept_row else ""

        success_count = 0
        for p in persons:
            cursor.execute(
                "INSERT INTO RS_INFO (XM, IDCARD, XB, CSNY) VALUES (?, ?, ?, ?)",
                (p["xm"], p["idcard"], p["xb"], p["csny"]),
            )
            cursor.execute("SELECT @@IDENTITY")
            rsid = cursor.fetchone()[0]

            cursor.execute(
                "INSERT INTO USERS_DEPARTMENT (RSID, DEPARTMENTID, DEPARTMENTORDER) VALUES (?, ?, ?)",
                (rsid, bm, 0),
            )

            cursor.execute(f"""
                CREATE TABLE RS_DESCRIPT_{rsid} (
                    Archid int NULL,
                    Length int NULL,
                    Path varchar(50) NULL,
                    Pdfkey varchar(64) NULL,
                    Sxh int NULL,
                    Oldfilename varchar(60) NULL,
                    Newfilename varchar(60) NULL,
                    uptime datetime NULL,
                    GaoQingLength int NULL,
                    GAOQINGPDFKEY varchar(100) NULL
                )
            """)
            success_count += 1

        conn.commit()
        cursor.close()
        return JsonResponse(
            {
                "code": 0,
                "msg": f"成功添加 {success_count} 人",
                "count": success_count,
                "errors": errors,
            }
        )
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"批量新增人员失败: {e}")
        return JsonResponse({"code": 500, "msg": "批量新增人员失败"})
    finally:
        if conn:
            conn.close()
