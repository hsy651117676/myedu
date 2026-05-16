from django.urls import path, re_path
from django.conf.urls.static import static
from django.conf import settings
from django.urls import path, include

# 认证
from .views.auth import (
    login_view,
    register_view,
    forgot_pwd_view,
    send_reset_code,
    logout_view,
    change_pwd,
    base_info_view,
    generate_captcha,
    send_email_code,
    menu_api,
)

# 人口管理
from .views.people import (
    family_query_api,
    person_manage,
    data_change,
    person_query_api,
    person_save_api,
    person_query,
    key_data_update_api,
)

# 主页
from .views.home import home_view

# 工具
from .views.tools import linux, encrypt, decrypt

# 系统
from .views.system import base_info, placeholder

# 档案-人员维护
from .views.archives.person import (
    person_view,
    person_list_api,
    person_detail_api,
    person_save_api as archives_person_save_api,
    unit_list_api,
    tree_root_api,
    tree_children_api,
    person_search_api,
    person_basic_view,
    person_salary_view,
)
from .views.archives.salary import (
    salary_data_api,
    salary_save_api,
    salary_delete_api,
    salary_bzfind_api,
    salary_dcfind_api,
    salary_auto_api,
    salary_export_api,
    person_salary_view,
)
from .views.archives.position import (
    person_position_view,
    position_data_api,
    position_save_api,
    position_export_api,
)
from .views.archives.audit import (
    person_audit_view,
    audit_data_api,
    audit_save_api,
    audit_proof_check_api,
    audit_proof_print_api,
    audit_proof_print_admin_api,
)
from .views.archives.log_query import log_query_view, log_types_api, log_query_api
from .views.archives.identify import (
    person_identify_view,
    identify_data_api,
    identify_save_api,
    identify_generate_api,
    identify_export_api,
    alteration_save_api,
    alteration_delete_api,
    alteration_clear_api,
)
from .views.archives.preaudit import (
    person_preaudit_view,
    preaudit_data_api,
    preaudit_export_api,
)
from .views.archives.supplement import (
    person_supplement_view,
    supplement_data_api,
    supplement_save_api,
)
from .views.archives.family import person_family_view, family_data_api, family_save_api
from .views.archives.directory import (
    person_directory_view,
    directory_tree_api,
    directory_list_api,
    directory_save_api,
    directory_print_api,
)
from .views.system import (
    base_info,
    placeholder,
    user_yhbh_view,
    archives_auto_view,
    archives_auto_list_api,
    archives_auto_save_api,
    archives_auto_fl_api,
    archives_auto_export_api,
)
from .views.archives.cadre import (
    person_cadre_view,
    cadre_list_api,
    cadre_detail_api,
    cadre_save_api,
    cadre_add_api,
    cadre_delete_api,
    cadre_extract_api,
)

