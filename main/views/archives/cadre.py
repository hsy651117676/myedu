"""干部任免审批表"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.utils import _get_conn
import json
import logging
import base64
import os
from io import BytesIO
from urllib.parse import quote
from django.conf import settings
import openpyxl
from main.utils.decorators import archive_perm_required
from django.http import HttpResponse
import pyodbc
from main.utils.date_utils import birth_with_age
from openpyxl.styles import Alignment, Font, Border, Side
from main.utils.string_utils import wrap_text

logger = logging.getLogger(__name__)


def _get_yhbh(request):
    try:
        return request.user.profile.yhbh or 0
    except:
        return 0


def _find_cadre_photo(rsid, cadre_id):
    """
    三层查找任免表照片：
      1. PERSON/{rsid}/IMG/{cadre_id}.jpg   （本表自己的照片）
      2. PERSON/{rsid}/IMG/001.jpg          （人员照片兜底）
    返回文件路径或 None
    """
    base_dir = os.path.join(
        settings.SCAN_IMAGE_BASE_DIR,
        "PERSON",
        str(rsid).zfill(8),
        "IMG",
    )
    for fname in (f"{cadre_id}.jpg", "001.jpg"):
        p = os.path.join(base_dir, fname)
        if os.path.exists(p):
            return p
    return None


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
        cursor.close()

        # 照片：从文件系统三层查找，返回 base64
        data["DQZP"] = ""
        photo_path = _find_cadre_photo(rsid, cadre_id)
        if photo_path:
            with open(photo_path, "rb") as f:
                data["DQZP"] = base64.b64encode(f.read()).decode()

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

    # 字段截断
    FIELD_LIMITS = {
        "CSNY": 20,
        "JG": 50,
        "JRSJ": 20,
        "JL": 2000,
        "MZ": 20,
        "XB": 20,
        "XM": 50,
        "ZZMM": 20,
        "BMMC": 50,
        "HEALTH": 10,
        "ZHUANYEJISHUZHIWU": 50,
        "XIANRENZHIWU": 1000,
        "NIRENZHIWU": 1000,
        "NIMIANZHIWU": 1000,
        "JIANGCHENGQINGKUANG": 1000,
        "YEARCHECK": 1000,
        "RENMIANREASON": 50,
        "CHENGBAODANWEI": 1000,
        "SHENPIJIGUANYIJIAN": 1000,
        "CHUSHENGDI": 180,
        "WORKTIME": 20,
        "QUANRIZIJIAOYU": 50,
        "QUANRIZIYXZY": 100,
        "ZAIZHIJIAOYU": 50,
        "ZAIZHIYXZY": 100,
        "NL": 10,
        "ZHUANCHANG": 50,
        "XZJGYJ": 2000,
    }
    for field, limit in FIELD_LIMITS.items():
        if field in data and isinstance(data[field], str) and len(data[field]) > limit:
            data[field] = data[field][:limit]

    # 照片写文件（仅当有有效 id，不碰 DQZP 字段）
    dqzp = data.get("DQZP", "")
    if dqzp and isinstance(dqzp, str) and cadre_id and int(cadre_id) > 0:
        if "," in dqzp:
            dqzp = dqzp.split(",", 1)[1]
        try:
            dqzp_bytes = base64.b64decode(dqzp)
            base_dir = os.path.join(
                settings.SCAN_IMAGE_BASE_DIR,
                "PERSON",
                str(rsid).zfill(8),
                "IMG",
            )
            os.makedirs(base_dir, exist_ok=True)
            with open(os.path.join(base_dir, f"{cadre_id}.jpg"), "wb") as f:
                f.write(dqzp_bytes)
        except Exception as e:
            logger.error(f"照片保存失败: {e}")

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
                "INSERT INTO CADREAPPROVE (RSID, CSNY, JG, JRSJ, JL, MZ, XB, XM, ZZMM, BMMC, HEALTH, ZHUANYEJISHUZHIWU, XIANRENZHIWU, NIRENZHIWU, NIMIANZHIWU, JIANGCHENGQINGKUANG, YEARCHECK, RENMIANREASON, CHENGBAODANWEI, SHENPIJIGUANYIJIAN, CHENGWEI1, XINGMING1, NIANLING1, ZHENGZHIMIANMAO1, UNITANDZHIWU1, CHENGWEI2, XINGMING2, NIANLING2, ZHENGZHIMIANMAO2, UNITANDZHIWU2, CHENGWEI3, XINGMING3, NIANLING3, ZHENGZHIMIANMAO3, UNITANDZHIWU3, CHENGWEI4, XINGMING4, NIANLING4, ZHENGZHIMIANMAO4, UNITANDZHIWU4, CHENGWEI5, XINGMING5, NIANLING5, ZHENGZHIMIANMAO5, UNITANDZHIWU5, CHENGWEI6, XINGMING6, NIANLING6, ZHENGZHIMIANMAO6, UNITANDZHIWU6, CHENGWEI7, XINGMING7, NIANLING7, ZHENGZHIMIANMAO7, UNITANDZHIWU7, ZHUANCHANG, XZJGYJ, CHUSHENGDI, WORKTIME, QUANRIZIJIAOYU, QUANRIZIYXZY, ZAIZHIJIAOYU, ZAIZHIYXZY, NL, CSNY1, CSNY2, CSNY3, CSNY4, CSNY5, CSNY6, CSNY7) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    int(rsid),
                    data.get("CSNY", ""),
                    data.get("JG", ""),
                    data.get("JRSJ", ""),
                    data.get("JL", ""),
                    data.get("MZ", ""),
                    data.get("XB", ""),
                    data.get("XM", ""),
                    data.get("ZZMM", ""),
                    data.get("BMMC", "干部任免审批表"),
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
                ),
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
        return JsonResponse({"code": 0, "data": rows, "new_id": new_id})
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
                   ZYZC AS ZHUANYEJISHUZHIWU, '' AS NL, '' AS JRSJ, '' AS HEALTH,
                   '' AS NIRENZHIWU, '' AS NIMIANZHIWU, '' AS ZHUANCHANG, '' AS XZJGYJ
            FROM RS_INFO WHERE RSID=?
        """,
            (int(rsid),),
        )
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        data = dict(zip(cols, row)) if row else {}

        # 家庭成员
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

        # 简历、奖惩、年度考核
        cursor.execute(
            "{CALL Z_supplement_EDIT(?, ?, '', '', '', 'SELECT')}",
            (int(rsid), _get_yhbh(request)),
        )
        cols2 = [col[0] for col in cursor.description]
        supp = cursor.fetchone()
        if supp:
            supp_data = dict(zip(cols2, supp))
            data["JL"] = supp_data.get("resume", "")
            data["JIANGCHENGQINGKUANG"] = supp_data.get("reward", "")
            data["YEARCHECK"] = supp_data.get("assessmentResults", "")

        # 照片不从数据库返回，前端自动 fallback 到 001.jpg
        data["DQZP"] = ""

        cursor.close()
        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def cadre_export_api(request):
    rsid = request.GET.get("rsid", "")
    cadre_id = request.GET.get("id", "0")
    export_type = request.GET.get("type", "normal")
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
        cursor.close()
    finally:
        if conn:
            conn.close()

    template_path = os.path.join(
        settings.BASE_DIR, "static", "excel_templates", "干部任免审批表.xlsx"
    )
    wb = openpyxl.load_workbook(template_path)
    ws = wb["干部任免审批表"]

    if export_type == "special":
        ws["A1"] = "全国干部人事档案专项审核专用"

    def gv(k, d=""):
        v = data.get(k)
        return str(v) if v is not None else str(d)

    ws["C4"] = gv("XM")
    ws["E4"] = gv("XB")
    ws["H4"] = birth_with_age(gv("CSNY"))
    ws["H4"].alignment = Alignment(wrap_text=True, vertical="center")
    ws["C5"] = gv("MZ")
    ws["E5"] = gv("JG")
    ws["H5"] = gv("CHUSHENGDI")
    ws["C6"] = gv("ZZMM")
    ws["E6"] = gv("WORKTIME")
    ws["H6"] = gv("HEALTH")
    ws["C7"] = gv("ZHUANYEJISHUZHIWU")
    ws["F7"] = gv("ZHUANCHANG")
    ws["D8"] = gv("QUANRIZIJIAOYU")
    ws["H8"] = gv("QUANRIZIYXZY")
    ws["D9"] = gv("ZAIZHIJIAOYU")
    ws["H9"] = gv("ZAIZHIYXZY")
    ws["D10"] = gv("XIANRENZHIWU")
    ws["D11"] = gv("NIRENZHIWU")
    ws["D12"] = gv("NIMIANZHIWU")
    ws["B13"] = wrap_text(gv("JL"))
    ws["B13"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["B14"] = gv("JIANGCHENGQINGKUANG")
    ws["B15"] = gv("YEARCHECK")
    ws["B16"] = gv("RENMIANREASON")
    for i in range(1, 8):
        r = 17 + i
        ws.cell(row=r, column=2).value = gv(f"CHENGWEI{i}")
        ws.cell(row=r, column=4).value = gv(f"XINGMING{i}")
        ws.cell(row=r, column=5).value = birth_with_age(gv(f"CSNY{i}"))
        ws.cell(row=r, column=5).alignment = Alignment(
            wrap_text=True, vertical="center"
        )
        ws.cell(row=r, column=6).value = gv(f"ZHENGZHIMIANMAO{i}")
        ws.cell(row=r, column=8).value = gv(f"UNITANDZHIWU{i}")
    ws["B25"] = gv("CHENGBAODANWEI")
    ws["B26"] = gv("SHENPIJIGUANYIJIAN")
    ws["H26"] = gv("XZJGYJ")

    # 插入照片到 I4（合并单元格 I4:I7）
    zp_path = _find_cadre_photo(rsid, cadre_id)
    if zp_path:
        try:
            from openpyxl.drawing.image import Image
            from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, TwoCellAnchor

            img = Image(zp_path)
            img.anchor = TwoCellAnchor(
                _from=AnchorMarker(col=8, colOff=0, row=3, rowOff=0),
                to=AnchorMarker(col=9, colOff=0, row=7, rowOff=0),
            )
            img.anchor.editAs = "twoCell"
            ws.add_image(img)
        except Exception as e:
            print(f"插入照片失败: {e}")

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = HttpResponse(
        buf,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    if export_type == "special":
        filename = f"{gv('XM')}_专审_干部任免审批表.xlsx"
    else:
        filename = f"{gv('XM')}_干部任免审批表.xlsx"
    resp["Content-Disposition"] = f"attachment; filename={quote(filename)}"
    return resp
