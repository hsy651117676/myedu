"""
常用文件 - 管理
"""
import json
import hashlib
import os
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.utils import _get_conn
from . import common_files_service as service

logger = logging.getLogger(__name__)


@login_required
def manage_page(request):
    return render(request, "archivesSystem/common_files_manage.html")


@login_required
def manage_list_api(request):
    try:
        rows, total = service.query_files_grouped(
            category=request.GET.get("category", "").strip(),
            year=request.GET.get("year", "").strip(),
            page=int(request.GET.get("page", 1)),
            page_size=int(request.GET.get("pageSize", 20)),
        )
        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
def persons_api(request):
    file_no = request.GET.get("fileNo", "")
    if not file_no:
        return JsonResponse({"code": 400})
    try:
        return JsonResponse({"code": 0, "data": service.query_persons_by_fileno(file_no)})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
@csrf_exempt
def save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    action = data.get("action")
    try:
        if action == "update_persons":
            service.update_persons(data.get("FileNo", ""), data.get("Category", ""),
                                   data.get("Year", ""), data.get("persons", []))
        elif action == "delete":
            service.delete_file(data.get("FileNo", ""))
        return JsonResponse({"code": 0, "msg": "操作成功"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
@csrf_exempt
def rename_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    try:
        service.update_file_info(data.get("oldFileNo", ""), data.get("FileNo", ""),
                                 data.get("Category", ""), data.get("Year", ""), data.get("FileName", ""))
        return JsonResponse({"code": 0, "msg": "修改成功"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
@csrf_exempt
def upload_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})

    category = request.POST.get("category", "").strip()
    year = request.POST.get("year", "").strip()
    file_no = request.POST.get("fileNo", "").strip()
    uploaded_file = request.FILES.get("file")
    persons_str = request.POST.get("persons", "")
    if not category or not year or not uploaded_file:
        return JsonResponse({"code": 400, "msg": "类别、年度和文件不能为空"})
    md5 = hashlib.md5()
    for chunk in uploaded_file.chunks():
        md5.update(chunk)
    md5_hash = md5.hexdigest()

    persons = json.loads(persons_str) if persons_str else [{"personName": "", "summary": ""}]
    if not persons:
        persons = [{"personName": "", "summary": ""}]

    file_name = uploaded_file.name
    relative_path = os.path.join(category, year, file_name)
    full_path = service.build_full_path(relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    with open(full_path, 'wb') as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)

    file_size = os.path.getsize(full_path)
    file_type = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else ''

    service.insert_file(category, year, file_no, file_name, relative_path, file_size, file_type, md5_hash,
                        request.user.username, persons)
    return JsonResponse({"code": 0, "msg": "上传成功"})

@login_required
@csrf_exempt
def update_pdf_api(request):
    if request.method != 'POST':
        return JsonResponse({'code': 1, 'msg': '方法不允许'})
    
    file_no = request.POST.get('file_no', '')
    uploaded_file = request.FILES.get('file')
    
    if not file_no or not uploaded_file:
        return JsonResponse({'code': 1, 'msg': '参数不完整'})
    
    success, msg = service.update_pdf_file(file_no, uploaded_file)
    return JsonResponse({'code': 0 if success else 1, 'msg': msg})

@login_required
@csrf_exempt
def add_category_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "方法不允许"})
    try:
        data = json.loads(request.body)
        category_name = data.get("category", "").strip()
        if not category_name:
            return JsonResponse({"code": 400, "msg": "类别名称不能为空"})
        success, msg = service.add_category(category_name)
        return JsonResponse({"code": 0 if success else 1, "msg": msg})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
