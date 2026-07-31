"""9-1-1_干部工资变动情况表"""

import json
import logging
import os
from contextlib import contextmanager
from io import BytesIO
from urllib.parse import quote

import openpyxl
import pyodbc
import xlrd
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse, FileResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from openpyxl.styles import Alignment, Border, Font, Side
from weasyprint import HTML
from xlutils.copy import copy

from main.utils import _get_conn, execute_sql
from main.utils.decorators import archive_perm_required

logger = logging.getLogger(__name__)


def fmt6(s):
    if s and len(s) >= 6:
        return s[:4] + "." + s[4:6]
    return s or ""


@contextmanager
def db():
    """数据库上下文管理器，自动 commit/rollback + 死锁重试"""
    conn = cursor = None
    last_error = None
    for attempt in range(3):
        try:
            conn = _get_conn()
            cursor = conn.cursor()
            yield cursor
            conn.commit()
            return
        except pyodbc.Error as e:
            error_code = e.args[0] if e.args else ""
            if "1205" in str(error_code) and attempt < 2:
                logger.warning(f"db() 死锁，第{attempt + 1}次重试: {e}")
                import time

                time.sleep(0.5 * (attempt + 1))
                last_error = e
                continue
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        except Exception as e:
            logger.error(f"DB Error: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            if cursor:
                cursor.close()

    if last_error:
        raise last_error


@login_required
@archive_perm_required
def person_salary_view(request):
    return render(request, "archives/person_salary.html")


@login_required
def salary_dcfind_api(request):
    lb = request.GET.get("lb", "")
    if not lb:
        return JsonResponse({"code": 400})

    lbs = [x.strip() for x in lb.split(",") if x.strip()]
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
            val = row[0] if row else ""
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
    if request.method == "POST":
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
                dc = item.get("dc", "")
                sj = item.get("sj", "")
                bz = item.get("bz", "")
                key = f"bz_{dc}_{sj}_{bz}"

                cached = cache.get(key)
                if cached is not None:
                    results[key] = cached
                    continue

                cursor.execute("{CALL Z_gzbzfind(?, ?, ?)}", (dc, sj, bz))
                row = cursor.fetchone()
                val = row[0] if row else 0
                while cursor.nextset():
                    pass
                results[key] = val
                cache.set(key, val, 3600)
            cursor.close()
            return JsonResponse({"code": 0, "data": results})
        except Exception as e:
            return JsonResponse({"code": 500, "msg": str(e)})
        finally:
            if conn:
                conn.close()

    dc = request.GET.get("dc", "")
    sj = request.GET.get("sj", "")
    bz = request.GET.get("bz", "")

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
        while cursor.nextset():
            pass
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
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少RSID"})

    try:
        with db() as c:
            c.execute("{CALL update_gzxx_ZH(?)}", (int(rsid),))
            cols_new = [col[0] for col in c.description]
            rows_new = [dict(zip(cols_new, r)) for r in c.fetchall()]

            c.execute(
                "SELECT SXH AS 序号, WH AS 变动原因, ZXSJ AS 执行时间, ZWGZ AS 职务档次, ZWJE AS 职务金额, JBGZ AS 级别档次, JBJE AS 级别金额, BZ AS 备注 FROM YW_GZBD WHERE RSID = ? AND SXH <> 0 ORDER BY SXH",
                (int(rsid),),
            )
            cols_old = [col[0] for col in c.description]
            rows_old = [dict(zip(cols_old, r)) for r in c.fetchall()]

            c.execute(
                "SELECT WH AS 单位及职务, ZXSJ AS 任职时间, ZWGZ AS 职务档次, ZWJE AS 职务金额, JBGZ AS 级别档次, JBJE AS 级别金额 FROM YW_GZBD WHERE RSID = ? AND SXH = 0",
                (int(rsid),),
            )
            cols_93 = [col[0] for col in c.description]
            rows_93 = [dict(zip(cols_93, r)) for r in c.fetchall()]

        return JsonResponse(
            {
                "code": 0,
                "data": {"newData": rows_new, "oldData": rows_old, "data93": rows_93},
            }
        )
    except Exception as e:
        logger.error(f"工资查询失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})


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
        values.append(
            f"({rsid},{sxh},'{wh}','{zxsj}','{zwgz}','{zwje}','{jbgz}','{jbje}','{bz}')"
        )

    sql = f"""
        MERGE YW_GZBD AS t
        USING (VALUES {",".join(values)}) AS s(RSID, sXH, WH, ZXSJ, ZWGZ, ZWJE, JBGZ, JBJE, BZ)
        ON t.RSID = s.RSID AND t.sXH = s.sXH
        WHEN MATCHED THEN UPDATE SET WH=s.WH, ZXSJ=s.ZXSJ, ZWGZ=s.ZWGZ, ZWJE=s.ZWJE, JBGZ=s.JBGZ, JBJE=s.JBJE, BZ=s.BZ
        WHEN NOT MATCHED THEN INSERT (RSID, sXH, WH, ZXSJ, ZWGZ, ZWJE, JBGZ, JBJE, BZ) VALUES (s.RSID, s.sXH, s.WH, s.ZXSJ, s.ZWGZ, s.ZWJE, s.JBGZ, s.JBJE, s.BZ);
    """

    try:
        execute_sql(sql)
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        logger.error(f"保存失败: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
def salary_delete_api(request):
    rsid = request.GET.get("rsid", "")
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
    rsid = request.GET.get("rsid", "")
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


@login_required
def salary_export_api(request):
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400})

    template_path = os.path.join(
        settings.BASE_DIR, "static", "excel_templates", "9_1_1.xlsx"
    )

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT XM, WORKTIME, JOBUNIT, APPOINTTIME FROM RS_INFO WHERE RSID=?",
            (int(rsid),),
        )
        p = cursor.fetchone()
        cursor.execute(
            "SELECT WH, ZXSJ, ZWGZ, ZWJE, JBGZ, JBJE FROM YW_GZBD WHERE RSID=? AND sXH=0",
            (int(rsid),),
        )
        gz93 = cursor.fetchone()
        cursor.execute(
            "SELECT WH, ZXSJ, ZWGZ, ZWJE, JBGZ, JBJE FROM YW_GZBD WHERE RSID=? AND sXH<>0 ORDER BY sXH",
            (int(rsid),),
        )
        rows = cursor.fetchall()
        cursor.close()

        if not p:
            return JsonResponse({"code": 404})

        wb = openpyxl.load_workbook(template_path)
        ws = wb.active

        merged = list(ws.merged_cells.ranges)
        for mr in merged:
            ws.unmerge_cells(str(mr))

        def safe_set(r, c, v):
            ws.cell(row=r, column=c).value = v

        safe_set(3, 2, p[0] or "")
        safe_set(3, 6, p[1])
        safe_set(4, 2, p[2] or "")
        safe_set(5, 3, p[2] or "")
        safe_set(6, 3, fmt6(p[3]))
        safe_set(6, 7, fmt6(p[3]))

        if gz93:
            safe_set(10, 1, gz93[0] or "")
            safe_set(10, 4, gz93[1] or "")
            safe_set(10, 5, gz93[2] or "")
            safe_set(10, 6, gz93[3] or "")
            safe_set(10, 7, gz93[4] or "")
            safe_set(10, 8, gz93[5] or "")

        for i, rd in enumerate(rows):
            r = 14 + i if i < 18 else 36 + (i - 18)
            if r > 61:
                break
            safe_set(r, 2, rd[0] if rd[0] else "")
            safe_set(r, 4, rd[1] if rd[1] else "")
            safe_set(r, 5, rd[2] if rd[2] else "")
            safe_set(r, 6, rd[3] if rd[3] else "")
            safe_set(r, 7, rd[4] if rd[4] else "")
            safe_set(r, 8, rd[5] if rd[5] else "")

        for mr in merged:
            ws.merge_cells(str(mr))

        fn = f"{p[0]}_9-1-1_干部工资变动情况表.xlsx"

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)

        encoded_fn = quote(fn.encode("utf-8"))
        response = HttpResponse(
            buf,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f"attachment; filename=\"{encoded_fn}\"; filename*=UTF-8''{encoded_fn}"
        )
        return response
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


