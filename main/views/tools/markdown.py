"""
在线日记 - Markdown编辑
"""
import json
import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.models import Diary

logger = logging.getLogger(__name__)


@login_required
def page(request):
    return render(request, "tools/markdown.html")


@login_required
def list_api(request):
    """日记列表"""
    diaries = Diary.objects.filter(user=request.user) \
        .values('id', 'title', 'updated_at') \
        .order_by('-updated_at')
    return JsonResponse({
        "code": 0,
        "data": [{
            "id": d["id"],
            "title": d["title"] or "无标题",
            "updated_at": d["updated_at"].strftime("%Y-%m-%d %H:%M")
        } for d in diaries]
    })


@login_required
def detail_api(request):
    """日记详情"""
    diary_id = request.GET.get("id", "")
    if not diary_id:
        return JsonResponse({"code": 400, "msg": "缺少ID"})
    diary = get_object_or_404(Diary, id=int(diary_id), user=request.user)
    return JsonResponse({
        "code": 0,
        "data": {
            "id": diary.id,
            "title": diary.title,
            "content": diary.content,
            "updated_at": diary.updated_at.strftime("%Y-%m-%d %H:%M")
        }
    })


@login_required
@csrf_exempt
def save_api(request):
    """保存日记"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400, "msg": "参数格式错误"})

    diary_id = data.get("id")
    title = data.get("title", "").strip()
    content = data.get("content", "")

    if diary_id:
        diary = get_object_or_404(Diary, id=int(diary_id), user=request.user)
        diary.title = title or "无标题"
        diary.content = content
        diary.save()
        return JsonResponse({"code": 0, "msg": "保存成功", "id": diary.id})
    else:
        diary = Diary.objects.create(
            user=request.user,
            title=title or "无标题",
            content=content
        )
        return JsonResponse({"code": 0, "msg": "创建成功", "id": diary.id})


@login_required
@csrf_exempt
def delete_api(request):
    """删除日记"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})
    diary_id = data.get("id")
    if not diary_id:
        return JsonResponse({"code": 400, "msg": "缺少ID"})
    Diary.objects.filter(id=int(diary_id), user=request.user).delete()
    return JsonResponse({"code": 0, "msg": "删除成功"})
