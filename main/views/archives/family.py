from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.db_utils import _get_conn
import json
import logging
from main.decorators import archive_perm_required
#@archive_perm_required

logger = logging.getLogger(__name__)

def _get_yhbh(request):
    try: return request.user.profile.yhbh or 0
    except: return 0

@login_required
@archive_perm_required
def person_family_view(request):
    return render(request, 'archives/person_family.html')

@login_required
def family_data_api(request):
    rsid = request.GET.get('rsid', '')
    if not rsid: return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT serialNumber, appellation AS 称谓, name AS 姓名, sex AS 性别, IDCard AS 身份证号, workUnit AS 工作单位及职务 FROM Z_FamilyMembers WHERE rsid=? ORDER BY serialNumber", (int(rsid),))
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn: conn.close()

@login_required
@csrf_exempt
def family_save_api(request):
    if request.method != "POST": return JsonResponse({"code": 405})
    try: data = json.loads(request.body)
    except: return JsonResponse({"code": 400})
    rsid = data.get("rsid")
    rows = data.get("rows", [])
    if not rsid: return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        for row in rows:
            sn = row.get("serialNumber", 0)
            cursor.execute("SELECT COUNT(*) FROM Z_FamilyMembers WHERE rsid=? AND serialNumber=?", (int(rsid), int(sn)))
            if cursor.fetchone()[0] > 0:
                cursor.execute("UPDATE Z_FamilyMembers SET appellation=?, name=?, sex=?, IDCard=?, workUnit=? WHERE rsid=? AND serialNumber=?", (row.get('称谓',''), row.get('姓名',''), row.get('性别',''), row.get('身份证号',''), row.get('工作单位及职务',''), int(rsid), int(sn)))
            else:
                cursor.execute("INSERT INTO Z_FamilyMembers (rsid, serialNumber, appellation, name, sex, IDCard, workUnit) VALUES (?,?,?,?,?,?,?)", (int(rsid), int(sn), row.get('称谓',''), row.get('姓名',''), row.get('性别',''), row.get('身份证号',''), row.get('工作单位及职务','')))
        conn.commit(); cursor.close()
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn: conn.close()
