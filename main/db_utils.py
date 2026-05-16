import time
import pyodbc
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

_conn_pool = {"conn": None, "last_use": 0, "timeout": 300}


def _get_conn():
    now = time.time()
    
    # 检查连接池
    if _conn_pool["conn"] and now - _conn_pool["last_use"] < _conn_pool["timeout"]:
        try:
            _conn_pool["conn"].cursor().execute("SELECT 1")
            _conn_pool["last_use"] = now
            return _conn_pool["conn"]
        except:
            try:
                _conn_pool["conn"].close()
            except:
                pass
            _conn_pool["conn"] = None
    
    # 获取配置并构建 ODBC 连接字符串
    db_config = settings.ARCHIVES_DB
    
    conn_str = (
        f"DRIVER={{{db_config['DRIVER']}}};"
        f"SERVER={db_config['SERVER']},{db_config['PORT']};"
        f"DATABASE={db_config['DATABASE']};"
        f"UID={db_config['UID']};"
        f"PWD={db_config['PWD']};"
        f"TrustServerCertificate={db_config.get('TrustServerCertificate', 'Yes')};"
    )
    
    try:
        conn = pyodbc.connect(conn_str, timeout=5)
        conn.timeout = 10
        _conn_pool["conn"] = conn
        _conn_pool["last_use"] = now
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        raise
def query_dict(sql):
    """
    执行SQL查询，返回字典列表
    """
    conn = _get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()


def execute_sql(sql):
    """
    执行增删改SQL，返回影响行数
    """
    conn = _get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        conn.commit()
        return cursor.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
