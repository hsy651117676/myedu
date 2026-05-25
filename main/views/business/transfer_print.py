"""
档案转递打印
"""
import os
import logging
from io import BytesIO
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.conf import settings
from main.db_utils import _get_conn
from main.decorators import archive_perm_required
import openpyxl
from weasyprint import HTML
from urllib.parse import quote

logger = logging.getLogger(__name__)

TEMPLATE_PATH = os.path.join(settings.BASE_DIR, "static", "excel_templates", "干部档案传递单.xlsx")


def _get_print_data(rid):
    """获取打印数据"""
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM YW_DAZD WHERE ID=?", (int(rid),))
        cols = [c[0] for c in cursor.description]
        row = cursor.fetchone()
        if not row:
            return None, None, None, None, None
        record = dict(zip(cols, row))

        # 被转递人信息
        person_rsid = str(record.get("RSID", ""))
        person_info = {}
        if person_rsid:
            cursor.execute("""
                SELECT XM AS 姓名, XB AS 性别, CSNY AS 出生年月,
                       MZ AS 民族, RYBH AS 档案编号,
                       JOBUNIT AS 单位及职务, IDCARD AS 身份证号
                FROM RS_INFO WHERE RSID=?
            """, (int(person_rsid),))
            pcols = [c[0] for c in cursor.description]
            prow = cursor.fetchone()
            if prow:
                person_info = dict(zip(pcols, prow))
        cursor.close()

        zdsj = record.get("ZDSJ", "") or ""
        zdsj_year = zdsj[:4] if len(zdsj) >= 4 else ""
        wjh = record.get("WJH", "") or ""
        zdwh = f"盘教档传递【{zdsj_year}】{wjh}号"
        zdsj_display = f"{zdsj[:4]}年{zdsj[4:6]}月{zdsj[6:8]}日" if len(zdsj) == 8 else zdsj
        zwdw = record.get("ZWDW", "") or ""
        fb = record.get("FB", "") or ""
        person_job = person_info.get("单位及职务", "")

        return record, person_info, zdwh, zdsj_display, zwdw, fb, person_job
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
def print_page(request):
    """打印预览页面"""
    rid = request.GET.get("id", "")
    if not rid:
        return HttpResponse("缺少ID", status=400)

    result = _get_print_data(rid)
    if result[0] is None:
        return HttpResponse("记录不存在", status=404)
    record, person_info, zdwh, zdsj_display, zwdw, fb, person_job = result

    return render(request, "business/archive_transfer_print.html", {
        "record": record,
        "person_info": person_info,
        "zdwh": zdwh,
        "zdsj_display": zdsj_display,
        "zwdw": zwdw,
        "fb": fb,
        "person_job": person_job,
        "rid": rid,
        "zdyy": record.get("ZDYY", "") or "",
    })


