from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.conf import settings
import json
import logging
from contextlib import contextmanager
import time

from main.db_utils import _get_conn

logger = logging.getLogger(__name__)

# ==================== 配置 ====================

CACHE_TIMEOUT = 600
DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 100


# ==================== 上下文管理器 ====================

@contextmanager
def get_db():
    """数据库连接上下文管理器"""
    conn = None
    cursor = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        yield conn, cursor
    except Exception as e:
        logger.error(f"数据库错误: {e}")
        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass


# ==================== 页面视图 ====================

@login_required
def person_query(request):
    return render(request, 'population/person_query.html')


@login_required
def person_manage(request):
    return render(request, 'population/person_manage.html')


@login_required
def data_change(request):
    return render(request, 'population/data_change.html')


# ==================== API视图 ====================

@login_required
def person_query_api(request):
    """人员查询API"""
    start_time = time.time()
    
    name = request.GET.get("name", "").strip()
    idcard = request.GET.get("idCard", "").strip()
    address = request.GET.get("address", "").strip()
    work_unit = request.GET.get("workUnit", "").strip()
    
    try:
        page = max(1, int(request.GET.get("page", 1)))
        page_size = min(MAX_PAGE_SIZE, max(1, int(request.GET.get("pageSize", DEFAULT_PAGE_SIZE))))
    except ValueError:
        return JsonResponse({"code": 400, "msg": "分页参数错误"})
    
    cache_key = f"person_query:{name}:{idcard}:{address}:{work_unit}:{page}:{page_size}"
    cached_result = cache.get(cache_key)
    
    if cached_result:
        logger.info(f"从缓存返回，耗时: {time.time() - start_time:.3f}s")
        return JsonResponse(cached_result)
    
    try:
        with get_db() as (conn, cursor):
            cursor.execute(
                "{CALL B_population_EDIT_W(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)}",
                ('SELECT', 0, idcard, name, '', '', '', '', address, work_unit, '', '', '', '', '', page, page_size)
            )
            
            # 第一个结果集：总数
            total = cursor.fetchone()[0]
            
            # 第二个结果集：分页数据
            cursor.nextset()
            columns = [col[0] for col in cursor.description]
            data = []
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                data.append({
                    "RSID": row_dict.get("RSID"),
                    "IDCard": row_dict.get("IDCard"),
                    "Name": row_dict.get("Name"),
                    "FormerName": row_dict.get("FormerName", ""),
                    "Nation": row_dict.get("Nation", ""),
                    "Gender": row_dict.get("Gender", ""),
                    "DeathDate": row_dict.get("DeathDate", ""),
                    "BirthDate": row_dict.get("BirthDate", ""),
                    "HomeAddress": row_dict.get("HomeAddress", ""),
                    "WorkUnit": row_dict.get("WorkUnit", ""),
                    "Telephone": row_dict.get("Telephone", ""),
                    "fatherID": row_dict.get("fatherID", ""),
                    "motherID": row_dict.get("motherID", ""),
                    "SpouseID": row_dict.get("SpouseID", ""),
                })
        
        result = {
            "code": 0,
            "data": data,
            "total": total,
            "page": page,
            "pageSize": page_size
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
    """人员信息保存"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"code": 400, "msg": "参数格式错误"})
    
    rsid = data.get("RSID")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "请选择人员"})
    
    allowed_fields = [
        "FormerName", "Nation", "Gender", "DeathDate", "BirthDate",
        "HomeAddress", "WorkUnit", "Telephone",
        "fatherID", "motherID", "SpouseID"
    ]
    
    try:
        with get_db() as (conn, cursor):
            cursor.execute(
                "SELECT IDCard, Name FROM B_population WHERE RSID=?",
                (rsid,)
            )
            person = cursor.fetchone()
            if not person:
                return JsonResponse({"code": 400, "msg": "人员不存在"})
            
            real_idcard, real_name = person
            update_params = [rsid, real_idcard, real_name]
            update_params.extend([data.get(field, "") for field in allowed_fields])
            
            cursor.execute("""
                EXEC B_population_EDIT_W 
                    @TYPE='UPDATE',
                    @RSID=?, @IDCard=?, @Name=?, 
                    @FormerName=?, @Nation=?, @Gender=?,
                    @DeathDate=?, @BirthDate=?, @HomeAddress=?, @WorkUnit=?, @Telephone=?,
                    @fatherID=?, @motherID=?, @SpouseID=?
            """, update_params)
            
            conn.commit()
            cache.delete_pattern("person_query:*")
        
        return JsonResponse({"code": 0, "msg": "保存成功"})
        
    except Exception as e:
        logger.error(f"保存失败: {e}")
        return JsonResponse({"code": 500, "msg": "保存失败：" + str(e)})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def key_data_update_api(request):
    """关键数据更新"""
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
        with get_db() as (conn, cursor):
            cursor.execute("""
                SELECT RSID, IDCard, Name, FormerName, Nation, Gender, 
                       DeathDate, BirthDate, HomeAddress, WorkUnit, Telephone, 
                       fatherID, motherID, SpouseID 
                FROM B_population WHERE RSID=?
            """, (rsid,))
            
            old = cursor.fetchone()
            if not old:
                return JsonResponse({"code": 404, "msg": "未找到人员"})
            
            cursor.execute("""
                EXEC B_population_EDIT_W
                    @TYPE='UPDATE',
                    @RSID=?, @IDCard=?, @Name=?,
                    @FormerName=?, @Nation=?, @Gender=?,
                    @DeathDate=?, @BirthDate=?, @HomeAddress=?, @WorkUnit=?, @Telephone=?,
                    @fatherID=?, @motherID=?, @SpouseID=?
            """, (
                rsid, new_idcard, new_name,
                old.FormerName, old.Nation, old.Gender,
                old.DeathDate, old.BirthDate,
                old.HomeAddress, old.WorkUnit, old.Telephone,
                old.fatherID, old.motherID, old.SpouseID
            ))
            
            conn.commit()
            cache.delete_pattern("person_query:*")
        
        return JsonResponse({"code": 0, "msg": "修改成功"})
        
    except Exception as e:
        logger.error(f"关键数据更新失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
def family_query_api(request):
    """家庭关系查询"""
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少RSID"})
    
    cache_key = f"family_{rsid}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return JsonResponse({"code": 0, "data": cached_data, "source": "cache"})
    
    try:
        with get_db() as (conn, cursor):
            cursor.execute(
                "{CALL B_population_EDIT_W(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)}",
                ('QUERY', rsid, '', '', '', '', '', '', '', '', '', '', '', '', '')
            )
            
            columns = [col[0] for col in cursor.description]
            family = []
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                family.append({
                    "RSID": row_dict.get("RSID"),
                    "关系": row_dict.get("关系"),
                    "姓名": row_dict.get("姓名"),
                    "民族": row_dict.get("民族"),
                    "性别": row_dict.get("性别"),
                    "出生时间": str(row_dict.get("出生时间"))[:10] if row_dict.get("出生时间") else "",
                    "家庭住址": row_dict.get("家庭住址"),
                    "工作单位": row_dict.get("工作单位"),
                    "联系电话": row_dict.get("联系电话"),
                    "身份证号": row_dict.get("身份证号"),
                    "死亡时间": str(row_dict.get("死亡时间"))[:10] if row_dict.get("死亡时间") else "",
                    "父亲身份证号": row_dict.get("父亲身份证号"),
                    "母亲身份证号": row_dict.get("母亲身份证号"),
                    "配偶身份证号": row_dict.get("配偶身份证号"),
                })
        
        cache.set(cache_key, family, CACHE_TIMEOUT)
        return JsonResponse({"code": 0, "data": family, "source": "database"})
        
    except Exception as e:
        logger.error(f"家庭查询失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
