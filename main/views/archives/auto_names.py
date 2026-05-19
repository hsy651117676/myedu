from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
import sqlite3
import os
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json



@login_required
def archives_auto_view(request):
    return render(request, "system/archives_auto.html")


@login_required
def archives_auto_list_api(request):
    """材料名称列表"""
    keyword = request.GET.get("keyword", "")
    fl = request.get.get("fl", "")
    page = int(request.get.get("page", 1))
    page_size = int(request.GET.get("pageSize", 30))

    db_path = os.path.join(settings.BASE_DIR, "DasArchivesAuto.s3db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    sql = "SELECT id, archivesName, flName, updateTime FROM ArchivesAuto WHERE 1=1"
    params = []
    if keyword:
        sql += " AND archivesName LIKE ?"
        params.append(f"%{keyword}%")
    if fl:
        sql += " AND flName = ?"
        params.append(fl)

    # 总数
    count_sql = sql.replace(
        "SELECT id, archivesName, flName, updateTime", "SELECT COUNT(*)"
    )
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]

    # 分页
    sql += " ORDER BY id LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    cursor.execute(sql, params)
    rows = [
        {"id": r[0], "archivesName": r[1], "flName": r[2], "updateTime": r[3]}
        for r in cursor.fetchall()
    ]

    cursor.close()
    conn.close()
    return JsonResponse({"code": 0, "data": rows, "total": total})


@login_required
@csrf_exempt
def archives_auto_save_api(request):
    """保存材料名称"""
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    db_path = os.path.join(settings.BASE_DIR, "DasArchivesAuto.s3db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    action = data.get("action")
    if action == "add":
        cursor.execute(
            "INSERT INTO ArchivesAuto (archivesName, flName, updateTime) VALUES (?, ?, datetime('now'))",
            (data.get("archivesName", ""), data.get("flName", "")),
        )
    elif action == "update":
        cursor.execute(
            "UPDATE ArchivesAuto SET archivesName=?, flName=?, updateTime=datetime('now') WHERE id=?",
            (data.get("archivesName", ""), data.get("flName", ""), data.get("id")),
        )
    elif action == "delete":
        cursor.execute("DELETE FROM ArchivesAuto WHERE id=?", (data.get("id"),))

    conn.commit()
    cursor.close()
    conn.close()
    return JsonResponse({"code": 0, "msg": "操作成功"})


@login_required
def archives_auto_fl_api(request):
    """获取所有分类"""
    db_path = os.path.join(settings.BASE_DIR, "DasArchivesAuto.s3db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT flName FROM ArchivesAuto ORDER BY flName")
    rows = [r[0] for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return JsonResponse({"code": 0, "data": rows})


@login_required
def archives_auto_export_api(request):
    """生成材料名称 JS 文件，按分类分组"""
    db_path = os.path.join(settings.BASE_DIR, "DasArchivesAuto.s3db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT flName, archivesName FROM ArchivesAuto WHERE archivesName IS NOT NULL AND archivesName != '' ORDER BY flName, archivesName"
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    groups = {}
    for fl, name in rows:
        if fl not in groups:
            groups[fl] = []
        groups[fl].append(name)

    data = [{"fl": k, "names": v} for k, v in groups.items()]

    js_content = (
        "window.ARCHIVES_AUTO_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n"
    )

    flat = []
    for g in data:
        for n in g["names"]:
            flat.append(f"{g['fl']} - {n}")
    js_content += (
        "window.ARCHIVES_AUTO_FLAT = " + json.dumps(flat, ensure_ascii=False) + ";\n"
    )

    js_dir = os.path.join(settings.BASE_DIR, "static", "js")
    os.makedirs(js_dir, exist_ok=True)
    js_path = os.path.join(js_dir, "archives_auto_names.js")

    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_content)

    return JsonResponse(
        {"code": 0, "msg": f"已生成，共 {len(rows)} 条，{len(groups)} 个分类"}
    )