@login_required
@archive_perm_required
def export_excel(request):
    """导出Excel"""
    rid = request.GET.get("id", "")
    if not rid:
        return HttpResponse("缺少ID", status=400)

    result = _get_print_data(rid)
    if result[0] is None:
        return HttpResponse("记录不存在", status=404)
    record, person_info, zdwh, zdsj_display, zwdw, fb, person_job = result

    wb = openpyxl.load_workbook(TEMPLATE_PATH)
    sheet = wb["档案转递单"]

    # C2 和 C7 填文件号
    sheet.cell(row=2, column=3).value = zdwh
    sheet.cell(row=7, column=3).value = zdwh

    # Row 3: 姓名 | 工作单位 | 调往何单位
    sheet.cell(row=4, column=1).value = f"{fb}"
    sheet.cell(row=4, column=2).value = f"{person_job}"
    sheet.cell(row=4, column=3).value = f"{zwdw}"

    # Row 8: 转往单位
    sheet.cell(row=8, column=1).value = f"{zwdw}："

    # Row 9: 等同志的档案材料转出
    sheet.cell(row=9, column=1).value = f"  {fb}等同志的档案材料转出，请按档案内所列目录清点查收，并将回执退回。"

    # Row 11 Col 3: 转递日期
    sheet.cell(row=11, column=3).value = zdsj_display

    # Row 12: 姓名 | 工作单位 | 调往何单位
    sheet.cell(row=13, column=1).value = f"{fb}"
    sheet.cell(row=13, column=2).value = f"{person_job}"
    sheet.cell(row=13, column=3).value = f"{zwdw}"

    # 回执空着不填

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"{zdwh}_{fb}.xlsx"
    resp = HttpResponse(buf, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return resp


@login_required
@archive_perm_required
def export_pdf(request):
    """导出PDF"""
    rid = request.GET.get("id", "")
    if not rid:
        return HttpResponse("缺少ID", status=400)

    result = _get_print_data(rid)
    if result[0] is None:
        return HttpResponse("记录不存在", status=404)
    record, person_info, zdwh, zdsj_display, zwdw, fb, person_job = result

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
@page{{size:A4 portrait;margin:15mm 12mm 15mm 12mm;}}
body{{font-family:"SimSun","宋体",sans-serif;font-size:14pt;margin:0;}}
h1{{text-align:center;font-size:20pt;font-weight:bold;margin:0 0 6px 0;}}
h2{{text-align:center;font-size:20pt;font-weight:bold;margin:10px 0 6px 0;}}
.file-no{{text-align:center;font-size:14pt;margin:0 0 6px 0;}}
table{{border-collapse:collapse;width:100%;}}
td{{border:1px solid #000;padding:6px 8px;font-size:14pt;vertical-align:middle;text-align:center;}}
.sep{{text-align:center;font-size:14pt;margin:6px 0;letter-spacing:4px;}}
.content{{border:1px solid #000;padding:8px;margin:6px 0;font-size:14pt;line-height:1.8;text-align:left;}}
.right{{text-align:right;font-size:14pt;margin:4px 0;}}
.return-title{{text-align:center;font-weight:bold;font-size:16pt;margin:8px 0;}}
.footer{{font-size:12pt;margin-top:12px;line-height:1.6;}}
.c1{{width:15%;}}.c2{{width:42%;}}.c3{{width:28%;}}.c4{{width:15%;}}
</style></head><body>

<h1>干部档案传递存根</h1>
<div class="file-no">{zdwh}</div>
<table>
<tr><td class="c1">姓名：{fb}</td><td class="c2">工作单位：{person_job}</td><td class="c3">调往何单位：{zwdw}</td><td class="c4">档案卷数<br>壹卷</td></tr>
</table>
<div class="sep">…………………………………………………………………………………………</div>

<h2>干部档案传递通知单</h2>
<div class="file-no">{zdwh}</div>
<div style="font-size:14pt;">{zwdw}：</div>
<div class="content">
  {fb}等同志的档案材料转出，请按档案内所列目录清点查收，并将回执退回。
</div>
<div class="right">盘州市教育局档案室</div>
<div class="right">{zdsj_display}</div>

<div class="sep">…………………………………………………………………………………………</div>

<table>
<tr><td class="c1">姓名：{fb}</td><td class="c2">工作单位：{person_job}</td><td class="c3">调往何单位：{zwdw}</td><td class="c4">档案卷数<br>壹卷</td></tr>
</table>
<div class="sep">…………………………………………………………………………………………</div>

<div style="font-size:14pt;margin:4px 0;">盘州市教育局：</div>
<div class="return-title">回&emsp;执</div>
<div class="content" style="font-size:12pt;line-height:2;">
&emsp;&emsp;你处&emsp;&emsp;年&emsp;月&emsp;日转来的第&emsp;&emsp;号干部档案转递通知单中所列的&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;等&emsp;&emsp;名同志档案共&emsp;&emsp;卷，我处已于&emsp;&emsp;年&emsp;月&emsp;日收到，经清点无误，现将回执退回，请查收。
</div>
<div style="margin:8px 0;">
  <span>收件人签字：</span>
  <span style="margin-left:40px;">收件单位（盖章）</span>
  <span style="margin-left:60px;">年&emsp;月&emsp;日</span>
</div>
<div class="footer">
  回执邮寄地址：贵州省六盘水市盘州市红果街道盘西新城纵五路教育局大楼517档案室<br>
  联系电话：0858-3634122
</div>
</body></html>"""

    buf = BytesIO()
    HTML(string=html).write_pdf(buf)
    buf.seek(0)
    resp = HttpResponse(buf, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="干部档案传递单_{fb}.pdf"'
    return resp
