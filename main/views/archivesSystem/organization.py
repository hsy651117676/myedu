"""
机构维护 - 树形展示、拖拽排序、右键菜单、弹窗编辑
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


@login_required
@admin_required
def tree_api(request):
    """第一层分组 PID=-1"""
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT BM, BMMC, BMDM, PID, SXH FROM DEPART WHERE PID=-1 ORDER BY SXH, BM"
        )
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@admin_required
def tree_children_api(request):
    """子节点"""
    pid = request.GET.get("pid", "")
    if not pid:
        return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT BM, BMMC, BMDM, PID, SXH FROM DEPART WHERE PID=? ORDER BY SXH, BM",
            (pid,)
        )
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@admin_required
def detail_api(request):
    """机构详情"""
    bm = request.GET.get("bm", "")
    if not bm:
        return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT BM, BMMC, BMDM, PID, SXH FROM DEPART WHERE BM=?", (bm,)
        )
        cols = [c[0] for c in cursor.description]
        row = cursor.fetchone()
        cursor.close()
        if row:
            data = dict(zip(cols, row))
            # 查上级名称
            if data.get("PID") and data["PID"] != -1:
                cursor = conn.cursor()
                cursor.execute("SELECT BMMC FROM DEPART WHERE BM=?", (str(data["PID"]),))
                pr = cursor.fetchone()
                data["parent_name"] = pr[0] if pr else ""
                cursor.close()
            else:
                data["parent_name"] = ""
            return JsonResponse({"code": 0, "data": data})
        return JsonResponse({"code": 404, "msg": "机构不存在"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@admin_required
@csrf_exempt
def save_api(request):
    """新增或更新"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400, "msg": "参数格式错误"})

    action = data.get("action", "update")
    bm = str(data.get("bm", "")).strip()
    bmmc = str(data.get("bmmc", "")).strip()
    bmdm = str(data.get("bmdm", "")).strip()
    pid = str(data.get("pid", "")).strip()
    sxh = data.get("sxh", 0)

    if not bmmc:
        return JsonResponse({"code": 400, "msg": "机构名称不能为空"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if action == "create":
            cursor.execute("SELECT ISNULL(MAX(BM),0)+1 FROM DEPART")
            new_bm = str(cursor.fetchone()[0])
            cursor.execute(
                "INSERT INTO DEPART (BM, BMMC, BMDM, PID, SXH) VALUES (?,?,?,?,?)",
                (new_bm, bmmc, bmdm, pid, int(sxh) if sxh else 0)
            )
            conn.commit()
            cursor.close()
            return JsonResponse({"code": 0, "msg": "新增成功", "bm": new_bm})
        else:
            if not bm:
                return JsonResponse({"code": 400, "msg": "缺少机构ID"})
            cursor.execute(
                "UPDATE DEPART SET BMMC=?, BMDM=?, SXH=? WHERE BM=?",
                (bmmc, bmdm, int(sxh) if sxh else 0, bm)
            )
            conn.commit()
            cursor.close()
            return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        return JsonResponse({"code": 500, "msg": str(e)})
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
        return JsonResponse({"code": 400})

    bm = str(data.get("bm", "")).strip()
    if not bm:
        return JsonResponse({"code": 400, "msg": "缺少机构ID"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM DEPART WHERE PID=?", (bm,))
        if cursor.fetchone()[0] > 0:
            cursor.close()
            return JsonResponse({"code": 400, "msg": "该机构下有子机构，无法删除"})
        cursor.execute("SELECT COUNT(*) FROM USERS_DEPARTMENT WHERE DEPARTMENTID=?", (bm,))
        if cursor.fetchone()[0] > 0:
            cursor.close()
            return JsonResponse({"code": 400, "msg": "该机构下有人员，无法删除"})
        cursor.execute("DELETE FROM DEPART WHERE BM=?", (bm,))
        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "删除成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@admin_required
@csrf_exempt
def sort_api(request):
    """拖拽排序：批量更新SXH"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    items = data.get("items", [])
    if not items:
        return JsonResponse({"code": 400, "msg": "参数为空"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        for item in items:
            cursor.execute(
                "UPDATE DEPART SET SXH=? WHERE BM=?",
                (int(item.get("sxh", 0)), str(item.get("bm", "")))
            )
        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "排序保存成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
