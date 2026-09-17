"""人员基本信息"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from django.conf import settings
import json
import logging
import os
import pyodbc
from contextlib import contextmanager
from main.utils.field_maps import RS_INFO_MAP, to_frontend, to_backend
from main.utils import _get_conn
from main.utils.decorators import archive_perm_required
# @archive_perm_required

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
    archive_user = request.session.get("archive_user", {})
    if archive_user.get("yhbh"):
        return archive_user["yhbh"]
    try:
        return request.user.profile.yhbh
    except:
        return None


def _check_perm(request):
    return _get_yhbh(request) is not None


# ==================== 页面 ====================


@login_required
@archive_perm_required
def person_view(request):
    return render(request, "archives/person.html")


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
@archive_perm_required
def person_basic_view(request):
    return render(request, "archives/person_basic.html")


@login_required
@archive_perm_required
def person_salary_view(request):
    return render(request, "archives/person_salary.html")


@login_required
@csrf_exempt
def person_photo_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST"})

    rsid = request.POST.get("rsid")
    photo = request.FILES.get("photo")
    if not rsid or not photo:
        return JsonResponse({"code": 400, "msg": "缺少参数"})

    try:
        img_bytes = photo.read()

        # 原图落盘：{SCAN_IMAGE_BASE_DIR}/PERSON/{rsid}/IMG/001.jpg
        base_dir = os.path.join(
            settings.SCAN_IMAGE_BASE_DIR, "PERSON", str(rsid).zfill(8), "IMG"
        )
        os.makedirs(base_dir, exist_ok=True)
        with open(os.path.join(base_dir, "001.jpg"), "wb") as f:
            f.write(img_bytes)

        # 缩略图入库
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(img_bytes))
        img.thumbnail((200, 260))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=80)

        with db() as c:
            c.execute(
                "UPDATE RS_INFO SET DQZP=? WHERE RSID=?",
                (buf.getvalue(), int(rsid)),
            )
        return JsonResponse({"code": 0, "msg": "照片已保存"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
