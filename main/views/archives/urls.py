from django.urls import path, include
from django.contrib.auth.decorators import login_required

from . import person as person_views
from . import salary as salary_views
from . import position as position_views
from . import audit as audit_views
from . import identify as identify_views
from . import preaudit as preaudit_views
from . import supplement as supplement_views
from . import family as family_views
from . import directory as directory_views
from . import cadre as cadre_views
from . import log_query as log_views
from . import auto_names

urlpatterns = [
    # ==================== 人员维护 ====================
    path("person", person_views.person_view, name="archives-person"),
    path("person-basic/", person_views.person_basic_view, name="person-basic"),
    path("person-salary/", person_views.person_salary_view, name="person-salary"),
    path("api/person-detail/", person_views.person_detail_api, name="archives-person-detail"),
    path("api/person-save/", person_views.person_save_api, name="archives-person-save"),
    path("api/unit-list/", person_views.unit_list_api, name="archives-unit-list"),

    # ==================== 工资 ====================
    path("api/salary/", salary_views.salary_data_api, name="salary-data"),
    path("api/salary-save/", salary_views.salary_save_api, name="salary-save"),
    path("api/salary-delete/", salary_views.salary_delete_api, name="salary-delete"),
    path("api/salary-auto/", salary_views.salary_auto_api, name="salary-auto"),
    path("api/salary-export/", salary_views.salary_export_api, name="salary-export"),
    path("api/salary-bzfind/", salary_views.salary_bzfind_api, name="salary-bzfind"),
    path("api/salary-dcfind/", salary_views.salary_dcfind_api, name="salary-dcfind"),

    # ==================== 职务变动 ====================
    path("person-position/", position_views.person_position_view, name="person-position"),
    path("api/position/", position_views.position_data_api, name="position-data"),
    path("api/position-save/", position_views.position_save_api, name="position-save"),
    path("api/position-export/", position_views.position_export_api, name="position-export"),

    # ==================== 档案专审 ====================
    path("person-audit/", audit_views.person_audit_view, name="person-audit"),
    path("api/audit/", audit_views.audit_data_api, name="audit-data"),
    path("api/audit-save/", audit_views.audit_save_api, name="audit-save"),
    path("api/audit-proof-check/", audit_views.audit_proof_check_api, name="audit-proof-check"),
    path("api/audit-proof-print/", audit_views.audit_proof_print_api, name="audit-proof-print"),
    path("api/zs/", audit_views.audit_proof_print_admin_api, name="zs"),

    # ==================== 认定表 ====================
    path("person-identify/", identify_views.person_identify_view, name="person-identify"),
    path("api/identify/", identify_views.identify_data_api, name="identify-data"),
    path("api/identify-save/", identify_views.identify_save_api, name="identify-save"),
    path("api/identify-generate/", identify_views.identify_generate_api, name="identify-generate"),
    path("api/identify-export/", identify_views.identify_export_api, name="identify-export"),
    path("api/alteration-save/", identify_views.alteration_save_api, name="alteration-save"),
    path("api/alteration-delete/", identify_views.alteration_delete_api, name="alteration-delete"),
    path("api/alteration-clear/", identify_views.alteration_clear_api, name="alteration-clear"),

    # ==================== 任前联审 ====================
    path("person-preaudit/", preaudit_views.person_preaudit_view, name="person-preaudit"),
    path("api/preaudit/", preaudit_views.preaudit_data_api, name="preaudit-data"),
    path("api/preaudit-export/", preaudit_views.preaudit_export_api, name="preaudit-export"),

    # ==================== 补充信息 ====================
    path("person-supplement/", supplement_views.person_supplement_view, name="person-supplement"),
    path("api/supplement/", supplement_views.supplement_data_api, name="supplement-data"),
    path("api/supplement-save/", supplement_views.supplement_save_api, name="supplement-save"),

    # ==================== 家庭成员 ====================
    path("person-family/", family_views.person_family_view, name="person-family"),
    path("api/family/", family_views.family_data_api, name="family-data"),
    path("api/family-save/", family_views.family_save_api, name="family-save"),

    # ==================== 档案目录 ====================
    path("person-directory/", directory_views.person_directory_view, name="person-directory"),
    path("api/directory-tree/", directory_views.directory_tree_api, name="directory-tree"),
    path("api/directory-list/", directory_views.directory_list_api, name="directory-list"),
    path("api/directory-save/", directory_views.directory_save_api, name="directory-save"),
    path("api/directory-print/", directory_views.directory_print_api, name="directory-print"),

    # ==================== 干部任免表 ====================
    path("person-cadre/", cadre_views.person_cadre_view, name="person-cadre"),
    path("api/cadre-list/", cadre_views.cadre_list_api, name="cadre-list"),
    path("api/cadre-detail/", cadre_views.cadre_detail_api, name="cadre-detail"),
    path("api/cadre-save/", cadre_views.cadre_save_api, name="cadre-save"),
    path("api/cadre-add/", cadre_views.cadre_add_api, name="cadre-add"),
    path("api/cadre-delete/", cadre_views.cadre_delete_api, name="cadre-delete"),
    path("api/cadre-extract/", cadre_views.cadre_extract_api, name="cadre-extract"),

    # ==================== 日志查询 ====================
    path("log", log_views.log_query_view, name="log-query"),
    path("api/log-types/", log_views.log_types_api, name="log-types"),
    path("api/log-query/", log_views.log_query_api, name="log-query-api"),

    #=======================材料名称自动补齐===============
    path("auto-names/", auto_names.archives_auto_view, name="archives-auto"),
    path("api/auto-names/list/", auto_names.archives_auto_list_api, name="archives-auto-list"),
    path("api/auto-names/save/", auto_names.archives_auto_save_api, name="archives-auto-save"),
    path("api/auto-names/fl/", auto_names.archives_auto_fl_api, name="archives-auto-fl"),
    path("api/auto-names/export/", auto_names.archives_auto_export_api, name="archives-auto-export"),

    # ==================== 扫描查看 ====================
    path('image/', include('main.views.archives.image.urls')),
]
