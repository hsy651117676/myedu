from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Menu, UserGroup, MenuGroup


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    fields = ['real_name', 'phone', 'id_card', 'address', 'yhbh']


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'parent', 'sort', 'is_active']


@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']


@admin.register(MenuGroup)
class MenuGroupAdmin(admin.ModelAdmin):
    list_display = ['menu', 'group']
