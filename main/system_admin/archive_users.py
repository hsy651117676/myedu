"""
SQL Server 档案用户管理
"""
import json
import hashlib
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.db_utils import _get_conn
from main.models import UserProfile
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)
DEFAULT_PWD = "12345abcde"


def _sync_platform_user(yhbh, yhmc, platform_group_id=None, delete=False):
    """同步档案用户到 MySQL auth_user + UserProfile"""
    try:
        username = f"archive_{yhbh}"
        if delete:
            User.objects.filter(username=username).delete()
            return
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': f'{yhbh}@archive.local', 'is_active': True}
        )
        if created or not user.has_usable_password():
            user.set_unusable_password()
            user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.yhbh = yhbh
        profile.real_name = yhmc or ''
        if platform_group_id is not None:
            profile.group_id = int(platform_group_id) if platform_group_id else None
        profile.save()
    except Exception as e:
        logger.warning(f"同步平台用户失败: {e}")


def _sync_userpower(conn, yhbh, scan, checkarch, printview, rcyw, systemmana):
    """同步 USERPOWER，存在更新，不存在新增"""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM USERPOWER WHERE YHBH=?", (yhbh,))
    if cursor.fetchone()[0] > 0:
        cursor.execute("""
            UPDATE USERPOWER SET SCAN=?, CHECKARCH=?, PRINTVIEW=?, RCYW=?, SYSTEMMANA=?
            WHERE YHBH=?
        """, (scan, checkarch, printview, rcyw, systemmana, yhbh))
    else:
        cursor.execute("""
            INSERT INTO USERPOWER (YHBH, SCAN, CHECKARCH, PRINTVIEW, RCYW, SYSTEMMANA)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (yhbh, scan, checkarch, printview, rcyw, systemmana))


@login_required
def page(request):
    return render(request, "system/users/archive_users.html")


@login_required
def depart_list_api(request):
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT BM, BMMC FROM DEPART ORDER BY BM")
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def query_api(request):
    depart_id = request.GET.get("departId", "").strip()
    unassigned = request.GET.get("unassigned", "").strip()
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 30))
    offset = (page - 1) * page_size

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if unassigned:
            where = "WHERE u.DEPARTID IS NULL OR u.DEPARTID = '0' OR u.DEPARTID = ''"
        elif depart_id:
            where = f"WHERE u.DEPARTID = '{depart_id}'"
        else:
            cursor.close()
            return JsonResponse({"code": 0, "data": [], "total": 0})

        cursor.execute(f"SELECT COUNT(*) FROM USERS u {where}")
        total = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT u.YHBH, u.USERID, u.YHMC, u.ZW, u.DEPARTID,
                   ISNULL(d.BMMC, '未分配') AS DEPART_NAME,
                   u.LX, u.ZBH, u.JGQX, u.DOORSTR, u.HANDSTR,
                   ISNULL(pw.SCAN, 0) AS SCAN,
                   ISNULL(pw.CHECKARCH, 0) AS CHECKARCH,
                   ISNULL(pw.PRINTVIEW, 0) AS PRINTVIEW,
                   ISNULL(pw.RCYW, 0) AS RCYW,
                   ISNULL(pw.SYSTEMMANA, 0) AS SYSTEMMANA
            FROM USERS u
            LEFT JOIN DEPART d ON u.DEPARTID = d.BM
            LEFT JOIN USERPOWER pw ON u.YHBH = pw.YHBH
            {where}
            ORDER BY u.YHBH
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """)
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()

        # 从 MySQL 批量查 group_id
        yhbh_list = [r['YHBH'] for r in rows if r.get('YHBH')]
        if yhbh_list:
            profiles = UserProfile.objects.filter(yhbh__in=yhbh_list).values('yhbh', 'group_id')
            profile_map = {p['yhbh']: p['group_id'] for p in profiles}
            for r in rows:
                r['platformGroupId'] = profile_map.get(r['YHBH'])
        else:
            for r in rows:
                r['platformGroupId'] = None

        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@csrf_exempt
