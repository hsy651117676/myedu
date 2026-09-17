from django.urls import path, include
from django.contrib.auth.decorators import login_required

from . import person
from . import salary
from . import position
from . import audit
from . import identify
from . import preaudit
from . import supplement
from . import family
from . import directory
from . import cadre
from . import log_query
from . import streamer
from . import directory_print
from . import meeting
from . import data_export

urlpatterns = [
    # ==================== 人员维护 ====================
    path("person", person.person_view, name="archives-person"),
    path("person-basic/", person.person_basic_view, name="person-basic"),
    path("person-salary/", person.person_salary_view, name="person-salary"),
    path("api/person-detail/", person.person_detail_api, name="archives-person-detail"),
    path("api/person-save/", person.person_save_api, name="archives-person-save"),
    path("api/unit-list/", person.unit_list_api, name="archives-unit-list"),
    path("api/person-photo/", person.person_photo_api, name="person-photo"),
    # ==================== 工资 ====================
    path("api/salary/", salary.salary_data_api, name="salary-data"),
    path("api/salary-save/", salary.salary_save_api, name="salary-save"),
    path("api/salary-delete/", salary.salary_delete_api, name="salary-delete"),
    path("api/salary-auto/", salary.salary_auto_api, name="salary-auto"),
    path("api/salary-export/", salary.salary_export_api, name="salary-export"),
    path("api/salary-bzfind/", salary.salary_bzfind_api, name="salary-bzfind"),
    path("api/salary-dcfind/", salary.salary_dcfind_api, name="salary-dcfind"),
    path("api/salary-print/", salary.salary_print_api, name="salary-print"),
    # ==================== 职务变动 ====================
    path("person-position/", position.person_position_view, name="person-position"),
    path("api/position/", position.position_data_api, name="position-data"),
    path("api/position-save/", position.position_save_api, name="position-save"),
    path("api/position-export/", position.position_export_api, name="position-export"),
    # ==================== 档案专审 ====================
    path("person-audit/", audit.person_audit_view, name="person-audit"),
    path("api/audit/", audit.audit_data_api, name="audit-data"),
    path("api/audit-save/", audit.audit_save_api, name="audit-save"),
    path(
        "api/audit-proof-check/", audit.audit_proof_check_api, name="audit-proof-check"
    ),
    path(
        "api/audit-proof-print/", audit.audit_proof_print_api, name="audit-proof-print"
    ),
    path("api/zs/", audit.audit_proof_print_admin_api, name="zs"),
    path("api/audit-export/", audit.audit_export_api, name="audit-export"),
    # ==================== 认定表 ====================
    path("person-identify/", identify.person_identify_view, name="person-identify"),
    path("api/identify/", identify.identify_data_api, name="identify-data"),
    path("api/identify-save/", identify.identify_save_api, name="identify-save"),
    path(
        "api/identify-generate/",
        identify.identify_generate_api,
        name="identify-generate",
    ),
    path("api/identify-export/", identify.identify_export_api, name="identify-export"),
    path("api/alteration-save/", identify.alteration_save_api, name="alteration-save"),
    path(
        "api/alteration-delete/",
        identify.alteration_delete_api,
        name="alteration-delete",
    ),
    path(
        "api/alteration-clear/", identify.alteration_clear_api, name="alteration-clear"
    ),
    # ==================== 任前联审 ====================
    path("person-preaudit/", preaudit.person_preaudit_view, name="person-preaudit"),
    path("api/preaudit/", preaudit.preaudit_data_api, name="preaudit-data"),
    path("api/preaudit-export/", preaudit.preaudit_export_api, name="preaudit-export"),
    # ==================== 补充信息 ====================
    path(
        "person-supplement/",
        supplement.person_supplement_view,
        name="person-supplement",
    ),
    path("api/supplement/", supplement.supplement_data_api, name="supplement-data"),
    path(
        "api/supplement-save/", supplement.supplement_save_api, name="supplement-save"
    ),
    # ==================== 家庭成员 ====================
    path("person-family/", family.person_family_view, name="person-family"),
    path("api/family/", family.family_data_api, name="family-data"),
    path("api/family-save/", family.family_save_api, name="family-save"),
    # ==================== 档案目录 ====================
    path("person-directory/", directory.person_directory_view, name="person-directory"),
    path("api/directory-tree/", directory.directory_tree_api, name="directory-tree"),
    path("api/directory-list/", directory.directory_list_api, name="directory-list"),
    path("api/directory-save/", directory.directory_save_api, name="directory-save"),
    path("directory-print/", directory_print.print_page, name="directory-print"),
    path(
        "api/directory-print-pdf/",
        directory_print.print_pdf_api,
        name="directory-print-pdf",
    ),
    path("api/directory-all/", directory.all_directory_api, name="directory-all"),
    path(
        "person-directory-all/",
        directory.all_directory_page,
        name="person-directory-all-page",
    ),
    path(
        "api/directory-print-export/",
        directory_print.print_export_api,
        name="directory-print-export",
    ),
    # ==================== 干部任免表 ====================
    path("person-cadre/", cadre.person_cadre_view, name="person-cadre"),
    path("api/cadre-list/", cadre.cadre_list_api, name="cadre-list"),
    path("api/cadre-detail/", cadre.cadre_detail_api, name="cadre-detail"),
    path("api/cadre-save/", cadre.cadre_save_api, name="cadre-save"),
    path("api/cadre-add/", cadre.cadre_add_api, name="cadre-add"),
    path("api/cadre-delete/", cadre.cadre_delete_api, name="cadre-delete"),
    path("api/cadre-extract/", cadre.cadre_extract_api, name="cadre-extract"),
    path("api/cadre-export/", cadre.cadre_export_api, name="cadre-export"),
    path("api/directory-all/", directory.all_directory_api, name="directory-all"),
    # ==================== 日志查询 ====================
    path("log", log_query.log_query_view, name="log-query"),
    path("api/log-types/", log_query.log_types_api, name="log-types"),
    path("api/log-query/", log_query.log_query_api, name="log-query-api"),
    # ==================== 扫描查看 ====================
    path("image/", include("main.views.archives.image.urls")),
    # ==================== 档案标签打印 ====================
    path("streamer/", streamer.page, name="streamer"),
    path("api/streamer/units/", streamer.unit_list_api, name="streamer-units"),
    path("api/streamer/table/", streamer.table_api, name="streamer-table"),
    path("api/streamer/save/", streamer.save_api, name="streamer-save"),
    path(
        "api/streamer/print-streamer/",
        streamer.print_streamer_api,
        name="streamer-print",
    ),
    path("api/streamer/print-label/", streamer.print_label_api, name="streamer-label"),
    path(
        "api/streamer/print-cabinet/",
        streamer.print_cabinet_api,
        name="streamer-cabinet",
    ),
    # 党组会认定
    path("person-meeting/", meeting.person_meeting_view, name="person-meeting"),
    path(
        "person-meeting-form/",
        meeting.person_meeting_form_view,
        name="person-meeting-form",
    ),
    path("api/meeting-list/", meeting.meeting_list_api, name="meeting-list"),
    path("api/meeting-detail/", meeting.meeting_detail_api, name="meeting-detail"),
    path("api/meeting-save/", meeting.meeting_save_api, name="meeting-save"),
    path("api/meeting-delete/", meeting.meeting_delete_api, name="meeting-delete"),
    path("api/meeting-extract/", meeting.meeting_extract_api, name="meeting-extract"),
    path("api/meeting-batches/", meeting.batch_list_api, name="meeting-batches"),
    # 数据导出
    path("data-export/", data_export.page, name="data_export_page"),
    path("api/data-export/types/", data_export.types_api, name="data_export_types"),
    path("api/data-export/tree/", data_export.tree_api, name="data_export_tree"),
    path("api/data-export/query/", data_export.query_api, name="data_export_query"),
    path("api/data-export/export/", data_export.export_api, name="data_export_export"),
]
