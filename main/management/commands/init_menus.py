from django.core.management.base import BaseCommand
from main.models import Menu, UserGroup, MenuGroup


class Command(BaseCommand):
    help = '初始化菜单和用户组'

    def handle(self, *args, **options):
        # 清空旧数据
        MenuGroup.objects.all().delete()
        Menu.objects.all().delete()

        # 创建用户组
        groups = {
            'admin': '管理员',
            'archive_reviewer': '档案专审人员',
            'archive_scanner': '档案扫描人员',
            'population_query': '人口查询人员',
        }

        group_map = {}
        for code, name in groups.items():
            group, _ = UserGroup.objects.get_or_create(code=code, defaults={'name': name})
            group_map[code] = group

        # 菜单数据（所有名称唯一）
        menus_data = [
            # 人口信息
            {'name': '人口信息', 'url': '', 'parent': None, 'sort': 1},
            {'name': '人员查询', 'url': '/person-query/', 'parent': '人口信息', 'sort': 1},
            {'name': '人口-人员维护', 'url': '/person-manage/', 'parent': '人口信息', 'sort': 2},
            {'name': '关键数据变更', 'url': '/data-change/', 'parent': '人口信息', 'sort': 3},
            # 档案管理
            {'name': '档案管理', 'url': '', 'parent': None, 'sort': 2},
            {'name': '档案-人员维护', 'url': '/archives/person', 'parent': '档案管理', 'sort': 1},
            {'name': '机构维护', 'url': '/archives/dept', 'parent': '档案管理', 'sort': 2},
            {'name': '档案标签', 'url': '/archives/label', 'parent': '档案管理', 'sort': 3},
            {'name': '查询统计', 'url': '/archives/query', 'parent': '档案管理', 'sort': 4},
            {'name': '常用文件', 'url': '/archives/file', 'parent': '档案管理', 'sort': 5},
            # 日常业务
            {'name': '日常业务', 'url': '', 'parent': None, 'sort': 3},
            {'name': '档案查阅', 'url': '/daily/look', 'parent': '日常业务', 'sort': 1},
            {'name': '档案借阅', 'url': '/daily/borrow', 'parent': '日常业务', 'sort': 2},
            {'name': '档案转递', 'url': '/daily/transfer', 'parent': '日常业务', 'sort': 3},
            {'name': '档案接收', 'url': '/daily/receive', 'parent': '日常业务', 'sort': 4},
            # 系统管理
            {'name': '系统管理', 'url': '', 'parent': None, 'sort': 4},
            {'name': '批量维护', 'url': '/archivesSystem/batch', 'parent': '系统管理', 'sort': 1},
            {'name': '日志查询', 'url': '/archivesSystem/log', 'parent': '系统管理', 'sort': 2},
            # 常用工具
            {'name': '常用工具', 'url': '', 'parent': None, 'sort': 99},
            {'name': 'Linux命令', 'url': '/linux/', 'parent': '常用工具', 'sort': 1},
            {'name': '算法加密', 'url': '/encrypt/', 'parent': '常用工具', 'sort': 2},
            {'name': '算法解密', 'url': '/decrypt/', 'parent': '常用工具', 'sort': 3},
            {'name': '键盘电子琴', 'url': '/static/HTML5piano.html', 'parent': '常用工具', 'sort': 4},
        ]

        # 创建菜单
        menu_map = {}
        for item in menus_data:
            parent = menu_map.get(item['parent']) if item['parent'] else None
            menu = Menu.objects.create(
                name=item['name'],
                url=item['url'],
                parent=parent,
                sort=item['sort']
            )
            menu_map[item['name']] = menu

        # 管理员：所有菜单
        for menu in Menu.objects.all():
            MenuGroup.objects.create(menu=menu, group=group_map['admin'])

        # 人口查询人员
        pop_menus = ['人口信息', '人员查询', '人口-人员维护', '常用工具',
                     'Linux命令', '算法加密', '算法解密', '键盘电子琴']
        for name in pop_menus:
            MenuGroup.objects.create(menu=menu_map[name], group=group_map['population_query'])

        # 档案专审人员
        reviewer_menus = ['档案管理', '档案-人员维护', '机构维护', '档案标签',
                          '查询统计', '常用文件', '日常业务', '档案查阅',
                          '档案借阅', '档案转递', '档案接收', '常用工具']
        for name in reviewer_menus:
            MenuGroup.objects.create(menu=menu_map[name], group=group_map['archive_reviewer'])

        # 档案扫描人员
        scanner_menus = ['档案管理', '档案-人员维护', '机构维护', '日常业务',
                         '档案查阅', '档案借阅', '常用工具']
        for name in scanner_menus:
            MenuGroup.objects.create(menu=menu_map[name], group=group_map['archive_scanner'])

        self.stdout.write(self.style.SUCCESS('菜单和权限初始化完成！'))
