import os
from django.conf import settings
from django.http import HttpResponse
from django.urls import path
from main.views.components import person_search, org_tree, archive_tree, scan_stats

app_name = "components"


def person_panel_embed(request):
    path = os.path.join(
        settings.BASE_DIR, "templates", "components", "person_panel_embed.html"
    )
    with open(path, "r", encoding="utf-8") as f:
        return HttpResponse(f.read())


def archive_tree_embed(request):
    path = os.path.join(
        settings.BASE_DIR, "templates", "components", "archive_tree_embed.html"
    )
    with open(path, "r", encoding="utf-8") as f:
        return HttpResponse(f.read())


def unit_tree_embed(request):
    path = os.path.join(
        settings.BASE_DIR, "templates", "components", "unit_tree_embed.html"
    )
    with open(path, "r", encoding="utf-8") as f:
        return HttpResponse(f.read())


urlpatterns = [
    # 页面
    path("person-panel-embed/", person_panel_embed, name="person_panel_embed"),
    path("archive-tree-embed/", archive_tree_embed, name="archive_tree_embed"),
    path("unit-tree-embed/", unit_tree_embed, name="unit_tree_embed"),
    # API
    path("person-search/", person_search.person_search_api, name="person_search"),
    path("tree/", org_tree.tree_root_api, name="tree_root"),
    path("tree-children/", org_tree.tree_children_api, name="tree_children"),
    path("archive-tree/", archive_tree.archive_tree_api, name="archive_tree"),
    path("scan-stats/", scan_stats.scan_stats_api, name="scan_stats"),
    path(
        "archive-tree-all/", archive_tree.archive_tree_all_api, name="archive-tree-all"
    ),
]
