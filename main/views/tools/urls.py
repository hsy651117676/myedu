import os
from django.conf import settings
from django.http import HttpResponse
from django.urls import path
from . import html5piano
from . import markdown
from . import mediaplayer

app_name = "tools"


urlpatterns = [
    path("linux/", html5piano.linux, name="tools_linux"),
    path("encrypt/", html5piano.encrypt, name="tools_encrypt"),
    path("decrypt/", html5piano.decrypt, name="tools_decrypt"),
    path("piano/", html5piano.piano, name="tools_html5piano"),
    path("diary/", markdown.page, name="diary"),
    path("api/diary/list/", markdown.list_api, name="diary-list"),
    path("api/diary/detail/", markdown.detail_api, name="diary-detail"),
    path("api/diary/save/", markdown.save_api, name="diary-save"),
    path("api/diary/delete/", markdown.delete_api, name="diary-delete"),
    # 多媒体
    path("media/", mediaplayer.player_page),
    path("media/manage/", mediaplayer.manage_page),
    path("api/media/list/", mediaplayer.list_api),
    path("api/media/play/", mediaplayer.play_api),
    path("api/media/upload/", mediaplayer.upload_api),
    path("api/media/delete/", mediaplayer.delete_api),
    path("api/media/letters/", mediaplayer.letters_api),
    path("api/media/instruments/", mediaplayer.instruments_api),
    path("api/media/styles/", mediaplayer.styles_api),
    path("api/media/edit/", mediaplayer.edit_api),
    path("api/media/cover/", mediaplayer.cover_api),
]
