from django.urls import path
from . import people

urlpatterns = [
    path("query/", people.person_query, name="person-query"),
    path("manage/", people.person_manage, name="person-manage"),
    path("data-change/", people.data_change, name="data-change"),
    path("api/person-query/", people.person_query_api, name="person-query-api"),
    path("api/family-query/", people.family_query_api, name="family-query-api"),
    path("api/person-save/", people.person_save_api, name="person-save-api"),
    path("api/key-data-update/", people.key_data_update_api, name="key-data-update-api"),
]
