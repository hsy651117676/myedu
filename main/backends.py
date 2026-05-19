"""
自定义认证后端
"""
import hashlib
import logging
from django.contrib.auth.models import User
from main.db_utils import _get_conn

logger = logging.getLogger(__name__)


class ArchiveAuthBackend:
    """
    档案用户认证后端
    验证 SQL Server USERS 表，仅限内网
    """

    def authenticate(self, request, username=None, password=None, is_archive_user=False):
        if not is_archive_user:
            return None
        if not username or not password:
            return None

        conn = None
        try:
            conn = _get_conn()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT YHBH, YHMM, YHMC, DEPARTID, JGQX, USERID, ZW, DOORSTR, HANDSTR "
                "FROM USERS WHERE USERID = ?", (username,)
            )

            row = cursor.fetchone()

            if not row:
                cursor.close()
                return None

            yhbh, yhmm, yhmc, depart_id, jgqx, userid, zw, doorstr, handstr = row

            input_md5 = hashlib.md5(password.encode()).hexdigest()
            if input_md5.upper() != yhmm.upper():
                cursor.close()
                return None

            cursor.execute(
                "SELECT LURU, SCAN, CHECKARCH, PRINTVIEW, RCYW, SYSTEMMANA, DOUBLEVIEW "
                "FROM USERPOWER WHERE YHBH = ?",
                (yhbh,)
            )
            power = cursor.fetchone()
            cursor.close()
            user, created = User.objects.get_or_create(
                username=f"archive_{yhbh}",
                defaults={'email': f'{yhbh}@archive.local', 'is_active': True}
            )
            if created:
                user.set_unusable_password()
                user.save()

            from main.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.yhbh = yhbh
            profile.real_name = yhmc or ''
            profile.save()

            request.session['archive_user'] = {
                'yhbh': yhbh,
                'yhmc': yhmc or '',
                'depart_id': depart_id,
                'jgqx': jgqx or '',
                'zw': zw or '',
                'doorstr': doorstr or '',
                'handstr': handstr or '',
                'is_admin': bool(power and power[5]) if power else False,
                'can_scan': bool(power and power[1]) if power else False,
                'can_check': bool(power and power[2]) if power else False,
                'can_print': bool(power and power[3]) if power else False,
            }

            logger.info(f"档案用户登录成功: YHBH={yhbh}, YHMC={yhmc}")
            return user

        except Exception as e:
            logger.error(f"档案用户认证失败: {e}")
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
