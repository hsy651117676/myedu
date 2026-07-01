"""
人口管理视图
"""

import json
import logging
import time

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.utils import _get_conn, call_proc, execute_sql, query_dict

logger = logging.getLogger(__name__)

DB = "POPULATION_DB"

CACHE_TIMEOUT = 600
DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 100

ALLOWED_FIELDS = [
    "FormerName",
    "Nation",
    "Gender",
    "DeathDate",
    "BirthDate",
    "HomeAddress",
    "WorkUnit",
    "Telephone",
    "fatherID",
    "motherID",
    "SpouseID",
]

FAMILY_FIELDS_MAP = {
    "RSID": "RSID",
    "关系": "关系",
    "姓名": "姓名",
    "民族": "民族",
    "性别": "性别",
    "出生时间": "出生时间",
    "家庭住址": "家庭住址",
    "工作单位": "工作单位",
    "联系电话": "联系电话",
    "身份证号": "身份证号",
    "死亡时间": "死亡时间",
    "父亲身份证号": "父亲身份证号",
    "母亲身份证号": "母亲身份证号",
    "配偶身份证号": "配偶身份证号",
}


@login_required
def person_query(request):
    return render(request, "population/person_query.html")


@login_required
def person_manage(request):
    return render(request, "population/person_manage.html")


@login_required
def data_change(request):
    return render(request, "population/data_change.html")


@login_required
def person_query_api(request):
    start_time = time.time()

    name = request.GET.get("name", "").strip()
    idcard = request.GET.get("idCard", "").strip()
    address = request.GET.get("address", "").strip()
    work_unit = request.GET.get("workUnit", "").strip()

    try:
        page = max(1, int(request.GET.get("page", 1)))
        page_size = min(
            MAX_PAGE_SIZE, max(1, int(request.GET.get("pageSize", DEFAULT_PAGE_SIZE)))
        )
    except ValueError:
        return JsonResponse({"code": 400, "msg": "分页参数错误"})

    cache_key = f"person_query:{name}:{idcard}:{address}:{work_unit}:{page}:{page_size}"
    cached_result = cache.get(cache_key)
    if cached_result:
        logger.info(f"从缓存返回，耗时: {time.time() - start_time:.3f}s")
        return JsonResponse(cached_result)

    try:
        results = call_proc(
            "B_population_EDIT_W",
            "SELECT",
            0,
            idcard,
            name,
            "",
            "",
            "",
            "",
            address,
            work_unit,
            "",
            "",
            "",
            "",
            "",
            page,
            page_size,
            db_alias=DB,
        )

        total = results[0][0].get(list(results[0][0].keys())[0]) if results[0] else 0
        data = []
        if len(results) > 1:
            for row in results[1]:
                data.append(
                    {
                        "RSID": row.get("RSID"),
                        "IDCard": row.get("IDCard"),
                        "Name": row.get("Name"),
                        "FormerName": row.get("FormerName", ""),
                        "Nation": row.get("Nation", ""),
                        "Gender": row.get("Gender", ""),
                        "DeathDate": row.get("DeathDate", ""),
                        "BirthDate": row.get("BirthDate", ""),
                        "HomeAddress": row.get("HomeAddress", ""),
                        "WorkUnit": row.get("WorkUnit", ""),
                        "Telephone": row.get("Telephone", ""),
                        "fatherID": row.get("fatherID", ""),
                        "motherID": row.get("motherID", ""),
                        "SpouseID": row.get("SpouseID", ""),
                    }
                )

        result = {
            "code": 0,
            "data": data,
            "total": total,
            "page": page,
            "pageSize": page_size,
        }

        if not any([name, idcard, address, work_unit]):
            cache.set(cache_key, result, CACHE_TIMEOUT)

        logger.info(f"查询完成，共{total}条，耗时: {time.time() - start_time:.3f}s")
        return JsonResponse(result)

    except Exception as e:
        logger.error(f"数据库查询错误: {e}")
        return JsonResponse({"code": 500, "msg": "查询失败，请稍后重试"})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def person_save_api(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"code": 400, "msg": "参数格式错误"})

    rsid = data.get("RSID")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "请选择人员"})

    try:
        rows = query_dict(
            "SELECT IDCard, Name FROM B_population WHERE RSID=?",
            (rsid,),
            db_alias=DB,
        )
        if not rows:
            return JsonResponse({"code": 400, "msg": "人员不存在"})

        real_idcard, real_name = rows[0]["IDCard"], rows[0]["Name"]
        update_params = [rsid, real_idcard, real_name]
        update_params.extend([data.get(f, "") for f in ALLOWED_FIELDS])

        call_proc("B_population_EDIT_W", "UPDATE", *update_params, db_alias=DB)
        cache.delete_pattern("person_query:*")
        return JsonResponse({"code": 0, "msg": "保存成功"})

    except Exception as e:
        logger.error(f"保存失败: {e}")
        return JsonResponse({"code": 500, "msg": "保存失败：" + str(e)})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def key_data_update_api(request):
    if not request.user.is_superuser:
        return JsonResponse({"code": 403, "msg": "无权限"})

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"code": 400, "msg": "参数错误"})

    rsid = data.get("RSID")
    new_name = data.get("Name", "").strip()
    new_idcard = data.get("IDCard", "").strip()

    if not all([rsid, new_name, new_idcard]):
        return JsonResponse({"code": 400, "msg": "姓名、身份证不能为空"})

    try:
        rows = query_dict(
            "SELECT FormerName, Nation, Gender, DeathDate, BirthDate, "
            "HomeAddress, WorkUnit, Telephone, fatherID, motherID, SpouseID "
            "FROM B_population WHERE RSID=?",
            (rsid,),
            db_alias=DB,
        )
        if not rows:
            return JsonResponse({"code": 404, "msg": "未找到人员"})

        old = rows[0]
        call_proc(
            "B_population_EDIT_W",
            "UPDATE",
            rsid,
            new_idcard,
            new_name,
            old["FormerName"],
            old["Nation"],
            old["Gender"],
            old["DeathDate"],
            old["BirthDate"],
            old["HomeAddress"],
            old["WorkUnit"],
            old["Telephone"],
            old["fatherID"],
            old["motherID"],
            old["SpouseID"],
            db_alias=DB,
        )

        cache.delete_pattern("person_query:*")
        return JsonResponse({"code": 0, "msg": "修改成功"})

    except Exception as e:
        logger.error(f"关键数据更新失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
def family_query_api(request):
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少RSID"})

    cache_key = f"family_{rsid}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return JsonResponse({"code": 0, "data": cached_data, "source": "cache"})

    try:
        results = call_proc(
            "B_population_EDIT_W",
            "QUERY",
            rsid,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            db_alias=DB,
        )

        family = []
        if results:
            for row in results[0]:
                item = {}
                for key, col_name in FAMILY_FIELDS_MAP.items():
                    val = row.get(col_name)
                    if key in ("出生时间", "死亡时间") and val:
                        val = str(val)[:10]
                    item[key] = val or ""
                family.append(item)

        cache.set(cache_key, family, CACHE_TIMEOUT)
        return JsonResponse({"code": 0, "data": family, "source": "database"})

    except Exception as e:
        logger.error(f"家庭查询失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
