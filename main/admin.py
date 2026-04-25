from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'real_name', 'phone', 'id_card', 'create_time']
    search_fields = ['real_name', 'phone', 'id_card', 'user__username']
    list_filter = ['create_time']
    readonly_fields = ['create_time', 'update_time']
