from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    real_name = models.CharField('真实姓名', max_length=20, blank=True)
    phone = models.CharField('联系电话', max_length=11, blank=True)
    id_card = models.CharField('身份证号', max_length=18, blank=True)
    address = models.CharField('居住地址', max_length=200, blank=True)
    create_time = models.DateTimeField(auto_now_add=True)
    update_time = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '用户扩展信息'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.real_name or self.user.username