urlpatterns = [
    # ==================== 主页 ====================
    path("", home_view, name="home"),
    # ==================== 认证 ====================
    path("login/", login_view, name="login"),
    path("register/", register_view, name="register"),
    path("forgot-pwd/", forgot_pwd_view, name="forgot_pwd"),
    path("send-reset-code/", send_reset_code, name="send_reset_code"),
    path("logout/", logout_view, name="logout"),
    path("change-pwd/", change_pwd, name="change_pwd"),
    path("base-info/", base_info_view, name="base_info"),
    path("captcha/", generate_captcha, name="captcha"),
    path("send-email-code/", send_email_code, name="send_email_code"),
    # ==================== 人口管理 ====================
    path("person-query/", person_query, name="person-query"),
    path("person-manage/", person_manage, name="person-manage"),
    path("data-change/", data_change, name="data-change"),
    path("api/person-query/", person_query_api, name="person-query-api"),
    path("api/family-query/", family_query_api, name="family-query-api"),
    path("api/person-save/", person_save_api, name="person-save-api"),
    path("api/key-data-update/", key_data_update_api, name="key-data-update-api"),
    # ==================== 菜单API ====================
    path("api/menu/", menu_api, name="menu-api"),
    # ==================== 常用工具 ====================
    path("tools/linux/", linux, name="linux"),
    path("tools/encrypt/", encrypt, name="encrypt"),
    path("tools/decrypt/", decrypt, name="decrypt"),
    # ==================== 档案-人员维护 ====================
    path("archives/person", person_view, name="archives-person"),
    path("archives/person-basic/", person_basic_view, name="person-basic"),
    path("archives/person-salary/", person_salary_view, name="person-salary"),
    path("archives/api/tree/", tree_root_api, name="archives-tree"),
    path(
        "archives/api/tree-children/", tree_children_api, name="archives-tree-children"
    ),
    path(
        "archives/api/person-search/", person_search_api, name="archives-person-search"
    ),
    path("archives/api/person-list/", person_list_api, name="archives-person-list"),
    path(
        "archives/api/person-detail/", person_detail_api, name="archives-person-detail"
    ),
    path(
        "archives/api/person-save/",
        archives_person_save_api,
        name="archives-person-save",
    ),
    path("archives/api/unit-list/", unit_list_api, name="archives-unit-list"),
    path("archives/api/salary/", salary_data_api, name="salary-data"),
    path("archives/api/salary-save/", salary_save_api, name="salary-save"),
    path("archives/api/salary-delete/", salary_delete_api, name="salary-delete"),
    path("archives/api/salary-auto/", salary_auto_api, name="salary-auto"),
    path("archives/api/salary-export/", salary_export_api, name="salary-export"),
    path("archives/api/salary-bzfind/", salary_bzfind_api, name="salary-bzfind"),
    path("archives/api/salary-dcfind/", salary_dcfind_api, name="salary-dcfind"),
    path("archives/person-position/", person_position_view, name="person-position"),
    path("archives/api/position/", position_data_api, name="position-data"),
    path("archives/api/position-save/", position_save_api, name="position-save"),
    path("archives/api/position-export/", position_export_api, name="position-export"),
    path("archives/person-audit/", person_audit_view, name="person-audit"),
    path("archives/api/audit/", audit_data_api, name="audit-data"),
    path("archives/api/audit-save/", audit_save_api, name="audit-save"),
    path(
        "archives/api/audit-proof-check/",
        audit_proof_check_api,
        name="audit-proof-check",
    ),
    path(
        "archives/api/audit-proof-print/",
        audit_proof_print_api,
        name="audit-proof-print",
    ),
    path("archives/api/zs/", audit_proof_print_admin_api, name="zs"),
    path("archives/person-identify/", person_identify_view, name="person-identify"),
    path("archives/api/identify/", identify_data_api, name="identify-data"),
    path("archives/api/identify-save/", identify_save_api, name="identify-save"),
    path(
        "archives/api/identify-generate/",
        identify_generate_api,
        name="identify-generate",
    ),
    path("archives/api/alteration-save/", alteration_save_api, name="alteration-save"),
    path(
        "archives/api/alteration-delete/",
        alteration_delete_api,
        name="alteration-delete",
    ),
    path(
        "archives/api/alteration-clear/", alteration_clear_api, name="alteration-clear"
    ),
    path("archives/api/identify-export/", identify_export_api, name="identify-export"),
    path("archives/person-preaudit/", person_preaudit_view, name="person-preaudit"),
    path("archives/api/preaudit/", preaudit_data_api, name="preaudit-data"),
    path("archives/api/preaudit-export/", preaudit_export_api, name="preaudit-export"),
    path("archives/person-directory/", person_directory_view, name="person-directory"),
    path("archives/api/directory-tree/", directory_tree_api, name="directory-tree"),
    path("archives/api/directory-list/", directory_list_api, name="directory-list"),
    path("archives/api/directory-save/", directory_save_api, name="directory-save"),
    path("archives/api/directory-print/", directory_print_api, name="directory-print"),
    path("archives/person-cadre/", person_cadre_view, name="person-cadre"),
    path("archives/api/cadre-list/", cadre_list_api, name="cadre-list"),
    path("archives/api/cadre-detail/", cadre_detail_api, name="cadre-detail"),
    path("archives/api/cadre-save/", cadre_save_api, name="cadre-save"),
    path("archives/api/cadre-add/", cadre_add_api, name="cadre-add"),
    path("archives/api/cadre-delete/", cadre_delete_api, name="cadre-delete"),
    path("archives/api/cadre-extract/", cadre_extract_api, name="cadre-extract"),
    # 补充信息
    path(
        "archives/person-supplement/", person_supplement_view, name="person-supplement"
    ),
    path("archives/api/supplement/", supplement_data_api, name="supplement-data"),
    path("archives/api/supplement-save/", supplement_save_api, name="supplement-save"),
    # 家庭成员
    path("archives/person-family/", person_family_view, name="person-family"),
    path("archives/api/family/", family_data_api, name="family-data"),
    path("archives/api/family-save/", family_save_api, name="family-save"),
    path("archivesSystem/log", log_query_view, name="log-query"),
    path("archivesSystem/api/log-types/", log_types_api, name="log-types"),
    path("archivesSystem/api/log-query/", log_query_api, name="log-query-api"),
    path("system/archives-auto/", archives_auto_view, name="archives-auto"),
    path(
        "system/api/archives-auto-list/",
        archives_auto_list_api,
        name="archives-auto-list",
    ),
    path(
        "system/api/archives-auto-save/",
        archives_auto_save_api,
        name="archives-auto-save",
    ),
    path("system/api/archives-auto-fl/", archives_auto_fl_api, name="archives-auto-fl"),
    path(
        "system/api/archives-auto-export/",
        archives_auto_export_api,
        name="archives-auto-export",
    ),

    path('archives/image/', include('main.views.archives.image.urls')),

    # ==================== 占位路由 ====================
    re_path(r"^(archives|daily|archivesSystem)/.*$", placeholder, name="placeholder"),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0]
    )
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
