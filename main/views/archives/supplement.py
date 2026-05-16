from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.db_utils import _get_conn
import json
import logging

logger = logging.getLogger(__name__)

def _get_yhbh(request):
    try: return request.user.profile.yhbh or 0
    except: return 0

@login_required
def person_supplement_view(request):
    return render(request, 'archives/person_supplement.html')

@login_required
def supplement_data_api(request):
    rsid = request.GET.get('rsid', '')
    if not rsid: return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("{CALL Z_supplement_EDIT(?, ?, '', '', '', 'SELECT')}", (int(rsid), _get_yhbh(request)))
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        data = dict(zip(cols, row)) if row else {}
        cursor.close()
        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn: conn.close()

@login_required
@csrf_exempt
def supplement_save_api(request):
    if request.method != "POST": return JsonResponse({"code": 405})
    try: data = json.loads(request.body)
    except: return JsonResponse({"code": 400})
    rsid = data.get("rsid")
    if not rsid: return JsonResponse({"code": 400})
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("{CALL Z_supplement_EDIT(?, ?, ?, ?, ?, 'UPDATE')}", (
            int(rsid), _get_yhbh(request),
            data.get('assessmentResults', ''),
            data.get('reward', ''),
            data.get('resume', '')
        ))
        conn.commit(); cursor.close()
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn: conn.close()
