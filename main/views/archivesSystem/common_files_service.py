"""
常用文件 - 公共服务层
"""
import os
import logging
import hashlib
import json
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)
BASE_DIR = getattr(settings, 'COMMON_FILES_BASE_DIR', '/mnt/data/ReadFiles')


def get_categories():
    cache_key = "common_files:categories"
    data = cache.get(cache_key)
    if data is not None:
        return data

    from main.db_utils import _get_conn
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT Category FROM CommonFiles WHERE IsActive=1 ORDER BY Category")
        data = [r[0] for r in cursor.fetchall()]
        cache.set(cache_key, data, 600)
        return data
    finally:
        if conn:
            conn.close()


def query_files_grouped(category="", year="", page=1, page_size=20):
    from main.db_utils import _get_conn
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        where = "WHERE f.IsActive=1"
        params = []
        if category:
            where += " AND f.Category=?"
            params.append(category)
        if year:
            where += " AND f.Year=?"
            params.append(year)

        cursor.execute(f"SELECT COUNT(*) FROM CommonFiles f {where}", params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor.execute(f"""
            SELECT f.FileNo, COUNT(p.ID) AS PersonCount, f.Year, f.ID AS FileID
            FROM CommonFiles f
            LEFT JOIN CommonFilePersons p ON f.ID = p.FileID AND p.IsActive=1
            {where}
            GROUP BY f.FileNo, f.Year, f.ID
            ORDER BY f.Year DESC, f.FileNo
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """, params)
        rows = [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]
        return rows, total
    finally:
        if conn:
            conn.close()


def query_files_flat(category="", year="", keyword="", page=1, page_size=20):
    cache_key = f"common_files:list:{hashlib.md5(json.dumps([category,year,keyword,page,page_size]).encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached.get('rows', []), cached.get('total', 0)

    from main.db_utils import _get_conn
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        where = "WHERE f.IsActive=1"
        params = []
        if category:
            where += " AND f.Category=?"
            params.append(category)
        if year:
            where += " AND f.Year=?"
            params.append(year)
        if keyword:
            where += " AND (f.FileNo LIKE ? OR p.PersonName LIKE ? OR p.Summary LIKE ?)"
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])

        cursor.execute(f"""
            SELECT COUNT(*) FROM CommonFiles f
            LEFT JOIN CommonFilePersons p ON f.ID = p.FileID AND p.IsActive=1
            {where}
        """, params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor.execute(f"""
            SELECT f.ID, f.Category, f.Year, f.FileNo, p.PersonName, p.Summary, f.FileName, f.FileSize, f.FileType, p.ID AS PersonID
            FROM CommonFiles f
            LEFT JOIN CommonFilePersons p ON f.ID = p.FileID AND p.IsActive=1
            {where}
            ORDER BY f.Year DESC, f.FileNo, p.ID
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """, params)
        rows = [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]

        cached = {'rows': rows, 'total': total}
        cache.set(cache_key, cached, 60)
        return rows, total
    finally:
        if conn:
            conn.close()


def get_file_info(file_id):
    from main.db_utils import _get_conn
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT FilePath, FileName FROM CommonFiles WHERE ID=? AND IsActive=1", (file_id,))
        row = cursor.fetchone()
        return (row[0], row[1]) if row else (None, None)
    finally:
        if conn:
            conn.close()


def build_full_path(relative_path):
    return os.path.join(BASE_DIR, relative_path) if relative_path else None


def query_persons_by_fileno(file_no):
    from main.db_utils import _get_conn
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT ID FROM CommonFiles WHERE FileNo=? AND IsActive=1", (file_no,))
        row = cursor.fetchone()
        if not row:
            return []
        file_id = row[0]

        cursor.execute("""
            SELECT p.ID, p.PersonName, p.Summary, f.FileName, f.FilePath, f.Category, f.Year, f.FileNo, f.ID AS FileID
            FROM CommonFiles f
            JOIN CommonFilePersons p ON f.ID = p.FileID AND p.IsActive=1
            WHERE f.ID=? AND p.IsActive=1
            ORDER BY p.ID
        """, (file_id,))
        return [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]
    finally:
        if conn:
            conn.close()


def delete_file(file_no):
    from main.db_utils import _get_conn
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT ID, FilePath FROM CommonFiles WHERE FileNo=? AND IsActive=1", (file_no,))
        row = cursor.fetchone()
        if row:
            full = build_full_path(row[1])
            if full and os.path.exists(full):
                os.remove(full)
            cursor.execute("UPDATE CommonFilePersons SET IsActive=0 WHERE FileID=?", (row[0],))
            cursor.execute("UPDATE CommonFiles SET IsActive=0 WHERE ID=?", (row[0],))
        conn.commit()
    finally:
        if conn:
            conn.close()


def rename_file(file_no, new_name):
    from main.db_utils import _get_conn
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT FilePath, FileName FROM CommonFiles WHERE FileNo=? AND IsActive=1", (file_no,))
        row = cursor.fetchone()
        if row and row[1] != new_name:
            new_relative = os.path.join(os.path.dirname(row[0]), new_name)
            old_full = build_full_path(row[0])
            new_full = build_full_path(new_relative)
            if old_full and os.path.exists(old_full) and not os.path.exists(new_full):
                os.rename(old_full, new_full)
            cursor.execute("UPDATE CommonFiles SET FileName=?, FilePath=? WHERE FileNo=?",
                           (new_name, new_relative, file_no))
            conn.commit()
    finally:
        if conn:
            conn.close()


def update_file_info(old_file_no, new_file_no, category, year, file_name):
    rename_file(old_file_no, file_name)
    from main.db_utils import _get_conn
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE CommonFiles SET FileNo=?, Category=?, Year=? WHERE FileNo=?",
                       (new_file_no, category, year, old_file_no))
        conn.commit()
    finally:
        if conn:
            conn.close()


