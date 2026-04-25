from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
import re


class UserProfile(models.Model):
    """用户扩展信息模型"""
    
    # 字段验证器
    phone_validator = RegexValidator(
        regex=r'^1[3-9]\d{9}$',
        message='请输入有效的手机号码'
    )
    
    id_card_validator = RegexValidator(
        regex=r'^(\d{15}|\d{17}[\dXx])$',
        message='请输入有效的身份证号'
    )
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='profile',
        verbose_name='用户'
    )
    real_name = models.CharField('真实姓名', max_length=20, blank=True, db_index=True)
    phone = models.CharField(
        '联系电话', 
        max_length=11, 
        blank=True, 
        validators=[phone_validator]
    )
    id_card = models.CharField(
        '身份证号', 
        max_length=18, 
        blank=True, 
        validators=[id_card_validator],
        unique=True,  # 身份证号应该唯一
        null=True  # 允许为空
    )
    address = models.CharField('居住地址', max_length=200, blank=True)
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    update_time = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '用户扩展信息'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['real_name']),
        ]

    def __str__(self):
        return self.real_name or self.user.username
    
    def save(self, *args, **kwargs):
        # 保存前清理数据
        if self.phone:
            self.phone = self.phone.strip()
        if self.id_card:
            self.id_card = self.id_card.strip().upper()
        super().save(*args, **kwargs)
