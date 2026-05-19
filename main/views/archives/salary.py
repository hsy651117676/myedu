from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
import logging
import pyodbc
from django.core.cache import cache
from contextlib import contextmanager
import os
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side
from urllib.parse import quote
import xlrd
from xlutils.copy import copy
from main.db_utils import _get_conn
from main.decorators import archive_perm_required
#@archive_perm_required

def fmt6(s):
    if s and len(s) >= 6:
        return s[:4] + '.' + s[4:6]
    return s or ''

@contextmanager
def db():
    conn = cursor = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        logger.error(f"DB Error: {e}")
        if conn:
            try: conn.rollback()
            except: pass
        raise
    finally:
        if cursor: cursor.close()


@login_required
@archive_perm_required
def person_salary_view(request):
    return render(request, 'archives/person_salary.html')

@login_required
def salary_dcfind_api(request):
    lb = request.GET.get('lb', '')
    if not lb:
        return JsonResponse({"code": 400})

    lbs = [x.strip() for x in lb.split(',') if x.strip()]
    result = {}

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        for one_lb in lbs:
            cache_key = f"salary_dcfind_{one_lb}"
            cached = cache.get(cache_key)
            if cached:
                result[one_lb] = cached
                continue
            cursor.execute("SELECT dc FROM Z_GZBZ WHERE lb=?", (one_lb,))
            row = cursor.fetchone()
            val = row[0] if row else ''
            result[one_lb] = val
            cache.set(cache_key, val, 3600)
        cursor.close()
        return JsonResponse({"code": 0, "data": result})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()

@login_required
@csrf_exempt
def salary_bzfind_api(request):
    if request.method == 'POST':
        try:
            items = json.loads(request.body) if request.body else []
        except:
            items = []

        results = {}
        conn = None
        try:
            conn = _get_conn()
            cursor = conn.cursor()
            for item in items:
                dc = item.get('dc', '')
                sj = item.get('sj', '')
                bz = item.get('bz', '')
                key = f"bz_{dc}_{sj}_{bz}"

                cached = cache.get(key)
                if cached is not None:
                    results[key] = cached
                    continue

                cursor.execute("{CALL Z_gzbzfind(?, ?, ?)}", (dc, sj, bz))
                row = cursor.fetchone()
                val = row[0] if row else 0
                while cursor.nextset(): pass
                results[key] = val
                cache.set(key, val, 3600)
            cursor.close()
            return JsonResponse({"code": 0, "data": results})
        except Exception as e:
            return JsonResponse({"code": 500, "msg": str(e)})
        finally:
            if conn:
                conn.close()

    dc = request.GET.get('dc', '')
    sj = request.GET.get('sj', '')
    bz = request.GET.get('bz', '')

    cache_key = f"bz_{dc}_{sj}_{bz}"
    result = cache.get(cache_key)
    if result is not None:
        return JsonResponse({"code": 0, "data": result})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("{CALL Z_gzbzfind(?, ?, ?)}", (dc, sj, bz))
        row = cursor.fetchone()
        while cursor.nextset(): pass
        result = row[0] if row else 0
        cursor.close()
        cache.set(cache_key, result, 3600)
        return JsonResponse({"code": 0, "data": result})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()

