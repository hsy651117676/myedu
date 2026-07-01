"""
档案目录批量添加
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
    return render(request, "archivesSystem/batch.html")


@login_required
@admin_required
def unit_persons_api(request):
    """获取单位下人员列表"""
    unit_id = request.GET.get("unitId", "")
    if not unit_id:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT RS_INFO.RSID, XM AS 姓名, DEPART.BMMC AS 单位
            FROM USERS_DEPARTMENT
            LEFT JOIN RS_INFO ON USERS_DEPARTMENT.RSID = RS_INFO.RSID
            LEFT JOIN DEPART ON USERS_DEPARTMENT.DEPARTMENTID = DEPART.BM
            WHERE USERS_DEPARTMENT.DEPARTMENTID = ?
            ORDER BY RS_INFO.RYBH
        """, (unit_id,))
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
def category_list_api(request):
    """获取材料类别列表，按档案目录顺序排列，排除4和9大类"""
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT FL, JBBH + '：' + FLSM AS display_name "
            "FROM CATETREE WHERE FL NOT IN (4, 9) ORDER BY ORDERNUM"
        )
        rows = [{"fl": r[0], "display_name": r[1]} for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@admin_required
def existing_count_api(request):
    """获取已勾选人员在指定类别下的已有数量和下一个序号"""
    rsids = request.GET.get("rsids", "")
    fl = request.GET.get("fl", "")
    if not rsids or not fl:
        return JsonResponse({"code": 400})

    ids = [x.strip() for x in rsids.split(",") if x.strip()]

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        result = {}
        for rsid in ids:
            cursor.execute(
                "SELECT COUNT(*), ISNULL(MAX(XH), 0) FROM RS_ARCHINFO WHERE RSID=? AND FL=?",
                (int(rsid), int(fl))
            )
            cnt, max_xh = cursor.fetchone()
            result[rsid] = {"count": cnt, "next_xh": max_xh + 1}
        cursor.close()
        return JsonResponse({"code": 0, "data": result})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@admin_required
def jbbh_api(request):
    """根据FL获取JBBH，用于拼接预览编号"""
    fl = request.GET.get("fl", "")
    if not fl:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT JBBH FROM CATETREE WHERE FL=?", (int(fl),))
        row = cursor.fetchone()
        cursor.close()
        if row:
            return JsonResponse({"code": 0, "jbbh": row[0]})
        return JsonResponse({"code": 404, "msg": "类别不存在"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@admin_required
@csrf_exempt
def batch_insert_api(request):
    """批量插入材料"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    rsids = data.get("rsids", [])
    fl = int(data.get("fl", 0))
    year = data.get("year", None)
    month = data.get("month", None)
    day = data.get("day", None)
    ys = data.get("ys", None)
    bz = data.get("bz", "")
    cltm = data.get("cltm", "")
    if fl <= 0:
        return JsonResponse({"code": 400, "msg": "请选择有效的材料类别"})
    if not rsids or not fl or not year or not month or not day or not ys or not cltm:
        return JsonResponse({"code": 400, "msg": "参数不完整"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        count = 0

        for rsid in rsids:
            cursor.execute(
                "SELECT ISNULL(MAX(XH),0) FROM RS_ARCHINFO WHERE RSID=? AND FL=?",
                (int(rsid), fl)
            )
            xh = cursor.fetchone()[0] + 1

            cursor.execute("""
                INSERT INTO RS_ARCHINFO (RSID, BZ, CLTM, FL, XH, YS, FYEAR, FMONTH, FDAY, ADDTIME)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
            """, (int(rsid), bz, cltm, fl, xh, ys, year, month, day))
            count += 1

        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": f"成功为 {count} 人添加材料,请回到档案人员维护——档案目录中进行查看。注意：请不要重复插入！"})
    except Exception as e:
        if conn:
            conn.rollback()
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
