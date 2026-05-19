from django.urls import path
from . import log_query

urlpatterns = [
    path("log/", log_query.page, name="log-query"),
    path("api/log/types/", log_query.types_api, name="log-types"),
    path("api/log/query/", log_query.query_api, name="log-query-api"),
]
