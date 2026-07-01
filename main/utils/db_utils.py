# main/db_utils.py
import logging
import threading
import time

import pyodbc
from django.conf import settings

logger = logging.getLogger(__name__)

# ==================== 配置 ====================

CONN_TIMEOUT = 300  # 连接空闲超时（秒）
CONNECT_TIMEOUT = 5  # 建立连接超时（秒）
QUERY_TIMEOUT = 30  # 单次查询超时（秒）
MAX_RETRIES = 3  # 死锁最大重试次数
RETRY_DELAY = 0.5  # 重试基础间隔（秒）
HEALTH_CHECK_SQL = "SELECT 1"

# ==================== 线程本地存储 ====================

_local = threading.local()


def _get_conn(db_alias="ARCHIVES_DB"):
    """
    获取线程本地数据库连接

    Args:
        db_alias: 数据库配置别名，默认 'ARCHIVES_DB'，也可传 'POPULATION_DB'
    """
    now = time.time()
    conn_attr = f"conn_{db_alias}"
    last_use_attr = f"last_use_{db_alias}"

    conn = getattr(_local, conn_attr, None)
    last_use = getattr(_local, last_use_attr, 0)
    thread_id = threading.get_ident()

    # ----- 连接存在且未超时 -----
    if conn and (now - last_use) < CONN_TIMEOUT:
        try:
            cursor = conn.cursor()
            cursor.execute(HEALTH_CHECK_SQL)
            cursor.close()
            setattr(_local, last_use_attr, now)
            return conn
        except pyodbc.Error as e:
            logger.warning(f"[线程{thread_id}] {db_alias} 连接已断开，重新创建: {e}")
            _safe_close(conn)
            setattr(_local, conn_attr, None)
        except Exception as e:
            logger.warning(f"[线程{thread_id}] {db_alias} 健康检查异常: {e}")
            _safe_close(conn)
            setattr(_local, conn_attr, None)

    # ----- 连接超时 -----
    if conn and (now - last_use) >= CONN_TIMEOUT:
        logger.info(f"[线程{thread_id}] {db_alias} 连接超时，关闭重建")
        _safe_close(conn)
        setattr(_local, conn_attr, None)

    # ----- 创建新连接 -----
    db_config = getattr(settings, db_alias)

    conn_str = (
        f"DRIVER={{{db_config['DRIVER']}}};"
        f"SERVER={db_config['SERVER']},{db_config['PORT']};"
        f"DATABASE={db_config['DATABASE']};"
        f"UID={db_config['UID']};"
        f"PWD={db_config['PWD']};"
        f"Encrypt={db_config.get('Encrypt', 'Optional')};"
        f"TrustServerCertificate={db_config.get('TrustServerCertificate', 'Yes')};"
        f"Connection Timeout={CONNECT_TIMEOUT};"
    )

    try:
        conn = pyodbc.connect(conn_str, timeout=CONNECT_TIMEOUT)
        conn.timeout = QUERY_TIMEOUT
        conn.autocommit = False

        setattr(_local, conn_attr, conn)
        setattr(_local, last_use_attr, now)
        logger.debug(
            f"[线程{thread_id}] {db_alias} 新建连接: {db_config['SERVER']}:{db_config['PORT']}/{db_config['DATABASE']}"
        )
        return conn

    except pyodbc.Error as e:
        logger.error(f"[线程{thread_id}] {db_alias} 连接失败: {e}")
        raise
    except Exception as e:
        logger.error(f"[线程{thread_id}] {db_alias} 未知连接错误: {e}")
        raise


def _safe_close(conn):
    """安全关闭连接"""
    try:
        conn.close()
    except Exception:
        pass


def close_conn(db_alias="ARCHIVES_DB"):
    """手动关闭当前线程的连接"""
    conn_attr = f"conn_{db_alias}"
    last_use_attr = f"last_use_{db_alias}"
    conn = getattr(_local, conn_attr, None)
    if conn:
        _safe_close(conn)
        setattr(_local, conn_attr, None)
        setattr(_local, last_use_attr, 0)


def query_dict(sql, params=None, db_alias="ARCHIVES_DB"):
    """执行查询，返回字典列表"""
    conn = _get_conn(db_alias)
    cursor = conn.cursor()
    try:
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()


def execute_sql(sql, params=None, db_alias="ARCHIVES_DB"):
    """执行增删改SQL，自动重试死锁"""
    last_error = None

    for attempt in range(MAX_RETRIES):
        conn = _get_conn(db_alias)
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            conn.commit()
            return cursor.rowcount

        except pyodbc.Error as e:
            _safe_rollback(conn)
            error_code = e.args[0] if e.args else ""

            if (
                "1205" in str(error_code) or "1222" in str(error_code)
            ) and attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (attempt + 1)
                logger.warning(f"死锁/锁超时，第{attempt + 1}次重试（{delay}s后）: {e}")
                time.sleep(delay)
                last_error = e
                continue

            raise

        except Exception as e:
            _safe_rollback(conn)
            logger.error(f"SQL执行失败: {e}")
            raise

        finally:
            cursor.close()

    raise last_error


def _safe_rollback(conn):
    """安全回滚"""
    try:
        conn.rollback()
    except Exception:
        pass


def call_proc(proc_name, *params, db_alias="ARCHIVES_DB"):
    """调用存储过程，返回所有结果集"""
    conn = _get_conn(db_alias)
    cursor = conn.cursor()
    results = []

    try:
        placeholders = ",".join(["?"] * len(params))
        cursor.execute(f"{{CALL {proc_name}({placeholders})}}", params)

        if cursor.description:
            columns = [col[0] for col in cursor.description]
            results.append([dict(zip(columns, row)) for row in cursor.fetchall()])

        while cursor.nextset():
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                results.append([dict(zip(columns, row)) for row in cursor.fetchall()])

        return results

    finally:
        cursor.close()
        conn.commit()
