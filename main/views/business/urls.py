from django.urls import path
from main.views.business import archive_read
from . import archive_borrow
from . import archive_transfer
from . import archive_receive
from . import query_stats
from . import transfer_print

app_name = 'business'

urlpatterns = [
    # 档案查阅
    path("look/", archive_read.page, name="archive-look"),
    path("api/look/list/", archive_read.list_api, name="look-list"),
    path("api/look/save/", archive_read.save_api, name="look-save"),
    path("api/look/persons/", archive_read.persons_api, name="look-persons"),
    path("api/look/suggest/", archive_read.suggest_api, name="look-suggest"),

    # 档案借阅
    path("borrow/", archive_borrow.page, name="archive-borrow"),
    path("api/borrow/list/", archive_borrow.list_api, name="borrow-list"),
    path("api/borrow/save/", archive_borrow.save_api, name="borrow-save"),
    path("api/borrow/persons/", archive_borrow.persons_api, name="borrow-persons"),
    path("api/borrow/suggest/", archive_borrow.suggest_api, name="borrow-suggest"),

    # 档案传递
    path("transfer/", archive_transfer.page, name="archive-transfer"),
    path("api/transfer/list/", archive_transfer.list_api, name="transfer-list"),
    path("api/transfer/save/", archive_transfer.save_api, name="transfer-save"),
    path("api/transfer/persons/", archive_transfer.persons_api, name="transfer-persons"),

    # 档案接收
    path("receive/", archive_receive.page, name="archive-receive"),
    path("api/receive/list/", archive_receive.list_api, name="receive-list"),
    path("api/receive/save/", archive_receive.save_api, name="receive-save"),
    path("api/receive/persons/", archive_receive.persons_api, name="receive-persons"),

    # 查询统计
    path("query/", query_stats.page, name="query-stats"),
    path("api/query/stats/", query_stats.stats_api, name="query-stats-api"),
    path("api/query/detail/", query_stats.detail_api, name="query-detail-api"),

    # 转递打印
    path("transfer/print/", transfer_print.print_page, name="transfer-print"),
    path("transfer/print/excel/", transfer_print.export_excel, name="transfer-print-excel"),
    path("transfer/print/pdf/", transfer_print.export_pdf, name="transfer-print-pdf"),
]
