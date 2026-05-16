from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator


class Menu(models.Model):
    """菜单表"""
    name = models.CharField('菜单名称', max_length=50)
    url = models.CharField('URL', max_length=200)
    icon = models.CharField('图标', max_length=50, blank=True, default='')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name='父菜单')
    sort = models.IntegerField('排序', default=0)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'main_menu'
        verbose_name = '菜单'
        verbose_name_plural = '菜单'
        ordering = ['sort']

    def __str__(self):
        return self.name


class UserGroup(models.Model):
    """用户组"""
    name = models.CharField('组名称', max_length=50)
    code = models.CharField('组代码', max_length=50, unique=True)
    description = models.CharField('描述', max_length=200, blank=True, default='')
    menus = models.ManyToManyField(Menu, through='MenuGroup', verbose_name='菜单权限')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'main_usergroup'
        verbose_name = '用户组'
        verbose_name_plural = '用户组'

    def __str__(self):
        return self.name


class MenuGroup(models.Model):
    """菜单-用户组关联"""
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE)
    group = models.ForeignKey(UserGroup, on_delete=models.CASCADE)

    class Meta:
        db_table = 'main_menugroup'
        verbose_name = '菜单权限'
        verbose_name_plural = '菜单权限'
        unique_together = ('menu', 'group')

    def __str__(self):
        return f'{self.group.name} - {self.menu.name}'


class UserProfile(models.Model):
    """用户扩展信息"""
    phone_validator = RegexValidator(regex=r'^1[3-9]\d{9}$', message='请输入有效的手机号码')
    id_card_validator = RegexValidator(regex=r'^(\d{15}|\d{17}[\dXx])$', message='请输入有效的身份证号')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name='用户')
    real_name = models.CharField('真实姓名', max_length=20, blank=True, db_index=True)
    phone = models.CharField('联系电话', max_length=11, blank=True, validators=[phone_validator])
    id_card = models.CharField('身份证号', max_length=18, blank=True, null=True, validators=[id_card_validator], unique=True)
    address = models.CharField('居住地址', max_length=200, blank=True)
    group = models.ForeignKey(UserGroup, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='用户组')
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    update_time = models.DateTimeField('更新时间', auto_now=True)
    yhbh = models.IntegerField('档案系统用户编号', null=True, blank=True, help_text='对应USERS表的YHBH')

    class Meta:
        verbose_name = '用户扩展信息'
        verbose_name_plural = '用户扩展信息'

    def __str__(self):
        return self.real_name or self.user.username
