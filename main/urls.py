from django.urls import path
from .views.auth import *
from .views.people import family_query_api, person_manage, data_change, person_query_api, person_save_api,person_query,key_data_update_api
from .views.home import home_view
from .views.tools import linux, encrypt, decrypt, piano
from .views.system import base_info

urlpatterns = [
    path('', home_view, name='home'),

    # 认证
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('forgot-pwd/', forgot_pwd_view, name='forgot_pwd'),
    path('send-reset-code/', send_reset_code, name='send_reset_code'),
    path('logout/', logout_view, name='logout'),
    path('change-pwd/', change_pwd, name='change_pwd'),
    path('base-info/', base_info_view, name='base_info'),

    path('captcha/', generate_captcha, name='captcha'),
    path('send-email-code/', send_email_code, name='send_email_code'),

    path('person-query/', person_query, name='person-query'),
    path('person-manage/', person_manage, name='person-manage'),
    path('data-change/', data_change, name='data-change'),

    path('api/person-query/', person_query_api, name='person-query-api'),
    path('api/family-query/', family_query_api, name='family-query-api'),
    path('api/person-save/', person_save_api, name='person-save-api'),
    path('api/key-data-update/', key_data_update_api, name='key-data-update-api'),
]
 