@login_required
def salary_data_api(request):
    rsid = request.GET.get('rsid', '')
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少RSID"})

    try:
        with db() as c:
            c.execute("{CALL update_gzxx_ZH(?)}", (int(rsid),))
            cols_new = [col[0] for col in c.description]
            rows_new = [dict(zip(cols_new, r)) for r in c.fetchall()]

            c.execute("SELECT SXH AS 序号, WH AS 变动原因, ZXSJ AS 执行时间, ZWGZ AS 职务档次, ZWJE AS 职务金额, JBGZ AS 级别档次, JBJE AS 级别金额, BZ AS 备注 FROM YW_GZBD WHERE RSID = ? AND SXH <> 0 ORDER BY SXH", (int(rsid),))
            cols_old = [col[0] for col in c.description]
            rows_old = [dict(zip(cols_old, r)) for r in c.fetchall()]

            c.execute("SELECT WH AS 单位及职务, ZXSJ AS 任职时间, ZWGZ AS 职务档次, ZWJE AS 职务金额, JBGZ AS 级别档次, JBJE AS 级别金额 FROM YW_GZBD WHERE RSID = ? AND SXH = 0", (int(rsid),))
            cols_93 = [col[0] for col in c.description]
            rows_93 = [dict(zip(cols_93, r)) for r in c.fetchall()]

        return JsonResponse({
            "code": 0,
            "data": {"newData": rows_new, "oldData": rows_old, "data93": rows_93}
        })
    except Exception as e:
        logger.error(f"工资查询失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
@csrf_exempt
@login_required
@csrf_exempt
def salary_save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    rsid = data.get("rsid")
    rows = data.get("rows", [])

    if not rows:
        return JsonResponse({"code": 400, "msg": "无数据"})

    values = []
    for row in rows:
        sxh = row.get("序号", 0)
        wh = (row.get("变动原因") or "").replace("'", "''")
        zxsj = row.get("执行时间") or ""
        zwgz = row.get("职务档次") or ""
        zwje = row.get("职务金额") or ""
        jbgz = row.get("级别档次") or ""
        jbje = row.get("级别金额") or ""
        bz = (row.get("备注") or "").replace("'", "''")
        values.append(f"({rsid},{sxh},'{wh}','{zxsj}','{zwgz}','{zwje}','{jbgz}','{jbje}','{bz}')")

    sql = f"""
        MERGE YW_GZBD AS t
        USING (VALUES {','.join(values)}) AS s(RSID, sXH, WH, ZXSJ, ZWGZ, ZWJE, JBGZ, JBJE, BZ)
        ON t.RSID = s.RSID AND t.sXH = s.sXH
        WHEN MATCHED THEN UPDATE SET WH=s.WH, ZXSJ=s.ZXSJ, ZWGZ=s.ZWGZ, ZWJE=s.ZWJE, JBGZ=s.JBGZ, JBJE=s.JBJE, BZ=s.BZ
        WHEN NOT MATCHED THEN INSERT (RSID, sXH, WH, ZXSJ, ZWGZ, ZWJE, JBGZ, JBJE, BZ) VALUES (s.RSID, s.sXH, s.WH, s.ZXSJ, s.ZWGZ, s.ZWJE, s.JBGZ, s.JBJE, s.BZ);
    """

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        logger.error(f"保存失败: {e}")
        if conn:
            try: conn.rollback()
            except: pass
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            try: conn.close()
            except: pass

@login_required
def salary_delete_api(request):
    rsid = request.GET.get('rsid', '')
    if not rsid:
        return JsonResponse({"code": 400})
    try:
        with db() as c:
            c.execute("{CALL delete_gzxx(?)}", (int(rsid),))
        return JsonResponse({"code": 0, "msg": "删除成功"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})

@login_required
def salary_auto_api(request):
    rsid = request.GET.get('rsid', '')
    if not rsid:
        return JsonResponse({"code": 400})
    try:
        with db() as c:
            c.execute("{CALL update_gzxx_ZH(?)}", (int(rsid),))
            cols = [col[0] for col in c.description]
            rows = [dict(zip(cols, r)) for r in c.fetchall()]
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})

import openpyxl
import copy

@login_required
def salary_export_api(request):
    rsid = request.GET.get('rsid', '')
    if not rsid:
        return JsonResponse({"code": 400})

    template_path = os.path.join(settings.BASE_DIR, 'static', 'excel_templates', '9_1_1.xlsx')

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT XM, WORKTIME, JOBUNIT, APPOINTTIME FROM RS_INFO WHERE RSID=?", (int(rsid),))
        p = cursor.fetchone()
        cursor.execute("SELECT WH, ZXSJ, ZWGZ, ZWJE, JBGZ, JBJE FROM YW_GZBD WHERE RSID=? AND sXH=0", (int(rsid),))
        gz93 = cursor.fetchone()
        cursor.execute("SELECT WH, ZXSJ, ZWGZ, ZWJE, JBGZ, JBJE FROM YW_GZBD WHERE RSID=? AND sXH<>0 ORDER BY sXH", (int(rsid),))
        rows = cursor.fetchall()
        cursor.close()

        if not p:
            return JsonResponse({"code": 404})

        wb = openpyxl.load_workbook(template_path)
        ws = wb.active

        # 记录所有合并区域
        merged = list(ws.merged_cells.ranges)

        # 取消所有合并
        for mr in merged:
            ws.unmerge_cells(str(mr))

        # 安全写入
        def safe_set(r, c, v):
            ws.cell(row=r, column=c).value = v

        safe_set(3, 2, p[0] or '')
        safe_set(3, 6, fmt6(p[1]))
        safe_set(4, 2, p[2] or '')
        safe_set(5, 3, p[3] or '')
        safe_set(6, 3, fmt6(p[3]))
        safe_set(6, 7, fmt6(p[3]))

        if gz93:
            safe_set(10, 1, gz93[0] or '')
            safe_set(10, 4, gz93[1] or '')
            safe_set(10, 5, gz93[2] or '')
            safe_set(10, 6, gz93[3] or '')
            safe_set(10, 7, gz93[4] or '')
            safe_set(10, 8, gz93[5] or '')

        for i, rd in enumerate(rows):
            r = 14 + i if i < 18 else 36 + (i - 18)
            if r > 61: break
            safe_set(r, 2, rd[0] if rd[0] else '')
            safe_set(r, 4, rd[1] if rd[1] else '')
            safe_set(r, 5, rd[2] if rd[2] else '')
            safe_set(r, 6, rd[3] if rd[3] else '')
            safe_set(r, 7, rd[4] if rd[4] else '')
            safe_set(r, 8, rd[5] if rd[5] else '')

        # 恢复合并
        for mr in merged:
            ws.merge_cells(str(mr))

        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        fn = f"{p[0]}_{rsid}.xlsx"
        filepath = os.path.join(export_dir, fn)
        wb.save(filepath)

        return JsonResponse({"code": 0, "url": f"/media/exports/{fn}"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            try: conn.close()
            except: pass
