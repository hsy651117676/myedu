from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
import sqlite3
import os
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json


def base_info(request):
    return render(request, "base_info.html")


@login_required
def placeholder(request, path=None):
    return render(request, "placeholder.html", {"path": path or request.path})

@login_required
def user_yhbh_view(request):
    keyword = request.GET.get("keyword", "").strip()
    users = []
    try:
        import pyodbc

        conn_str = ";".join([f"{k}={v}" for k, v in settings.ARCHIVES_DB.items()])
        conn = pyodbc.connect(conn_str, timeout=5)
        c = conn.cursor()
        if keyword:
            c.execute(
                """
                SELECT YHBH, USERID, YHMC, ZW, DOORSTR
                FROM USERS
                WHERE USERID LIKE ? OR YHMC LIKE ? OR ZW LIKE ?
                ORDER BY YHBH
                """,
                (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"),
            )
        else:
            c.execute(
                "SELECT TOP 50 YHBH, USERID, YHMC, ZW, DOORSTR FROM USERS ORDER BY YHBH"
            )
        cols = [col[0] for col in c.description]
        users = [dict(zip(cols, r)) for r in c.fetchall()]
        c.close()
        conn.close()
    except Exception as e:
        users = [{"YHBH": "错误", "USERID": str(e), "YHMC": "", "ZW": "", "DOORSTR": ""}]

    return render(request, "system/user_yhbh.html", {"users": users, "keyword": keyword})