def save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    action = data.get("action")
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if action == "add":
            md5_pwd = hashlib.md5(DEFAULT_PWD.encode()).hexdigest()
            cursor.execute("""
                INSERT INTO USERS (USERID, YHMM, YHMC, ZW, DEPARTID, LX, ZBH, JGQX, DOORSTR, HANDSTR)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get("USERID", ""), md5_pwd,
                data.get("YHMC", ""), data.get("ZW", ""),
                data.get("DEPARTID") or None,
                data.get("LX"), data.get("ZBH"), data.get("JGQX", ""),
                data.get("DOORSTR", ""), data.get("HANDSTR", "")
            ))
            cursor.execute("SELECT SCOPE_IDENTITY()")
            new_yhbh = cursor.fetchone()[0]
            _sync_userpower(conn, new_yhbh,
                data.get("SCAN", 0), data.get("CHECKARCH", 0),
                data.get("PRINTVIEW", 0), data.get("RCYW", 0),
                data.get("SYSTEMMANA", 0))
            _sync_platform_user(new_yhbh, data.get("YHMC", ""))

        elif action == "update":
            rows = data.get("rows", [])
            for r in rows:
                yhbh = r.get("YHBH")
                # 查 USERS 是否存在
                cursor.execute("SELECT COUNT(*) FROM USERS WHERE YHBH=?", (yhbh,))
                if cursor.fetchone()[0] > 0:
                    cursor.execute("""
                        UPDATE USERS SET YHMC=?, ZW=?, DEPARTID=?, LX=?, ZBH=?,
                        JGQX=?, DOORSTR=?, HANDSTR=? WHERE YHBH=?
                    """, (
                        r.get("YHMC", ""), r.get("ZW", ""),
                        r.get("DEPARTID") or None, r.get("LX"),
                        r.get("ZBH"), r.get("JGQX", ""),
                        r.get("DOORSTR", ""), r.get("HANDSTR", ""), yhbh
                    ))
                else:
                    md5_pwd = hashlib.md5(DEFAULT_PWD.encode()).hexdigest()
                    cursor.execute("""
                        INSERT INTO USERS (YHBH, USERID, YHMM, YHMC, ZW, DEPARTID, LX, ZBH, JGQX, DOORSTR, HANDSTR)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (yhbh, r.get("USERID", ""), md5_pwd,
                        r.get("YHMC", ""), r.get("ZW", ""),
                        r.get("DEPARTID") or None, r.get("LX"),
                        r.get("ZBH"), r.get("JGQX", ""),
                        r.get("DOORSTR", ""), r.get("HANDSTR", "")))
                _sync_userpower(conn, yhbh,
                    r.get("SCAN", 0), r.get("CHECKARCH", 0),
                    r.get("PRINTVIEW", 0), r.get("RCYW", 0),
                    r.get("SYSTEMMANA", 0))
                _sync_platform_user(yhbh, r.get("YHMC", ""), r.get("platformGroupId"))

        elif action == "delete":
            ids = data.get("ids", [])
            for yhbh in ids:
                cursor.execute("SELECT COUNT(*) FROM USERS WHERE YHBH=?", (yhbh,))
                if cursor.fetchone()[0] > 0:
                    cursor.execute("DELETE FROM USERPOWER WHERE YHBH=?", (yhbh,))
                    cursor.execute("DELETE FROM USERS WHERE YHBH=?", (yhbh,))
                _sync_platform_user(yhbh, "", delete=True)

        elif action == "reset_pwd":
            ids = data.get("ids", [])
            md5_pwd = hashlib.md5(DEFAULT_PWD.encode()).hexdigest()
            for yhbh in ids:
                cursor.execute("UPDATE USERS SET YHMM=? WHERE YHBH=?", (md5_pwd, yhbh))

        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "操作成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
