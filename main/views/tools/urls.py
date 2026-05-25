
import os
from django.conf import settings
from django.http import HttpResponse
from django.urls import path
from . import html5piano
from . import markdown

app_name = 'tools'


urlpatterns = [
    path('linux/', html5piano.linux, name='tools_linux'),
    path('encrypt/', html5piano.encrypt, name='tools_encrypt'),
    path('decrypt/', html5piano.decrypt, name='tools_decrypt'),
    path('piano/', html5piano.piano, name='tools_html5piano'),

    path('diary/', markdown.page, name='diary'),
    path('api/diary/list/', markdown.list_api, name='diary-list'),
    path('api/diary/detail/', markdown.detail_api, name='diary-detail'),
    path('api/diary/save/', markdown.save_api, name='diary-save'),
    path('api/diary/delete/', markdown.delete_api, name='diary-delete'),
]
