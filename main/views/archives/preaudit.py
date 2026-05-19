from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from main.db_utils import _get_conn
import json
import logging
import os
import openpyxl
from urllib.parse import quote
from main.decorators import archive_perm_required
#@archive_perm_required

logger = logging.getLogger(__name__)


def _get_yhbh(request):
    try: return request.user.profile.yhbh or 0
    except: return 0


@login_required
@archive_perm_required
def person_preaudit_view(request):
    return render(request, 'archives/person_preaudit.html')


@login_required
def preaudit_data_api(request):
    """获取任前联审数据"""
    rsid = request.GET.get('rsid', '')
    if not rsid: return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        yhbh = _get_yhbh(request)
        cursor.execute("{CALL ZXSH_RQLSDJB(?, 'SELECT', ?)}", (int(rsid), yhbh))
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        data = dict(zip(cols, row)) if row else {}
        cursor.close()

        # 处理意见自动填充
        if data.get('rqls28', '') and len(data.get('rqls28', '')) <= 5:
            data['rqls29'] = '此表信息已核实确认无误，不影响任用。'
        else:
            data['rqls29'] = data.get('rqls29', '') or '此表信息已核实确认无误，干部档案存在的问题不影响任用。'

        # 布尔字段
        bool_fields = ['rqls3','rqls4','rqls5','rqls6','rqls7','rqls8','rqls9','rqls10','rqls11','rqls22','rqls23']
        for f in bool_fields:
            data[f] = bool(data.get(f))

        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def preaudit_export_api(request):
    """导出任前联审登记表"""
    rsid = request.GET.get('rsid', '')
    if not rsid: return JsonResponse({"code": 400})

    template_path = os.path.join(settings.BASE_DIR, 'static', 'excel_templates', '任前联审登记表.xlsx')
    if not os.path.exists(template_path):
        return JsonResponse({"code": 500, "msg": "模板不存在"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        yhbh = _get_yhbh(request)
        cursor.execute("{CALL ZXSH_RQLSDJB(?, 'SELECT', ?)}", (int(rsid), yhbh))
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        data = dict(zip(cols, row)) if row else {}
        cursor.close()

        if not data:
            return JsonResponse({"code": 404, "msg": "请先填写专审情况登记表"})

        wb = openpyxl.load_workbook(template_path)
        ws = wb.active
        merged = list(ws.merged_cells.ranges)
        for mr in merged:
            ws.unmerge_cells(str(mr))

        def yn(v, default=1):
            if default == 0 and not v:
                return ''
            return '☑' if v else '☐'

        rdsj = 0 if data.get('rqls14', '') in ('群众', '') else 1

        ws.cell(row=3, column=2).value = data.get('rqls1', '')   # 姓名
        ws.cell(row=3, column=9).value = data.get('rqls2', '')   # 工作单位及职务
        ws.cell(row=6, column=2).value = yn(data.get('rqls3'))   # 出生时间是否一致
        ws.cell(row=7, column=2).value = yn(data.get('rqls4'))
        ws.cell(row=8, column=2).value = yn(data.get('rqls5'), rdsj)
        ws.cell(row=6, column=8).value = yn(data.get('rqls6'))   # 是否涂改
        ws.cell(row=7, column=8).value = yn(data.get('rqls7'))
        ws.cell(row=8, column=8).value = yn(data.get('rqls8'), rdsj)
        ws.cell(row=6, column=11).value = yn(data.get('rqls9'))  # 是否认定
        ws.cell(row=7, column=11).value = yn(data.get('rqls10'))
        ws.cell(row=8, column=11).value = yn(data.get('rqls11'))
        ws.cell(row=6, column=14).value = data.get('rqls12', '') or ''
        ws.cell(row=7, column=14).value = data.get('rqls13', '') or ''
        ws.cell(row=8, column=14).value = data.get('rqls14', '') or ''
        ws.cell(row=9, column=4).value = data.get('rqls15', '') or ''
        ws.cell(row=10, column=4).value = data.get('rqls16', '') or ''
        ws.cell(row=9, column=12).value = data.get('rqls17', '') or ''
        ws.cell(row=10, column=12).value = data.get('rqls18', '') or ''
        ws.cell(row=11, column=2).value = data.get('rqls19', '') or ''
        ws.cell(row=11, column=9).value = data.get('rqls20', '') or ''
        ws.cell(row=11, column=14).value = data.get('rqls21', '') or ''
        ws.cell(row=12, column=4).value = yn(data.get('rqls22'))
        ws.cell(row=12, column=12).value = yn(data.get('rqls23'))
        ws.cell(row=13, column=4).value = data.get('rqls24', '') or ''
        ws.cell(row=13, column=12).value = data.get('rqls25', '') or ''
        ws.cell(row=14, column=4).value = data.get('rqls26', '') or ''
        ws.cell(row=15, column=4).value = data.get('rqls27', '') or ''
        ws.cell(row=17, column=3).value = data.get('rqls28', '') or ''
        ws.cell(row=17, column=13).value = data.get('rqls29', '') or ''

        for mr in merged:
            ws.merge_cells(str(mr))

        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        fn = f"{data.get('rqls1', '')}_{rsid}_任前联审.xlsx"
        filepath = os.path.join(export_dir, fn)
        wb.save(filepath)

        return JsonResponse({"code": 0, "url": f"/media/exports/{fn}"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()
