# main/views/archives/image/scan_stats.py
"""
扫描情况统计 - API 接口
"""

import json
import logging

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.cache import cache

from main.utils.decorators import archive_perm_required, _is_admin
from main.utils import _get_conn, query_dict

logger = logging.getLogger(__name__)


@login_required
@archive_perm_required
def page(request):
    return render(request, "archives/image/scan_stats.html")


@login_required
def unit_list_api(request):
    """单位列表（管理员全部，普通用户仅本单位）"""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("{CALL z_selectname(0, '')}")
    cols = [c[0] for c in cursor.description]
    rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
    cursor.close()
    conn.close()

    if not _is_admin(request):
        archive_user = request.session.get("archive_user", {})
        depart_id = int(archive_user.get("depart_id", 0))
        rows = [r for r in rows if r.get("序号") == depart_id]

    return JsonResponse({"code": 0, "data": rows})


@login_required
def stats_api(request):
    """扫描统计（缓存10分钟）"""
    unit_id = request.GET.get("unit_id", "")
    if not unit_id:
        return JsonResponse({"code": 400, "msg": "缺少单位ID"})

    if not _is_admin(request):
        archive_user = request.session.get("archive_user", {})
        allowed_depart = str(archive_user.get("depart_id", ""))
        if unit_id != allowed_depart:
            return JsonResponse({"code": 403, "msg": "无权访问其他单位"})

    cache_key = f"scan_stats:{unit_id}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse({"code": 0, "data": cached["data"], "cats": cached["cats"]})

    # 1. 该单位所有人员
    persons = query_dict(
        """SELECT RS_INFO.RSID, RS_INFO.XM AS name, RS_INFO.RYBH
           FROM USERS_DEPARTMENT
           LEFT JOIN RS_INFO ON USERS_DEPARTMENT.RSID = RS_INFO.RSID
           WHERE USERS_DEPARTMENT.DEPARTMENTID = ?
           ORDER BY RS_INFO.RYBH""",
        (int(unit_id),),
    )

    # 2. 十大类
    cats = query_dict("SELECT FL, JBBH FROM CATETREE WHERE PID=-1 ORDER BY FL")
    rsids = [p["RSID"] for p in persons]

    # 3. 一次性查所有人员的 RS_ARCHINFO（含 YS）
    all_arch = {}
    if rsids:
        placeholders = ",".join(["?"] * len(rsids))
        rows = query_dict(
            f"SELECT RSID, FL, ARCHID, YS FROM RS_ARCHINFO WHERE RSID IN ({placeholders})",
            rsids,
        )
        for r in rows:
            rsid = r["RSID"]
            fl = r["FL"]
            if rsid not in all_arch:
                all_arch[rsid] = {}
            if fl not in all_arch[rsid]:
                all_arch[rsid][fl] = {"archids": [], "total_ys": 0}
            all_arch[rsid][fl]["archids"].append(r["ARCHID"])
            all_arch[rsid][fl]["total_ys"] += r["YS"] or 0

    # 4. 一次性查所有人员的 RS_DESCRIPT 已上传页数
    all_uploaded = {}
    for rsid in rsids:
        table_name = f"RS_DESCRIPT_{rsid}"
        try:
            rows = query_dict(
                f"SELECT Archid, COUNT(*) AS cnt FROM {table_name} GROUP BY Archid"
            )
            all_uploaded[rsid] = {r["Archid"]: r["cnt"] for r in rows}
        except:
            all_uploaded[rsid] = {}

    # 5. 组装结果
    result = []
    for p in persons:
        rsid = p["RSID"]
        arch_dict = all_arch.get(rsid, {})
        uploaded_dict = all_uploaded.get(rsid, {})
        row = {
            "RSID": rsid,
            "name": p["name"],
            "categories": [],
            "total_should": 0,
            "total_done": 0,
            "total_lack": 0,
        }

        for cat in cats:
            fl = cat["FL"]
            actual_fls = [fl]
            if fl == 4:
                actual_fls = [11, 12, 13, 14]
            elif fl == 9:
                actual_fls = [15, 16, 17, 18]

            should = 0
            done = 0
            for af in actual_fls:
                info = arch_dict.get(af, {"archids": [], "total_ys": 0})
                should += info["total_ys"]
                for aid in info["archids"]:
                    done += uploaded_dict.get(aid, 0)

            lack = should - done
            row["categories"].append(
                {
                    "fl": fl,
                    "jbbh": cat["JBBH"],
                    "should": should,
                    "done": done,
                    "lack": lack,
                }
            )
            row["total_should"] += should
            row["total_done"] += done

        row["total_lack"] = row["total_should"] - row["total_done"]
        row["rate"] = (
            round(row["total_done"] / row["total_should"] * 100, 1)
            if row["total_should"] > 0
            else 0
        )
        result.append(row)

    cats_data = [{"fl": c["FL"], "jbbh": c["JBBH"]} for c in cats]
    cache.set(cache_key, {"data": result, "cats": cats_data}, 600)

    return JsonResponse({"code": 0, "data": result, "cats": cats_data})
