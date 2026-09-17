from django.urls import path
from . import log_query, common_files_browse, common_files_manage, common_files_dialog
from . import (
    auto_names,
    batch,
    archive_transfer,
    organization,
    meeting_admin,
    salary_standard,
)

urlpatterns = [
    # 日志
    path("log/", log_query.page),
    path("api/log/types/", log_query.types_api),
    path("api/log/query/", log_query.query_api),
    # 常用文件浏览
    path("files/", common_files_browse.browse_page),
    path("api/files/categories/", common_files_browse.categories_api),
    path("api/files/years/", common_files_browse.years_api),
    path("api/files/list/", common_files_browse.list_api),
    path("api/files/download/", common_files_browse.download_api),
    # 常用文件管理
    path("files/manage/", common_files_manage.manage_page),
    path("api/files/manage/list/", common_files_manage.manage_list_api),
    path("api/files/manage/persons/", common_files_manage.persons_api),
    path("api/files/manage/save/", common_files_manage.save_api),
    path("api/files/manage/rename/", common_files_manage.rename_api),
    path("api/files/manage/upload/", common_files_manage.upload_api),
    path("api/files/manage/update-pdf/", common_files_manage.update_pdf_api),
    path("api/files/categories/add/", common_files_manage.add_category_api),
    # 常用文件弹窗
    path("files/dialog/add/", common_files_dialog.add_dialog),
    path("files/dialog/edit/", common_files_dialog.edit_dialog),
    # 材料名称自动提示
    path("auto-names/", auto_names.archives_auto_view),
    path("api/auto-names/list/", auto_names.archives_auto_list_api),
    path("api/auto-names/save/", auto_names.archives_auto_save_api),
    path("api/auto-names/fl/", auto_names.archives_auto_fl_api),
    path("api/auto-names/export/", auto_names.archives_auto_export_api),
    # 档案目录批量添加
    path("batch/", batch.page),
    path("api/batch/unit-persons/", batch.unit_persons_api),
    path("api/batch/categories/", batch.category_list_api),
    path("api/batch/existing-count/", batch.existing_count_api),
    path("api/batch/insert/", batch.batch_insert_api),
    path("api/batch/jbbh/", batch.jbbh_api),
    # 档案人员调转
    path("transfer/", archive_transfer.page),
    path("api/transfer/person-detail/", archive_transfer.person_detail_api),
    path("api/transfer/xs-table/", archive_transfer.xs_table_api),
    path("api/transfer/same-xs-list/", archive_transfer.same_xs_list_api),
    path("api/transfer/save/", archive_transfer.save_api),
    # 机构维护
    path("organization/", organization.page, name="organization_page"),
    path("api/organization/tree/", organization.tree_api, name="org_tree_api"),
    path(
        "api/organization/tree-children/",
        organization.tree_children_api,
        name="org_tree_children_api",
    ),
    path("api/organization/save/", organization.save_api, name="org_save_api"),
    path("api/organization/delete/", organization.delete_api, name="org_delete_api"),
    # 人员维护
    path(
        "api/organization/person-list/",
        organization.person_list_api,
        name="org_person_list_api",
    ),
    path(
        "api/organization/person-create/",
        organization.person_create_api,
        name="org_person_create_api",
    ),
    path(
        "api/organization/person-batch-create/",
        organization.person_batch_create_api,
        name="org_person_batch_create_api",
    ),
    # 党组会管理
    path("meeting-admin/", meeting_admin.page),
    path("api/meeting-admin-list/", meeting_admin.list_api),
    path("api/meeting-admin-batches/", meeting_admin.batch_list_api),
    path("api/meeting-admin-all-batches/", meeting_admin.all_batches_api),
    path("api/meeting-admin-save-batch/", meeting_admin.save_batch_api),
    path("api/meeting-admin-delete-batch/", meeting_admin.delete_batch_api),
    path("api/meeting-admin-upload-file/", meeting_admin.upload_file_api),
    path("api/meeting-admin-file/", meeting_admin.download_file_api),
    path("api/meeting-admin-batch-file/", meeting_admin.batch_file_api),
    path("api/meeting-admin-batch-delete/", meeting_admin.batch_delete_api),
    path("api/meeting-admin-save/", meeting_admin.admin_save_api),
    path("api/meeting-admin-export/", meeting_admin.export_excel_api),
    path("api/meeting-admin-export-template/", meeting_admin.export_template_api),
    # 工资标准维护
    path("salary-standard/", salary_standard.page),
    path("api/salary-standard-list/", salary_standard.list_api),
    path("api/salary-standard-filters/", salary_standard.filters_api),
    path("api/salary-standard-save/", salary_standard.save_api),
    path("api/salary-standard-delete/", salary_standard.delete_api),
]
