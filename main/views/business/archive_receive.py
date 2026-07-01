"""
档案接收
"""
import json
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.utils import _get_conn
from main.utils.decorators import archive_perm_required

logger = logging.getLogger(__name__)


@login_required
@archive_perm_required
def page(request):
    return render(request, "business/archive_receive.html")


@login_required
@archive_perm_required
def list_api(request):
    """历史接收记录"""
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 20))

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM YW_JSDA")
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor.execute(f"""
            SELECT ID, RSID, SJSJ, SJWH, JSR, LJBM, DABH, ZB, FB, GH, CH, XH,
                   SHR, SHRQ, HZRQ, RKRQ, RKSPR, TXM, AJZL, BZ, num
            FROM YW_JSDA ORDER BY SJSJ DESC, ID DESC
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """)

        cols = [col[0] for col in cursor.description]
        rows = []
        for r in cursor.fetchall():
            d = dict(zip(cols, r))
            rows.append({
                "id": d["ID"],
                "personRsid": d["RSID"],
                "receiveDate": d["SJSJ"],
                "documentNo": d["SJWH"],
                "receiver": d["JSR"],
                "fromUnit": d["LJBM"],
                "archiveNo": d["DABH"],
                "original": d["ZB"],
                "copy": d["FB"],
                "cabinetNo": d["GH"],
                "layerNo": d["CH"],
                "sequenceNo": d["XH"],
                "sender": d["SHR"],
                "senderDate": d["SHRQ"],
                "returnDate": d["HZRQ"],
                "storageDate": d["RKRQ"],
                "storageApprover": d["RKSPR"],
                "personName": d["TXM"],
                "archiveType": d["AJZL"],
                "remark": d["BZ"],
                "personCount": d["num"],
            })

        cursor.close()
        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
@csrf_exempt
def save_api(request):
    """新增、修改、删除"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400, "msg": "参数格式错误"})

    action = data.get("action", "save")
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if action == "delete":
            rid = data.get("id")
            if not rid:
                return JsonResponse({"code": 400, "msg": "缺少ID"})
            cursor.execute("DELETE FROM YW_JSDA WHERE ID=?", (int(rid),))
            conn.commit()
            cursor.close()
            return JsonResponse({"code": 0, "msg": "删除成功"})

        # save
        rid = data.get("id")
        personRsid = data.get("personRsid", "")
        receiveDate = data.get("receiveDate", "")
        documentNo = data.get("documentNo", "")
        receiver = data.get("receiver", "")
        fromUnit = data.get("fromUnit", "")
        archiveNo = data.get("archiveNo", "")
        original = data.get("original", "")
        copy_ = data.get("copy", "")
        cabinetNo = data.get("cabinetNo", "")
        layerNo = data.get("layerNo", "")
        sequenceNo = data.get("sequenceNo", "")
        sender = data.get("sender", "")
        senderDate = data.get("senderDate", "")
        returnDate = data.get("returnDate", "")
        storageDate = data.get("storageDate", "")
        storageApprover = data.get("storageApprover", "")
        personName = data.get("personName", "")
        archiveType = data.get("archiveType", "")
        remark = data.get("remark", "")
        personCount = data.get("personCount", 0)

        if rid:
            cursor.execute("""
                UPDATE YW_JSDA SET RSID=?, SJSJ=?, SJWH=?, JSR=?, LJBM=?, DABH=?,
                ZB=?, FB=?, GH=?, CH=?, XH=?, SHR=?, SHRQ=?, HZRQ=?, RKRQ=?,
                RKSPR=?, TXM=?, AJZL=?, BZ=?, num=? WHERE ID=?
            """, (
                personRsid, receiveDate, documentNo, receiver, fromUnit, archiveNo,
                original, copy_, cabinetNo, layerNo, sequenceNo, sender, senderDate,
                returnDate, storageDate, storageApprover, personName, archiveType, remark,
                personCount, int(rid)
            ))
        else:
            cursor.execute("SELECT ISNULL(MAX(ID),0)+1 FROM YW_JSDA")
            new_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO YW_JSDA (ID, RSID, SJSJ, SJWH, JSR, LJBM, DABH, ZB, FB, GH, CH, XH,
                SHR, SHRQ, HZRQ, RKRQ, RKSPR, TXM, AJZL, BZ, num)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_id, personRsid, receiveDate, documentNo, receiver, fromUnit, archiveNo,
                original, copy_, cabinetNo, layerNo, sequenceNo, sender, senderDate,
                returnDate, storageDate, storageApprover, personName, archiveType, remark,
                personCount
            ))

        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "操作成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
def persons_api(request):
    """被接收人详细信息"""
    rsids = request.GET.get("rsids", "")
    if not rsids:
        return JsonResponse({"code": 0, "data": []})
    ids = [x.strip() for x in rsids.split(",") if x.strip()]
    if not ids:
        return JsonResponse({"code": 0, "data": []})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(ids))
        cursor.execute(f"""
            SELECT RSID, XM AS 姓名, XB AS 性别, CSNY AS 出生年月,
                   WORKTIME AS 参加工作时间, MZ AS 民族, RYBH AS 档案编号,
                   ZZMM AS 政治面貌, JOINTIME AS 入党时间,
                   JOBUNIT AS 单位及职务, APPOINTTIME AS 任现职时间,
                   IDCARD AS 身份证号, QUANRIZIXUELI AS 全日制学历,
                   QUANRIZIXUEWEI AS 全日制学位, QUANRIZIYUANXIAO AS 全日制院校,
                   QUANRIZIZHUANYE AS 全日制专业, ZAIZHIXUELI AS 在职学历,
                   ZAIZHIXUEWEI AS 在职学位, ZAIZHIYUANXIAO AS 在职院校,
                   ZAIZHIZHUANYE AS 在职专业
            FROM RS_INFO WHERE RSID IN ({placeholders})
        """, ids)
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
