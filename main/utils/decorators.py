"""
自定义装饰器
"""

from functools import wraps

from django.core.cache import cache
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse


# ==================== 权限判断 ====================


def _is_admin(request):
    """判断是否管理员"""
    if request.user.is_superuser:
        return True
    try:
        if request.user.profile.group and request.user.profile.group.code == "admin":
            return True
    except:
        pass
    archive_user = request.session.get("archive_user", {})
    if archive_user.get("is_admin"):
        return True
    return False


def _rsid_in_perm(rsid, archive_user):
    """检查 rsid 是否在权限范围内"""
    yhbh = archive_user.get("yhbh")
    if not yhbh:
        return False
    cache_key = f"perm:rsid:{yhbh}:{rsid}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    result = _query_rsid_perm(rsid, archive_user)
    cache.set(cache_key, result, 1800)
    return result


def _query_rsid_perm(rsid, archive_user):
    """查询数据库验证 rsid 权限"""
    from main.utils.db_utils import _get_conn

    depart_id = archive_user.get("depart_id")
    jgqx = archive_user.get("jgqx", "")
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        if jgqx:
            ids = ",".join(jgqx.split(","))
            sql = f"SELECT COUNT(*) FROM USERS_DEPARTMENT WHERE RSID=? AND DEPARTMENTID IN ({ids})"
            cursor.execute(sql, (int(rsid),))
        elif depart_id:
            sql = (
                "SELECT COUNT(*) FROM USERS_DEPARTMENT WHERE RSID=? AND DEPARTMENTID=?"
            )
            cursor.execute(sql, (int(rsid), depart_id))
        else:
            return False
        return cursor.fetchone()[0] > 0
    except:
        return False
    finally:
        if conn:
            conn.close()


# ==================== 装饰器 ====================


def archive_perm_required(view_func):
    """档案权限装饰器"""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if _is_admin(request):
            return view_func(request, *args, **kwargs)

        archive_user = request.session.get("archive_user", {})
        yhbh = archive_user.get("yhbh") or getattr(request.user.profile, "yhbh", None)

        if not yhbh:
            return render(request, "archives/no_permission.html")

        rsid = request.GET.get("rsid", "")
        if rsid and not _rsid_in_perm(rsid, archive_user):
            return render(request, "archives/no_permission.html")

        request.archive_yhbh = yhbh
        request.archive_user = archive_user
        return view_func(request, *args, **kwargs)

    return wrapper


def admin_required(view_func):
    """管理员权限装饰器"""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if _is_admin(request):
            return view_func(request, *args, **kwargs)
        return render(request, "archives/no_permission.html")

    return wrapper


def ajax_login_required(view_func):
    """AJAX请求登录检查"""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"code": 401, "msg": "请先登录", "redirect": reverse("login")},
                status=401,
            )
        return view_func(request, *args, **kwargs)

    return wrapped_view


def login_required_top(view_func):
    """顶部窗口登录检查，iframe环境用"""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"code": 401, "msg": "未登录", "redirect": reverse("login")},
                    status=401,
                )
            next_url = request.build_absolute_uri()
            login_url = f"{reverse('login')}?next={next_url}"
            return HttpResponseRedirect(login_url)
        return view_func(request, *args, **kwargs)

    return wrapped_view
