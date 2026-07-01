"""Linux 命令速查工具"""

import json
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db import connection

logger = logging.getLogger(__name__)


@login_required
def linux_page(request):
    """Linux 命令速查页面"""
    return render(request, "tools/linux.html")


# ==================== API ====================


@login_required
def categories_api(request):
    """获取所有分类及数量"""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT category, COUNT(*) AS cnt FROM linuxcmd GROUP BY category ORDER BY category"
        )
        rows = cursor.fetchall()
    data = [{"category": r[0], "count": r[1]} for r in rows]
    return JsonResponse({"code": 0, "data": data})


@login_required
def list_api(request):
    """命令列表"""
    category = request.GET.get("category", "")
    keyword = request.GET.get("keyword", "")
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 30))

    where = []
    params = []
    if category:
        where.append("category = %s")
        params.append(category)
    if keyword:
        where.append("(name LIKE %s OR description LIKE %s)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM linuxcmd {where_clause}", params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor.execute(
            f"SELECT id, name, category, description, markdown FROM linuxcmd {where_clause} ORDER BY category, sort_order, id LIMIT %s OFFSET %s",
            params + [page_size, offset],
        )
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]

    return JsonResponse({"code": 0, "data": rows, "total": total})


@login_required
def detail_api(request):
    """命令详情"""
    cmd_id = request.GET.get("id", "")
    if not cmd_id:
        return JsonResponse({"code": 400})

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, name, category, description, markdown FROM linuxcmd WHERE id = %s",
            [int(cmd_id)],
        )
        cols = [c[0] for c in cursor.description]
        row = cursor.fetchone()

    if not row:
        return JsonResponse({"code": 404})
    return JsonResponse({"code": 0, "data": dict(zip(cols, row))})


@login_required
@csrf_exempt
def save_api(request):
    """新增/更新命令（管理员）"""
    if not request.user.is_superuser:
        return JsonResponse({"code": 403, "msg": "无权限"})

    if request.method != "POST":
        return JsonResponse({"code": 405})

    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    cmd_id = data.get("id")
    name = data.get("name", "").strip()
    category = data.get("category", "").strip()
    description = data.get("description", "").strip()
    markdown = data.get("markdown", "").strip()

    if not name or not category:
        return JsonResponse({"code": 400, "msg": "名称和分类不能为空"})

    with connection.cursor() as cursor:
        if cmd_id:
            cursor.execute(
                "UPDATE linuxcmd SET name=%s, category=%s, description=%s, markdown=%s WHERE id=%s",
                [name, category, description, markdown, int(cmd_id)],
            )
        else:
            cursor.execute(
                "INSERT INTO linuxcmd (name, category, description, markdown) VALUES (%s, %s, %s, %s)",
                [name, category, description, markdown],
            )
    return JsonResponse({"code": 0, "msg": "保存成功"})


@login_required
@csrf_exempt
def delete_api(request):
    """删除命令（管理员）"""
    if not request.user.is_superuser:
        return JsonResponse({"code": 403, "msg": "无权限"})

    if request.method != "POST":
        return JsonResponse({"code": 405})

    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    cmd_id = data.get("id")
    if not cmd_id:
        return JsonResponse({"code": 400})

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM linuxcmd WHERE id = %s", [int(cmd_id)])
    return JsonResponse({"code": 0, "msg": "删除成功"})
