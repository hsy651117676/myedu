import logging
import threading
import time

import pyodbc
from django.conf import settings

logger = logging.getLogger(__name__)

_local = threading.local()
CONN_TIMEOUT = 300


def _get_conn():
    now = time.time()
    conn = getattr(_local, "conn", None)
    last_use = getattr(_local, "last_use", 0)

    if conn and now - last_use < CONN_TIMEOUT:
        try:
            conn.cursor().execute("SELECT 1")
            _local.last_use = now
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            _local.conn = None

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
        _local.conn = conn
        _local.last_use = now
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        raise


def query_dict(sql):
    """执行SQL查询，返回字典列表"""
    conn = _get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()


def execute_sql(sql):
    """执行增删改SQL，返回影响行数"""
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