@login_required
def salary_print_api(request):
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return HttpResponse("缺少 rsid", status=400)

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT XM, WORKTIME, JOBUNIT, APPOINTTIME FROM RS_INFO WHERE RSID=?",
            (int(rsid),),
        )
        p = cursor.fetchone()
        if not p:
            return HttpResponse("人员不存在", status=404)

        cursor.execute(
            "SELECT WH, ZXSJ, ZWGZ, ZWJE, JBGZ, JBJE FROM YW_GZBD WHERE RSID=? AND sXH=0",
            (int(rsid),),
        )
        gz93 = cursor.fetchone()
        cursor.execute(
            "SELECT WH, ZXSJ, ZWGZ, ZWJE, JBGZ, JBJE FROM YW_GZBD WHERE RSID=? AND sXH<>0 ORDER BY sXH",
            (int(rsid),),
        )
        rows = cursor.fetchall()
        cursor.close()

        xm = p[0] or ""
        worktime = fmt6(p[1]) if p[1] else ""
        jobunit = p[2] or ""
        appoint = p[3] or ""

        def row_html(rd):
            return f"<tr style='height:17pt'><td colspan='2' class='reason'>{rd[0] or ''}</td><td>{rd[1] or ''}</td><td>{rd[2] or ''}</td><td>{rd[3] or ''}</td><td>{rd[4] or ''}</td><td>{rd[5] or ''}</td></tr>"

        def empty_row():
            return '<tr style="height:17pt"><td colspan="2" class="reason"></td><td></td><td></td><td></td><td></td><td></td></tr>'

        gz93_h = ""
        if gz93:
            gz93_h = f"<tr style='height:17pt'><td>{jobunit}</td><td>{worktime}</td><td>{gz93[2] or ''}</td><td>{gz93[3] or ''}</td><td>{gz93[4] or ''}</td><td>{gz93[5] or ''}</td></tr>"
        else:
            gz93_h = '<tr style="height:17pt"><td></td><td></td><td></td><td></td><td></td><td></td></tr>'

        p1 = "".join(row_html(r) for r in rows[:18]) + "".join(
            empty_row() for _ in range(18 - len(rows[:18]))
        )
        p2 = "".join(row_html(r) for r in rows[18:]) + "".join(
            empty_row() for _ in range(26 - len(rows[18:]))
        )

    except Exception as e:
        return HttpResponse(str(e), status=500)
    finally:
        if conn:
            conn.close()

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>
@page{{size:A4;margin:21mm 24mm 16mm 24mm;@bottom-center{{content:"共 " counter(pages) " 页  第 " counter(page) " 页";font-size:9pt;font-family:"SimSun",sans-serif;}}}}
body{{font-family:"FangSong","仿宋","仿宋_GB2312","SimSun",sans-serif;font-size:14pt;margin:0;padding:0;}}
.title{{text-align:center;font-size:16pt;font-weight:bold;height:29pt;line-height:29pt;}}
table{{width:100%;border-collapse:collapse;}}
th,td{{border:0.5px solid #000;padding:4pt 6pt;text-align:center;}}
td.noborder{{border:none;}}
.reason{{text-align:left;padding:4pt 8pt;}}
.vertical{{width:60px;font-weight:bold;font-size:14pt;text-align:center;line-height:1.2;border-right:2px solid #000;}}
.double-top td{{border-top:2px solid #000;}}
.double-bottom td{{border-bottom:2px solid #000;}}
.double-left{{border-left:2px solid #000;}}
.double-right{{border-right:2px solid #000;}}
</style></head><body>

<div style="page-break-after:always;">
<div class="title">干部工资变动情况表</div>
<table>
<colgroup>
<col style="width:7%"><col style="width:14%"><col style="width:14%"><col style="width:19%"><col style="width:10%"><col style="width:13%"><col style="width:13%">
</colgroup>
<tr style="height:29pt"><td colspan="7" class="noborder"></td></tr>
<tr style="height:29pt"><td colspan="7" class="noborder"></td></tr>
<tr style="height:28pt"><td class="double-top double-left">姓 名</td><td colspan="2" class="double-top"></td><td colspan="2" class="double-top">参加工作时间</td><td colspan="2" class="double-top double-right"></td></tr>
<tr style="height:28pt"><td class="double-left">单 位</td><td colspan="6" class="double-right"></td></tr>
<tr style="height:28pt"><td colspan="2" class="double-left">现 任 职 务</td><td colspan="5" class="double-right"></td></tr>
<tr style="height:28pt"><td colspan="2" class="double-left">任现职时间</td><td></td><td colspan="2">任现职级时间</td><td colspan="2" class="double-right"></td></tr>
<tr style="height:28pt"><td colspan="7" class="double-left double-right">1993 年 工 资 改 革 情 况</td></tr>
<tr style="height:28pt"><td rowspan="2" colspan="3" class="double-left">单 位 及 职 务</td><td rowspan="2">任职时间</td><td colspan="2">职务工资</td><td colspan="2">级别工资</td></tr>
<tr style="height:28pt"><td>档 次</td><td>金 额</td><td>档 次</td><td class="double-right">金 额</td></tr>
{gz93_h}
<tr style="height:17pt"><td colspan="7" class="noborder"></td></tr>
<tr style="height:28pt"><td rowspan="20" class="vertical">历<br>年<br>工<br>资<br>变<br>动<br>情<br>况</td><td rowspan="2" colspan="2">变动原因</td><td rowspan="2">执行时间</td><td colspan="2">职务工资</td><td colspan="2">级别工资</td></tr>
<tr style="height:28pt"><td>档 次</td><td>金 额</td><td>档 次</td><td class="double-right">金 额</td></tr>
{p1}
<tr style="height:17pt"><td colspan="2" class="double-bottom"></td><td class="double-bottom"></td><td class="double-bottom"></td><td class="double-bottom"></td><td class="double-bottom"></td><td class="double-bottom double-right"></td></tr>
</table>
</div>

<div class="title">干部工资变动情况表(续)</div>
<table>
<colgroup>
<col style="width:7%"><col style="width:14%"><col style="width:14%"><col style="width:19%"><col style="width:10%"><col style="width:13%"><col style="width:13%">
</colgroup>
<tr style="height:28pt"><td rowspan="28" class="vertical">历<br>年<br>工<br>资<br>变<br>动<br>情<br>况</td><td rowspan="2" colspan="2">变动原因</td><td rowspan="2">执行时间</td><td colspan="2">职务工资</td><td colspan="2">级别工资</td></tr>
<tr style="height:28pt"><td>档 次</td><td>金 额</td><td>档 次</td><td class="double-right">金 额</td></tr>
{p2}
<tr style="height:17pt"><td colspan="2" class="double-bottom"></td><td class="double-bottom"></td><td class="double-bottom"></td><td class="double-bottom"></td><td class="double-bottom"></td><td class="double-bottom double-right"></td></tr>
</table>
</body></html>"""

    buf = BytesIO()
    HTML(string=html).write_pdf(buf)
    buf.seek(0)
    return HttpResponse(buf, content_type="application/pdf")
