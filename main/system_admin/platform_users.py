"""
MySQL 平台用户管理
"""
import json
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.models import UserProfile, UserGroup, Menu, MenuGroup

logger = logging.getLogger(__name__)
DEFAULT_PWD = "12345abcde"


@login_required
def users_page(request):
    return render(request, "system/users/platform_users.html")


@login_required
def groups_page(request):
    return render(request, "system/users/platform_groups.html")


# ==================== 用户列表 ====================

@login_required
def user_list_api(request):
    keyword = request.GET.get("keyword", "").strip()
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 20))

    users = User.objects.select_related('profile__group').order_by('-date_joined')
    if keyword:
        users = users.filter(
            Q(username__icontains=keyword) |
            Q(profile__real_name__icontains=keyword) |
            Q(email__icontains=keyword)
        )

    total = users.count()
    start = (page - 1) * page_size
    users = users[start:start + page_size]

    data = []
    for u in users:
        p = getattr(u, 'profile', None)
        data.append({
            "id": u.id,
            "username": u.username,
            "email": u.email or "",
            "is_active": u.is_active,
            "real_name": p.real_name if p else "",
            "group_id": p.group_id if p else None,
            "group_name": p.group.name if p and p.group else "",
            "yhbh": p.yhbh if p else None,
        })
    return JsonResponse({"code": 0, "data": data, "total": total})


# ==================== 用户保存 ====================

@login_required
@csrf_exempt
def user_save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    action = data.get("action")
    try:
        if action == "update":
            user = User.objects.get(id=data.get("id"))
            profile, _ = UserProfile.objects.get_or_create(user=user)
            user.is_active = data.get("is_active", user.is_active)
            user.save()
            profile.real_name = data.get("real_name", "")
            profile.yhbh = data.get("yhbh") or None
            gid = data.get("group_id")
            profile.group_id = gid if gid else None
            profile.save()
        elif action == "reset_pwd":
            user = User.objects.get(id=data.get("id"))
            user.set_password(DEFAULT_PWD)
            user.save()
        return JsonResponse({"code": 0, "msg": "操作成功"})
    except User.DoesNotExist:
        return JsonResponse({"code": 404, "msg": "用户不存在"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})


# ==================== 用户组 ====================

@login_required
def group_list_api(request):
    groups = list(UserGroup.objects.all().values("id", "name", "code", "description"))
    return JsonResponse({"code": 0, "data": groups})


@login_required
@csrf_exempt
def group_save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    if data.get("action") == "delete":
        UserGroup.objects.filter(id=data.get("id")).delete()
        return JsonResponse({"code": 0, "msg": "已删除"})

    groups = data.get("groups", [])
    for g in groups:
        if g.get("id"):
            UserGroup.objects.filter(id=g["id"]).update(
                name=g.get("name", ""), code=g.get("code", ""),
                description=g.get("description", ""))
        else:
            UserGroup.objects.create(
                name=g.get("name", ""), code=g.get("code", ""),
                description=g.get("description", ""))
    return JsonResponse({"code": 0, "msg": "保存成功"})


# ==================== 菜单权限 ====================

@login_required
def menu_tree_api(request):
    menus = Menu.objects.filter(is_active=True).order_by('sort')
    tree = []
    menu_map = {}
    for m in menus:
        item = {"id": m.id, "name": m.name, "parent_id": m.parent_id, "children": []}
        menu_map[m.id] = item
        if m.parent_id is None:
            tree.append(item)
    for m in menus:
        if m.parent_id and m.parent_id in menu_map:
            menu_map[m.parent_id]["children"].append(menu_map[m.id])
    return JsonResponse({"code": 0, "data": tree})


@login_required
def group_menus_api(request):
    group_id = request.GET.get("group_id", "")
    if not group_id:
        return JsonResponse({"code": 0, "data": []})
    ids = list(MenuGroup.objects.filter(group_id=group_id).values_list("menu_id", flat=True))
    return JsonResponse({"code": 0, "data": ids})


@login_required
@csrf_exempt
def group_menus_save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    group_id = data.get("group_id")
    menu_ids = data.get("menu_ids", [])
    if not group_id:
        return JsonResponse({"code": 400, "msg": "缺少group_id"})

    try:
        group = UserGroup.objects.get(id=group_id)
        MenuGroup.objects.filter(group=group).delete()
        for mid in menu_ids:
            MenuGroup.objects.create(group=group, menu_id=mid)
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except UserGroup.DoesNotExist:
        return JsonResponse({"code": 404, "msg": "组不存在"})
