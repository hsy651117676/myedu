from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from main.db_utils import _get_conn
import json
import os
import logging

logger = logging.getLogger(__name__)


@login_required
def archives_auto_view(request):
    return render(request, "archivesSystem/archives_auto.html")


@login_required
def archives_auto_list_api(request):
    keyword = request.GET.get("keyword", "")
    fl = request.GET.get("fl", "")
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 30))
    offset = (page - 1) * page_size

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        where = "WHERE 1=1"
        params = []
        if keyword:
            where += " AND ArchivesName LIKE ?"
            params.append(f"%{keyword}%")
        if fl:
            where += " AND FL = ?"
            params.append(int(fl))

        cursor.execute(f"SELECT COUNT(*) FROM ArchivesAuto {where}", params)
        total = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT ID, FL, FlName, Number, ArchivesName, UpdateTime
            FROM ArchivesAuto {where}
            ORDER BY ID
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """, params)
        rows = [{"id": r[0], "fl": r[1], "flName": r[2], "number": r[3], "archivesName": r[4], "updateTime": str(r[5])} for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@csrf_exempt
def archives_auto_save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        action = data.get("action")
        if action == "add":
            cursor.execute(
                "INSERT INTO ArchivesAuto (FL, FlName, Number, ArchivesName) VALUES (?, ?, ?, ?)",
                (data.get("fl", 0), data.get("flName", ""), data.get("number", ""), data.get("archivesName", ""))
            )
        elif action == "update":
            cursor.execute(
                "UPDATE ArchivesAuto SET FL=?, FlName=?, Number=?, ArchivesName=?, UpdateTime=GETDATE() WHERE ID=?",
                (data.get("fl", 0), data.get("flName", ""), data.get("number", ""), data.get("archivesName", ""), data.get("id"))
            )
        elif action == "delete":
            cursor.execute("DELETE FROM ArchivesAuto WHERE ID=?", (data.get("id"),))

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


@login_required
def archives_auto_fl_api(request):
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT FL, FlName FROM ArchivesAuto WHERE FlName IS NOT NULL ORDER BY FlName")
        rows = [{"fl": r[0], "flName": r[1]} for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def archives_auto_export_api(request):
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT FlName, ArchivesName FROM ArchivesAuto WHERE ArchivesName IS NOT NULL AND ArchivesName != '' ORDER BY FlName, ArchivesName"
        )
        rows = cursor.fetchall()
        cursor.close()

        groups = {}
        for fl, name in rows:
            if fl not in groups:
                groups[fl] = []
            groups[fl].append(name)

        data = [{"fl": k, "names": v} for k, v in groups.items()]
        js_content = "window.ARCHIVES_AUTO_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n"

        flat = []
        for g in data:
            for n in g["names"]:
                flat.append(f"{g['fl']} - {n}")
        js_content += "window.ARCHIVES_AUTO_FLAT = " + json.dumps(flat, ensure_ascii=False) + ";\n"

        js_dir = os.path.join(settings.BASE_DIR, "static", "js")
        os.makedirs(js_dir, exist_ok=True)
        js_path = os.path.join(js_dir, "archives_auto_names.js")

        with open(js_path, "w", encoding="utf-8") as f:
            f.write(js_content)

        return JsonResponse({"code": 0, "msg": f"已生成，共 {len(rows)} 条，{len(groups)} 个分类"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