def update_persons(file_no, category, year, persons):
    from main.db_utils import _get_conn
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT ID FROM CommonFiles WHERE FileNo=? AND IsActive=1", (file_no,))
        row = cursor.fetchone()
        if not row:
            return
        file_id = row[0]

        cursor.execute("UPDATE CommonFiles SET Category=?, Year=?, UpdateTime=GETDATE() WHERE ID=?",
                       (category, year, file_id))

        cursor.execute("SELECT ID, PersonName FROM CommonFilePersons WHERE FileID=? AND IsActive=1", (file_id,))
        rows = cursor.fetchall()
        new_names = {p.get('personName', '').strip() for p in persons if p.get('personName', '').strip()}

        delete_rows = [r for r in rows if r[1] not in new_names]
        if len(delete_rows) == len(rows):
            delete_rows = delete_rows[1:]

        for r in delete_rows:
            cursor.execute("UPDATE CommonFilePersons SET IsActive=0 WHERE ID=?", (r[0],))

        for p in persons:
            name = p.get('personName', '').strip()
            if not name:
                continue
            summary = p.get('summary', '').strip()
            cursor.execute("SELECT ID FROM CommonFilePersons WHERE FileID=? AND PersonName=? AND IsActive=1",
                           (file_id, name))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("UPDATE CommonFilePersons SET Summary=?, UpdateTime=GETDATE() WHERE ID=?",
                               (summary, existing[0]))
            else:
                cursor.execute("INSERT INTO CommonFilePersons (FileID, PersonName, Summary) VALUES (?, ?, ?)",
                               (file_id, name, summary))

        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def insert_file(category, year, file_no, file_name, relative_path, file_size, file_type, md5_hash, upload_by, persons):
    from main.db_utils import _get_conn
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO CommonFiles (Category, Year, FileNo, FileName, FilePath, FileSize, FileType, MD5Hash, UploadBy)
            OUTPUT INSERTED.ID
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (category, year, file_no, file_name, relative_path, file_size, file_type, md5_hash, upload_by))
        file_id = cursor.fetchone()[0]

        for p in persons:
            cursor.execute("INSERT INTO CommonFilePersons (FileID, PersonName, Summary) VALUES (?, ?, ?)",
                           (file_id, p.get('personName', ''), p.get('summary', '')))

        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
