"""
菜单 API
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from main.models import Menu, MenuGroup, UserProfile

logger = logging.getLogger(__name__)

ALWAYS_SHOW_IDS = [24, 28, 34, 39, 47]


def _merge_top_labels(top_menus):
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
