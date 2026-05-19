from django.urls import path
from . import views
from . import menus
from . import auth
from . import archive_users
from . import platform_users

urlpatterns = [
    path("menus/", menus.menu_api, name="menu-api"),
    path("user-yhbh/", views.user_yhbh_view, name="user-yhbh"),

    # 档案用户管理
    path("archive-users/", archive_users.page, name="archive-users"),
    path("api/archive-users/query/", archive_users.query_api, name="archive-users-query"),
    path("api/archive-users/save/", archive_users.save_api, name="archive-users-save"),
    path("api/depart-list/", archive_users.depart_list_api, name="depart-list"),
    
    # 平台用户管理
    path("platform-users/", platform_users.users_page, name="platform-users"),
    path("api/platform-users/list/", platform_users.user_list_api, name="platform-users-list"),
    path("api/platform-users/save/", platform_users.user_save_api, name="platform-users-save"),

    # 认证
    path("login/", auth.login_view, name="login"),
    path("register/", auth.register_view, name="register"),
    path("forgot-pwd/", auth.forgot_pwd_view, name="forgot_pwd"),
    path("send-reset-code/", auth.send_reset_code, name="send_reset_code"),
    path("logout/", auth.logout_view, name="logout"),
    path("change-pwd/", auth.change_pwd, name="change_pwd"),
    path("base-info/", auth.base_info_view, name="base_info"),
    path("captcha/", auth.generate_captcha, name="captcha"),
    path("send-email-code/", auth.send_email_code, name="send_email_code"),

    # 菜单权限
    path("groups/", platform_users.groups_page, name="platform-groups"),
    path("api/platform-groups/list/", platform_users.group_list_api, name="platform-groups-list"),
    path("api/platform-groups/save/", platform_users.group_save_api, name="platform-groups-save"),
    path("api/menu-tree/", platform_users.menu_tree_api, name="menu-tree"),
    path("api/group-menus/", platform_users.group_menus_api, name="group-menus"),
    path("api/group-menus/save/", platform_users.group_menus_save_api, name="group-menus-save"),
]
