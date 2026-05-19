"""
菜单 API
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from main.models import Menu, MenuGroup, UserProfile

logger = logging.getLogger(__name__)

# 所有用户都显示的主菜单标签
ALWAYS_SHOW_IDS = [24, 28, 34, 39, 47]


def _merge_top_labels(top_menus):
    """合并主菜单标签，去重"""
    always = Menu.objects.filter(id__in=ALWAYS_SHOW_IDS, is_active=True).order_by('sort')
    existing = {m['id'] for m in top_menus}
    for m in always:
        if m.id not in existing:
            top_menus.append({
                'id': m.id, 'name': m.name, 'url': m.url,
                'icon': m.icon, 'parent_id': m.parent_id, 'children': []
            })
    return top_menus


@login_required
def menu_api(request):
    # ==================== 平台管理员 ====================
    is_platform_admin = False
    try:
        if request.user.is_superuser:
            is_platform_admin = True
        elif request.user.profile.group and request.user.profile.group.code == 'admin':
            is_platform_admin = True
    except:
        pass

    if is_platform_admin:
        menus = Menu.objects.filter(is_active=True).order_by('sort')
        menu_dict = {}
        top_menus = []
        for menu in menus:
            menu_dict[menu.id] = {
                'id': menu.id, 'name': menu.name, 'url': menu.url,
                'icon': menu.icon, 'parent_id': menu.parent_id, 'children': []
            }
        for menu in menus:
            item = menu_dict[menu.id]
            if menu.parent_id is None:
                top_menus.append(item)
            elif menu.parent_id in menu_dict:
                menu_dict[menu.parent_id]['children'].append(item)
        top_menus = _merge_top_labels(top_menus)
        return JsonResponse({'code': 0, 'data': top_menus})

    # ==================== 档案用户 ====================
    archive_user = request.session.get('archive_user', {})
    if archive_user:
        menus = []
        menus.append({'id': 29, 'name': '档案-人员维护', 'url': '/archives/person', 'parent_id': 28, 'icon': '', 'children': []})
        if archive_user.get('can_scan'):
            menus.append({'id': 55, 'name': '扫描档案查看', 'url': '/archives/image/scan/', 'parent_id': 28, 'icon': '', 'children': []})
        if archive_user.get('can_print'):
            menus.append({'id': 35, 'name': '档案查阅', 'url': '/daily/look', 'parent_id': 34, 'icon': '', 'children': []})
            menus.append({'id': 36, 'name': '档案借阅', 'url': '/daily/borrow', 'parent_id': 34, 'icon': '', 'children': []})
            menus.append({'id': 37, 'name': '档案转递', 'url': '/daily/transfer', 'parent_id': 34, 'icon': '', 'children': []})
            menus.append({'id': 38, 'name': '档案接收', 'url': '/daily/receive', 'parent_id': 34, 'icon': '', 'children': []})
        if archive_user.get('is_admin'):
            menus.append({'id': 54, 'name': '人员机构调整', 'url': '/business/organization/', 'parent_id': 28, 'icon': '', 'children': []})
            menus.append({'id': 32, 'name': '查询统计', 'url': '/archives/query', 'parent_id': 28, 'icon': '', 'children': []})
            menus.append({'id': 33, 'name': '常用文件', 'url': '/archives/file', 'parent_id': 28, 'icon': '', 'children': []})

        top_menus = _merge_top_labels([])
        # 把档案用户菜单挂到对应父节点下
        for m in menus:
            for t in top_menus:
                if t['id'] == m['parent_id']:
                    t['children'].append(m)
                    break
        return JsonResponse({'code': 0, 'data': top_menus})

    # ==================== 普通平台用户 ====================
    try:
        group = request.user.profile.group
    except:
        return JsonResponse({'code': 0, 'data': _merge_top_labels([])})

    if not group:
        return JsonResponse({'code': 0, 'data': _merge_top_labels([])})

    menu_ids = MenuGroup.objects.filter(group=group).values_list('menu_id', flat=True)
    menus = Menu.objects.filter(id__in=menu_ids, is_active=True).order_by('sort')

    menu_dict = {}
    top_menus = []
    for menu in menus:
        menu_dict[menu.id] = {
            'id': menu.id, 'name': menu.name, 'url': menu.url,
            'icon': menu.icon, 'parent_id': menu.parent_id, 'children': []
        }
    for menu in menus:
        item = menu_dict[menu.id]
        if menu.parent_id is None:
            top_menus.append(item)
        elif menu.parent_id in menu_dict:
            menu_dict[menu.parent_id]['children'].append(item)

    top_menus = _merge_top_labels(top_menus)
    return JsonResponse({'code': 0, 'data': top_menus})
