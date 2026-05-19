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

logger = logging.getLogger(__name__)
DEFAULT_PWD = "12345abcde"


@login_required
def page(request):
    return render(request, "system/users/archive_users.html")


@login_required
def depart_list_api(request):
    """单位列表"""
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

        cursor.execute(f"SELECT COUNT(*) FROM USERS u LEFT JOIN USERPOWER p ON u.YHBH = p.YHBH {where}")
        total = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT u.YHBH, u.USERID, u.YHMC, u.ZW, u.DEPARTID,
                   ISNULL(d.BMMC, '未分配') AS DEPART_NAME,
                   u.LX, u.ZBH, u.JGQX, u.DOORSTR, u.HANDSTR,
                   ISNULL(p.SCAN, 0) AS SCAN,
                   ISNULL(p.CHECKARCH, 0) AS CHECKARCH,
                   ISNULL(p.PRINTVIEW, 0) AS PRINTVIEW,
                   ISNULL(p.RCYW, 0) AS RCYW,
                   ISNULL(p.SYSTEMMANA, 0) AS SYSTEMMANA
            FROM USERS u
            LEFT JOIN DEPART d ON u.DEPARTID = d.BM
            LEFT JOIN USERPOWER p ON u.YHBH = p.YHBH
            {where}
            ORDER BY u.YHBH
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """)
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()

@login_required
@csrf_exempt
def save_api(request):
    """保存：添加/更新/删除/重置密码"""
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
            # 获取新插入的 YHBH
            cursor.execute("SELECT SCOPE_IDENTITY()")
            new_yhbh = cursor.fetchone()[0]
            # 插 USERPOWER
            cursor.execute("""
                INSERT INTO USERPOWER (YHBH, SCAN, CHECKARCH, PRINTVIEW, RCYW, SYSTEMMANA)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (new_yhbh,
                data.get("SCAN", 0), data.get("CHECKARCH", 0),
                data.get("PRINTVIEW", 0), data.get("RCYW", 0),
                data.get("SYSTEMMANA", 0)))

        elif action == "update":
            rows = data.get("rows", [])
            for r in rows:
                yhbh = r.get("YHBH")
                cursor.execute("""
                    UPDATE USERS SET YHMC=?, ZW=?, DEPARTID=?, LX=?, ZBH=?,
                    JGQX=?, DOORSTR=?, HANDSTR=? WHERE YHBH=?
                """, (
                    r.get("YHMC", ""), r.get("ZW", ""),
                    r.get("DEPARTID") or None, r.get("LX"),
                    r.get("ZBH"), r.get("JGQX", ""),
                    r.get("DOORSTR", ""), r.get("HANDSTR", ""), yhbh
                ))
                # 更新或插入 USERPOWER
                cursor.execute("SELECT COUNT(*) FROM USERPOWER WHERE YHBH=?", (yhbh,))
                if cursor.fetchone()[0] > 0:
                    cursor.execute("""
                        UPDATE USERPOWER SET SCAN=?, CHECKARCH=?, PRINTVIEW=?,
                        RCYW=?, SYSTEMMANA=? WHERE YHBH=?
                    """, (
                        r.get("SCAN", 0), r.get("CHECKARCH", 0),
                        r.get("PRINTVIEW", 0), r.get("RCYW", 0),
                        r.get("SYSTEMMANA", 0), yhbh
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO USERPOWER (YHBH, SCAN, CHECKARCH, PRINTVIEW, RCYW, SYSTEMMANA)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (yhbh,
                        r.get("SCAN", 0), r.get("CHECKARCH", 0),
                        r.get("PRINTVIEW", 0), r.get("RCYW", 0),
                        r.get("SYSTEMMANA", 0)))

        elif action == "delete":
            ids = data.get("ids", [])
            for yhbh in ids:
                cursor.execute("DELETE FROM USERPOWER WHERE YHBH=?", (yhbh,))
                cursor.execute("DELETE FROM USERS WHERE YHBH=?", (yhbh,))

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
