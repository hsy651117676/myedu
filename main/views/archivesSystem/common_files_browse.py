"""
常用文件 - 浏览
"""

import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse, Http404, HttpResponse
from . import common_files_service as service
from urllib.parse import quote
import os

logger = logging.getLogger(__name__)


@login_required
def browse_page(request):
    return render(request, "archivesSystem/common_files_browse.html")


@login_required
def categories_api(request):
    try:
        return JsonResponse({"code": 0, "data": service.get_categories()})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
def years_api(request):
    category = request.GET.get("category", "")
    try:
        conn = service._get_conn_safe()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT Year FROM CommonFiles WHERE Category=? AND IsActive=1 ORDER BY Year",
            (category,),
        )
        return JsonResponse({"code": 0, "data": [r[0] for r in cursor.fetchall()]})
    except:
        return JsonResponse({"code": 0, "data": []})


@login_required
def list_api(request):
    try:
        rows, total = service.query_files_flat(
            category=request.GET.get("category", "").strip(),
            year=request.GET.get("year", "").strip(),
            keyword=request.GET.get("keyword", "").strip(),
            page=int(request.GET.get("page", 1)),
            page_size=int(request.GET.get("pageSize", 20)),
        )
        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
def download_api(request):
    file_id = request.GET.get("id", "")
    try:
        file_path, file_name = service.get_file_info(file_id)
        if not file_path:
            raise Http404("文件不存在")
        full_path = service.build_full_path(file_path)
        if not full_path or not __import__("os").path.exists(full_path):
            raise Http404("文件未找到")

        with open(full_path, "rb") as f:
            resp = HttpResponse(f.read(), content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{file_name}"'
        resp["Content-Length"] = __import__("os").path.getsize(full_path)
        return resp
    except Http404:
        raise
    except:
        raise Http404("下载失败")
