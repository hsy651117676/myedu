from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.conf import settings
import json
import logging
import pyodbc
from contextlib import contextmanager
from functools import wraps, lru_cache
import time

logger = logging.getLogger(__name__)

# ==================== 数据库连接池配置 ====================

# 全局连接（简单连接复用）
_connection_pool = {
    'conn': None,
    'last_use': 0,
    'timeout': 300,  # 5分钟超时
}

def get_db_connection():
    """获取数据库连接（带简单复用）"""
    global _connection_pool
    
    current_time = time.time()
    
    # 如果连接存在且未超时，复用
    if (_connection_pool['conn'] and 
        current_time - _connection_pool['last_use'] < _connection_pool['timeout']):
        try:
            # 测试连接是否还活着
            _connection_pool['conn'].cursor().execute("SELECT 1")
            _connection_pool['last_use'] = current_time
            return _connection_pool['conn']
        except:
            # 连接失效，关闭并重新创建
            try:
                _connection_pool['conn'].close()
            except:
                pass
            _connection_pool['conn'] = None
    
    # 创建新连接
    db_config = getattr(settings, 'POPULATION_DB', {
        "DRIVER": "FreeTDS",
        "SERVER": "192.168.1.100",
        "PORT": "1433",
        "DATABASE": "rs_new",
        "UID": "sa",
        "PWD": "Rs_new",
        "TDS_Version": "7.2",
        "Encrypt": "No",
    })
    
    conn_str = ";".join([f"{k}={v}" for k, v in db_config.items()])
    conn = pyodbc.connect(conn_str, timeout=5)  # 5秒连接超时
    conn.timeout = 10  # 查询超时10秒
    
    _connection_pool['conn'] = conn
    _connection_pool['last_use'] = current_time
    
    return conn


@contextmanager
def get_db():
    """数据库连接上下文管理器"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        yield conn, cursor
    except pyodbc.Error as e:
        if conn:
            try:
                conn.close()
            except:
                pass
            global _connection_pool
            _connection_pool['conn'] = None
        logger.error(f"数据库错误: {e}")
        raise
    except Exception as e:
        logger.error(f"未知错误: {e}")
        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        # 不关闭连接，保留在连接池中


# ==================== 配置 ====================

CACHE_TIMEOUT = 600  # 缓存10分钟
DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 100


# ==================== 页面视图 ====================

@login_required
def person_query(request):
    return render(request, 'people/person_query.html')


@login_required
def person_manage(request):
    return render(request, 'people/person_manage.html')


@login_required
def data_change(request):
    return render(request, 'people/data_change.html')


# ==================== API视图 ====================

@login_required
def person_query_api(request):
    """人员查询API - 优化版"""
    start_time = time.time()
    
    # 获取查询参数
    name = request.GET.get("name", "").strip()
    idcard = request.GET.get("idCard", "").strip()
    address = request.GET.get("address", "").strip()
    work_unit = request.GET.get("workUnit", "").strip()
    
    # 分页参数
    try:
        page = max(1, int(request.GET.get("page", 1)))
        page_size = min(MAX_PAGE_SIZE, max(1, int(request.GET.get("pageSize", DEFAULT_PAGE_SIZE))))
    except ValueError:
        return JsonResponse({"code": 400, "msg": "分页参数错误"})
    
    # 缓存键（基于查询条件）
    cache_key = f"person_query:{name}:{idcard}:{address}:{work_unit}:{page}:{page_size}"
    cached_result = cache.get(cache_key)
    
    if cached_result:
        logger.info(f"从缓存返回结果，耗时: {time.time() - start_time:.3f}秒")
        return JsonResponse(cached_result)
    
    try:
        with get_db() as (conn, cursor):
            # 执行存储过程
            cursor.execute(
                "{CALL B_population_EDIT_W('SELECT', 0, ?, ?, '', '', '', '', '', ?, ?, '', '', '', '', ?, ?)}",
                (idcard, name, address, work_unit, page, page_size)
            )
            
            # 解析数据（只取需要的字段）
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
            
            # 获取总数
            cursor.nextset()
            total_row = cursor.fetchone()
            total = total_row[0] if total_row else 0
        
        result = {
            "code": 0,
            "data": data,
            "total": total,
            "page": page,
            "pageSize": page_size
        }
        
        # 缓存结果（有查询条件时不缓存，无条件时缓存）
        if not any([name, idcard, address, work_unit]):
            cache.set(cache_key, result, CACHE_TIMEOUT)
        
        elapsed = time.time() - start_time
        logger.info(f"查询完成，共{total}条记录，耗时: {elapsed:.3f}秒")
        
        return JsonResponse(result)
        
    except pyodbc.Error as e:
        logger.error(f"数据库查询错误: {e}")
        return JsonResponse({"code": 500, "msg": "查询失败，请稍后重试"})
    except Exception as e:
        logger.error(f"查询异常: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def person_save_api(request):
    """人员信息保存API"""
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
            # 验证人员是否存在
            cursor.execute(
                "SELECT IDCard, Name FROM B_population WHERE RSID=?",
                (rsid,)
            )
            person = cursor.fetchone()
            
            if not person:
                return JsonResponse({"code": 400, "msg": "人员不存在"})
            
            real_idcard, real_name = person
            
            # 准备更新参数
            update_params = [rsid, real_idcard, real_name]
            update_params.extend([data.get(field, "") for field in allowed_fields])
            
            # 执行更新
            cursor.execute("""
                EXEC B_population_EDIT_W 
                    @TYPE='UPDATE',
                    @RSID=?, @IDCard=?, @Name=?, 
                    @FormerName=?, @Nation=?, @Gender=?,
                    @DeathDate=?, @BirthDate=?, @HomeAddress=?, @WorkUnit=?, @Telephone=?,
                    @fatherID=?, @motherID=?, @SpouseID=?
            """, update_params)
            
            conn.commit()
            
            # 清除相关缓存
            cache.delete(f"family_{rsid}")
            # 清除查询缓存
            cache.delete_pattern("person_query:*")
        
        return JsonResponse({"code": 0, "msg": "保存成功"})
        
    except Exception as e:
        logger.error(f"保存失败: {e}")
        return JsonResponse({"code": 500, "msg": "保存失败：" + str(e)})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def key_data_update_api(request):
    """关键数据更新API"""
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
    """家庭关系查询API"""
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少RSID"})
    
    # 先从缓存获取
    cache_key = f"family_{rsid}"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return JsonResponse({"code": 0, "data": cached_data, "source": "cache"})
    
    try:
        with get_db() as (conn, cursor):
            cursor.execute("""
                EXEC B_population_EDIT_W
                    @TYPE='QUERY',
                    @RSID=?,
                    @IDCard='',@Name='',@FormerName='',@Nation='',@Gender='',
                    @DeathDate='',@BirthDate='',@HomeAddress='',@WorkUnit='',@Telephone='',
                    @fatherID='',@motherID='',@SpouseID=''
            """, (rsid,))
            
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
