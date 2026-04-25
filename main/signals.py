"""
main应用的信号处理
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.cache import cache
from .models import UserProfile
import logging

logger = logging.getLogger('main')


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """用户创建时自动创建扩展信息"""
    if created:
        UserProfile.objects.get_or_create(user=instance)
        logger.info(f"为新用户 {instance.username} 创建扩展信息")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """用户保存时同步保存扩展信息"""
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_save, sender=UserProfile)
def clear_user_cache(sender, instance, **kwargs):
    """用户信息更新时清除缓存"""
    cache_key = f'user_real_name_{instance.user.id}'
    cache.delete(cache_key)
    logger.debug(f"清除用户 {instance.user.username} 的缓存")


@receiver(post_delete, sender=UserProfile)
def delete_user_profile(sender, instance, **kwargs):
    """用户扩展信息删除时记录日志"""
    logger.info(f"用户 {instance.user.username} 的扩展信息被删除")
