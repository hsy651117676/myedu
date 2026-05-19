from django.urls import path
from main.views.business import organization
from main.views.business import archive_read
from . import archive_borrow
from . import archive_transfer
from . import archive_receive
from . import query_stats

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
    path("stats/", query_stats.stats_page, name="query-stats"),
    path("api/stats/", query_stats.stats_api, name="stats-api"),


    # 机构维护
    path('organization/', organization.organization_view, name='organization'),
    path('organization/api/search/', organization.person_search_api, name='org_search'),
    path('organization/api/detail/', organization.person_detail_api, name='org_detail'),
    path('organization/api/save/', organization.person_save_api, name='org_save'),
    path('organization/api/transfer/', organization.person_transfer_api, name='org_transfer'),
    path('organization/api/tree/', organization.org_tree_api, name='org_tree'),
    path('organization/api/tree-children/', organization.org_tree_children_api, name='org_tree_children'),
    path('organization/api/save-and-transfer/', organization.save_and_transfer_api, name='org_save_transfer'),
]
