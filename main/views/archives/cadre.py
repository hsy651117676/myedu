from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.db_utils import _get_conn
import json
import logging
import base64
from main.decorators import archive_perm_required
#@archive_perm_required

logger = logging.getLogger(__name__)


def _get_yhbh(request):
    try:
        return request.user.profile.yhbh or 0
    except:
        return 0


@login_required
@archive_perm_required
def person_cadre_view(request):
    return render(request, "archives/person_cadre.html")


@login_required
def cadre_list_api(request):
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ID, BMMC AS 名称, XM AS 姓名, XIANRENZHIWU AS 现任职务 FROM CADREAPPROVE WHERE RSID=? ORDER BY ID",
            (int(rsid),),
        )
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
def cadre_detail_api(request):
    rsid = request.GET.get("rsid", "")
    cadre_id = request.GET.get("id", "0")
    if not rsid or not cadre_id:
        return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM CADREAPPROVE WHERE ID=?", (int(cadre_id),))
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        data = dict(zip(cols, row)) if row else {}
        if data.get("DQZP"):
            data["DQZP"] = (
                base64.b64encode(data["DQZP"]).decode()
                if isinstance(data["DQZP"], bytes)
                else ""
            )
        cursor.close()
        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@csrf_exempt
def cadre_save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})
    rsid = data.get("rsid")
    cadre_id = data.get("id", 0)
    if not rsid:
        return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        if int(cadre_id) > 0:
            cursor.execute(
                "UPDATE CADREAPPROVE SET CSNY=?, JG=?, JRSJ=?, JL=?, MZ=?, XB=?, XM=?, ZZMM=?, BMMC=?, HEALTH=?, ZHUANYEJISHUZHIWU=?, XIANRENZHIWU=?, NIRENZHIWU=?, NIMIANZHIWU=?, JIANGCHENGQINGKUANG=?, YEARCHECK=?, RENMIANREASON=?, CHENGBAODANWEI=?, SHENPIJIGUANYIJIAN=?, CHENGWEI1=?, XINGMING1=?, NIANLING1=?, ZHENGZHIMIANMAO1=?, UNITANDZHIWU1=?, CHENGWEI2=?, XINGMING2=?, NIANLING2=?, ZHENGZHIMIANMAO2=?, UNITANDZHIWU2=?, CHENGWEI3=?, XINGMING3=?, NIANLING3=?, ZHENGZHIMIANMAO3=?, UNITANDZHIWU3=?, CHENGWEI4=?, XINGMING4=?, NIANLING4=?, ZHENGZHIMIANMAO4=?, UNITANDZHIWU4=?, CHENGWEI5=?, XINGMING5=?, NIANLING5=?, ZHENGZHIMIANMAO5=?, UNITANDZHIWU5=?, CHENGWEI6=?, XINGMING6=?, NIANLING6=?, ZHENGZHIMIANMAO6=?, UNITANDZHIWU6=?, CHENGWEI7=?, XINGMING7=?, NIANLING7=?, ZHENGZHIMIANMAO7=?, UNITANDZHIWU7=?, ZHUANCHANG=?, XZJGYJ=?, CHUSHENGDI=?, WORKTIME=?, QUANRIZIJIAOYU=?, QUANRIZIYXZY=?, ZAIZHIJIAOYU=?, ZAIZHIYXZY=?, NL=?, CSNY1=?, CSNY2=?, CSNY3=?, CSNY4=?, CSNY5=?, CSNY6=?, CSNY7=? WHERE ID=?",
                (
                    data.get("CSNY", ""),
                    data.get("JG", ""),
                    data.get("JRSJ", ""),
                    data.get("JL", ""),
                    data.get("MZ", ""),
                    data.get("XB", ""),
                    data.get("XM", ""),
                    data.get("ZZMM", ""),
                    data.get("BMMC", ""),
                    data.get("HEALTH", ""),
                    data.get("ZHUANYEJISHUZHIWU", ""),
                    data.get("XIANRENZHIWU", ""),
                    data.get("NIRENZHIWU", ""),
                    data.get("NIMIANZHIWU", ""),
                    data.get("JIANGCHENGQINGKUANG", ""),
                    data.get("YEARCHECK", ""),
                    data.get("RENMIANREASON", ""),
                    data.get("CHENGBAODANWEI", ""),
                    data.get("SHENPIJIGUANYIJIAN", ""),
                    data.get("CHENGWEI1", ""),
                    data.get("XINGMING1", ""),
                    data.get("NIANLING1", ""),
                    data.get("ZHENGZHIMIANMAO1", ""),
                    data.get("UNITANDZHIWU1", ""),
                    data.get("CHENGWEI2", ""),
                    data.get("XINGMING2", ""),
                    data.get("NIANLING2", ""),
                    data.get("ZHENGZHIMIANMAO2", ""),
                    data.get("UNITANDZHIWU2", ""),
                    data.get("CHENGWEI3", ""),
                    data.get("XINGMING3", ""),
                    data.get("NIANLING3", ""),
                    data.get("ZHENGZHIMIANMAO3", ""),
                    data.get("UNITANDZHIWU3", ""),
                    data.get("CHENGWEI4", ""),
                    data.get("XINGMING4", ""),
                    data.get("NIANLING4", ""),
                    data.get("ZHENGZHIMIANMAO4", ""),
                    data.get("UNITANDZHIWU4", ""),
                    data.get("CHENGWEI5", ""),
                    data.get("XINGMING5", ""),
                    data.get("NIANLING5", ""),
                    data.get("ZHENGZHIMIANMAO5", ""),
                    data.get("UNITANDZHIWU5", ""),
                    data.get("CHENGWEI6", ""),
                    data.get("XINGMING6", ""),
                    data.get("NIANLING6", ""),
                    data.get("ZHENGZHIMIANMAO6", ""),
                    data.get("UNITANDZHIWU6", ""),
                    data.get("CHENGWEI7", ""),
                    data.get("XINGMING7", ""),
                    data.get("NIANLING7", ""),
                    data.get("ZHENGZHIMIANMAO7", ""),
                    data.get("UNITANDZHIWU7", ""),
                    data.get("ZHUANCHANG", ""),
                    data.get("XZJGYJ", ""),
                    data.get("CHUSHENGDI", ""),
                    data.get("WORKTIME", ""),
                    data.get("QUANRIZIJIAOYU", ""),
                    data.get("QUANRIZIYXZY", ""),
                    data.get("ZAIZHIJIAOYU", ""),
                    data.get("ZAIZHIYXZY", ""),
                    data.get("NL", ""),
                    data.get("csny1", ""),
                    data.get("csny2", ""),
                    data.get("csny3", ""),
                    data.get("csny4", ""),
                    data.get("csny5", ""),
                    data.get("csny6", ""),
                    data.get("csny7", ""),
                    int(cadre_id),
                ),
            )
        else:
            cursor.execute(
                "INSERT INTO CADREAPPROVE (RSID, XM, BMMC) VALUES (?, '', '干部任免审批表')",
                (int(rsid),),
            )
        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        logger.error(f"任免表保存失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def cadre_add_api(request):
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT ISNULL(MAX(ID),0)+1 FROM CADREAPPROVE")
        new_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO CADREAPPROVE (ID, RSID, XM, BMMC) VALUES (?, ?, '', '干部任免审批表')",
            (new_id, int(rsid)),
        )
        conn.commit()
        cursor.execute(
            "SELECT ID, BMMC AS 名称, XM AS 姓名, XIANRENZHIWU AS 现任职务 FROM CADREAPPROVE WHERE RSID=? ORDER BY ID",
            (int(rsid),),
        )
        rows = [
            dict(zip([col[0] for col in cursor.description], r))
            for r in cursor.fetchall()
        ]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def cadre_delete_api(request):
    rsid = request.GET.get("rsid", "")
    cadre_id = request.GET.get("id", "0")
    if not rsid or not cadre_id:
        return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM CADREAPPROVE WHERE ID=?", (int(cadre_id),))
        conn.commit()
        cursor.execute(
            "SELECT ID, BMMC AS 名称, XM AS 姓名, XIANRENZHIWU AS 现任职务 FROM CADREAPPROVE WHERE RSID=? ORDER BY ID",
            (int(rsid),),
        )
        rows = [
            dict(zip([col[0] for col in cursor.description], r))
            for r in cursor.fetchall()
        ]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def cadre_extract_api(request):
    rsid = request.GET.get("rsid", "")
    cadre_id = request.GET.get("id", "0")
    if not rsid or not cadre_id:
        return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT XM, XB, MZ, JG, CHUSHENGDI, CSNY, WORKTIME, ZZMM, JOBUNIT AS XIANRENZHIWU,
                   QUANRIZIXUELI + CHAR(13)+CHAR(10) + ISNULL(QUANRIZIXUEWEI,'') AS QUANRIZIJIAOYU,
                   QUANRIZIYUANXIAO + CHAR(13)+CHAR(10) + ISNULL(QUANRIZIZHUANYE,'') AS QUANRIZIYXZY,
                   ZAIZHIXUELI + CHAR(13)+CHAR(10) + ISNULL(ZAIZHIXUEWEI,'') AS ZAIZHIJIAOYU,
                   ZAIZHIYUANXIAO + CHAR(13)+CHAR(10) + ISNULL(ZAIZHIZHUANYE,'') AS ZAIZHIYXZY,
                   JL, ZYZC AS ZHUANYEJISHUZHIWU, '' AS NL, '' AS JRSJ, '' AS HEALTH,
                   '' AS NIRENZHIWU, '' AS NIMIANZHIWU, '' AS JIANGCHENGQINGKUANG, '' AS YEARCHECK,
                   '' AS RENMIANREASON, '' AS CHENGBAODANWEI, '' AS SHENPIJIGUANYIJIAN,
                   '' AS ZHUANCHANG, '' AS XZJGYJ
            FROM RS_INFO WHERE RSID=?
        """,
            (int(rsid),),
        )
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        data = dict(zip(cols, row)) if row else {}
        for i in range(1, 8):
            cursor.execute(
                "SELECT appellation, name, csny, PoliticalLandscape, workUnit FROM Z_FamilyMembers WHERE rsid=? AND serialNumber=?",
                (int(rsid), i),
            )
            fm = cursor.fetchone()
            if fm:
                data[f"CHENGWEI{i}"] = fm[0] or ""
                data[f"XINGMING{i}"] = fm[1] or ""
                data[f"csny{i}"] = fm[2] or ""
                data[f"ZHENGZHIMIANMAO{i}"] = fm[3] or ""
                data[f"UNITANDZHIWU{i}"] = fm[4] or ""
        if data.get("DQZP"):
            data["DQZP"] = (
                base64.b64encode(data["DQZP"]).decode()
                if isinstance(data["DQZP"], bytes)
                else ""
            )
        cursor.close()
        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
