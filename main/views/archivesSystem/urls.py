from django.urls import path
from . import log_query, common_files_browse, common_files_manage, common_files_dialog
from . import auto_names
from . import batch
from . import archive_transfer
from . import organization

urlpatterns = [
    path("log/", log_query.page, name="log-query"),
    path("api/log/types/", log_query.types_api, name="log-types"),
    path("api/log/query/", log_query.query_api, name="log-query-api"),

    path("files/", common_files_browse.browse_page, name="common-files"),
    path("api/files/categories/", common_files_browse.categories_api, name="files-categories"),
    path("api/files/years/", common_files_browse.years_api, name="files-years"),
    path("api/files/list/", common_files_browse.list_api, name="files-list"),
    path("api/files/download/", common_files_browse.download_api, name="files-download"),

    path("files/manage/", common_files_manage.manage_page, name="common-files-manage"),
    path("api/files/manage/list/", common_files_manage.manage_list_api, name="files-manage-list"),
    path("api/files/manage/persons/", common_files_manage.persons_api, name="files-persons"),
    path("api/files/manage/save/", common_files_manage.save_api, name="files-manage-save"),
    path("api/files/manage/rename/", common_files_manage.rename_api, name="files-rename"),
    path("api/files/manage/upload/", common_files_manage.upload_api, name="files-manage-upload"),

    # 文件管理
    path("files/dialog/add/", common_files_dialog.add_dialog, name="files-dialog-add"),
    path("files/dialog/edit/", common_files_dialog.edit_dialog, name="files-dialog-edit"),

    # 档案目录材料名称自动提示
    path("auto-names/", auto_names.archives_auto_view, name="archives-auto"),
    path("api/auto-names/list/", auto_names.archives_auto_list_api, name="archives-auto-list"),
    path("api/auto-names/save/", auto_names.archives_auto_save_api, name="archives-auto-save"),
    path("api/auto-names/fl/", auto_names.archives_auto_fl_api, name="archives-auto-fl"),
    path("api/auto-names/export/", auto_names.archives_auto_export_api, name="archives-auto-export"),

    # 档案目录批量添加
    path("batch/", batch.page, name="batch"),
    path("api/batch/unit-persons/", batch.unit_persons_api, name="batch-unit-persons"),
    path("api/batch/categories/", batch.category_list_api, name="batch-categories"),
    path("api/batch/existing-count/", batch.existing_count_api, name="batch-existing-count"),
    path("api/batch/insert/", batch.batch_insert_api, name="batch-insert"),
    path("api/batch/jbbh/", batch.jbbh_api, name="batch-jbbh"),

    # 档案人员调转
    path("transfer/", archive_transfer.page, name="transfer"),
    path("api/transfer/person-detail/", archive_transfer.person_detail_api, name="transfer-person-detail"),
    path("api/transfer/xs-table/", archive_transfer.xs_table_api, name="transfer-xs-table"),
    path("api/transfer/same-xs-list/", archive_transfer.same_xs_list_api, name="transfer-same-xs-list"),
    path("api/transfer/save/", archive_transfer.save_api, name="transfer-save"),

    # 机构维护
    path("organization/", organization.page, name="organization"),
    path("api/organization/tree/", organization.tree_api, name="org-tree"),
    path("api/organization/tree-children/", organization.tree_children_api, name="org-tree-children"),
    path("api/organization/detail/", organization.detail_api, name="org-detail"),
    path("api/organization/save/", organization.save_api, name="org-save"),
    path("api/organization/delete/", organization.delete_api, name="org-delete"),
    path("api/organization/sort/", organization.sort_api, name="org-sort"),
]
