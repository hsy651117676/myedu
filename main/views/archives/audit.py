from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.cache import cache
import json
import logging
import os
from io import BytesIO
import xlrd
from xlutils.copy import copy
import openpyxl
from urllib.parse import quote
from main.db_utils import _get_conn
from django.http import HttpResponse
from main.decorators import archive_perm_required
#@archive_perm_required

logger = logging.getLogger(__name__)


def _get_yhbh(request):
    try:
        return request.user.profile.yhbh or 0
    except:
        return 0


@login_required
@archive_perm_required
def person_audit_view(request):
    return render(request, 'archives/person_audit.html')


@login_required
@archive_perm_required
def audit_data_api(request):
    rsid = request.GET.get('rsid', '')
    if not rsid:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        yhbh = _get_yhbh(request)
        cursor.execute("{CALL ZXSH_DAZSQKDJB(?, 'SELECT', ?)}", (int(rsid), yhbh))
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        data = dict(zip(cols, row)) if row else {}
        cursor.close()
        return JsonResponse({"code": 0, "data": data})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@csrf_exempt
def audit_save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    rsid = data.get("rsid")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少RSID"})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        yhbh = _get_yhbh(request)

        # 先查现有数据
        cursor.execute("{CALL ZXSH_DAZSQKDJB(?, 'SELECT', ?)}", (int(rsid), yhbh))
        cols = [col[0] for col in cursor.description]
        old_row = cursor.fetchone()
        old_data = dict(zip(cols, old_row)) if old_row else {}

        # 合并
        merged = {**old_data, **data}
        merged["RSID"] = int(rsid)
        merged["userid"] = yhbh

        cursor.execute("""
            EXEC ZXSH_DAZSQKDJB ?, 'UPDATE', ?,
            @cssj1A=?,@cssj2A=?,@cssj3A=?,@cssj4A=?,@cssj5A=?,@cssj6A=?,@cssj7A=?,@cssj8A=?,
            @cjgz1A=?,@cjgz2A=?,@cjgz3A=?,@cjgz4A=?,@cjgz5A=?,@cjgz6A=?,@cjgz7A=?,
            @rdsj1A=?,@rdsj2A=?,@rdsj3A=?,@rdsj4A=?,@rdsj5A=?,@rdsj6A=?,@rdsj7A=?,@rdsj8A=?,@rdsj9A=?,@rdsj10A=?,
            @xlxw1A=?,@xlxw2A=?,@xlxw3A=?,@xlxw4A=?,@xlxw5A=?,@xlxw6A=?,@xlxw7A=?,@xlxw8A=?,@xlxw9A=?,@xlxw10A=?,
            @xlxw11A=?,@xlxw12A=?,@xlxw13A=?,
            @gzjl1A=?,@gzjl2A=?,@gzjl3A=?,@gzjl4A=?,@gzjl5A=?,@gzjl6A=?,@gzjl7A=?,
            @gbsf1A=?,@gbsf2A=?,@gbsf3A=?,@gbsf4A=?,@zyjs1A=?,@zyjs2A=?,@zyjs3A=?,@zyjs4A=?,
            @jcqk1A=?,@jcqk2A=?,@mc1A=?,@mc2A=?,@mc3A=?,@shgx1A=?,@shgx2A=?,@qtwt=?,@shyj=?,
            @shr1=?,@shr2=?,@shrtime=?
        """, (
            merged["RSID"], yhbh,
            merged.get("cssj1A",0),merged.get("cssj2A",""),merged.get("cssj3A",""),merged.get("cssj4A",0),merged.get("cssj5A",0),merged.get("cssj6A",0),merged.get("cssj7A",0),merged.get("cssj8A",0),
            merged.get("cjgz1A",0),merged.get("cjgz2A",0),merged.get("cjgz3A",""),merged.get("cjgz4A",""),merged.get("cjgz5A",0),merged.get("cjgz6A",0),merged.get("cjgz7A",0),
            merged.get("rdsj1A",0),merged.get("rdsj2A",0),merged.get("rdsj3A",0),merged.get("rdsj4A",0),merged.get("rdsj5A",0),merged.get("rdsj6A",""),merged.get("rdsj7A",""),merged.get("rdsj8A",0),merged.get("rdsj9A",0),merged.get("rdsj10A",0),
            merged.get("xlxw1A",0),merged.get("xlxw2A",0),merged.get("xlxw3A",""),merged.get("xlxw4A",""),merged.get("xlxw5A",""),merged.get("xlxw6A",""),merged.get("xlxw7A",0),merged.get("xlxw8A",0),merged.get("xlxw9A",0),merged.get("xlxw10A",0),
            merged.get("xlxw11A",0),merged.get("xlxw12A",0),merged.get("xlxw13A",0),
            merged.get("gzjl1A",0),merged.get("gzjl2A",0),merged.get("gzjl3A",0),merged.get("gzjl4A",0),merged.get("gzjl5A",0),merged.get("gzjl6A",0),merged.get("gzjl7A",0),
            merged.get("gbsf1A",0),merged.get("gbsf2A",0),merged.get("gbsf3A",0),merged.get("gbsf4A",0),merged.get("zyjs1A",""),merged.get("zyjs2A",0),merged.get("zyjs3A",0),merged.get("zyjs4A",0),
            merged.get("jcqk1A",0),merged.get("jcqk2A",0),merged.get("mc1A",""),merged.get("mc2A",0),merged.get("mc3A",0),merged.get("shgx1A",0),merged.get("shgx2A",0),merged.get("qtwt",""),merged.get("shyj",""),
            merged.get("shr1",""),merged.get("shr2",""),merged.get("shrtime","")
        ))

        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        logger.error(f"专审保存失败: {e}")
        if conn:
            try: conn.rollback()
            except: pass
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            try: conn.close()
            except: pass


@login_required
def audit_proof_check_api(request):
    rsid = request.GET.get('rsid', '')
    if not rsid:
        return JsonResponse({"code": 400})

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        yhbh = _get_yhbh(request)
        cursor.execute("{CALL ZXSH_RQLSDJB(?, 'SELECTZXSHZM', ?)}", (int(rsid), yhbh))

        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        result = dict(zip(cols, row)) if row else {}

        details = []
        if cursor.nextset():
            dcols = [col[0] for col in cursor.description]
            for row in cursor.fetchall():
                details.append(dict(zip(dcols, row)))

        cursor.close()
        return JsonResponse({"code": 0, "result": result, "details": details})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()

def _generate_proof_pdf(rsid, proof_type, yhbh):
    import qrcode
    from PIL import Image
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from datetime import datetime
    import tempfile, os

    font_path = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
    if not os.path.exists(font_path):
        font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    pdfmetrics.registerFont(TTFont('Chinese', font_path))

    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("{CALL ZXSH_RQLSDJB(?, ?, ?)}", (int(rsid), proof_type, yhbh))
    cols = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    data = dict(zip(cols, row)) if row else {}
    cursor.close()
    conn.close()

    photo_path = None
    if data.get('DQZP'):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        tmp.write(data['DQZP'])
        tmp.close()
        photo_path = tmp.name

    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(data.get('qrcode', ''))
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='black', back_color='white').convert('RGB')

    if photo_path:
        logo = Image.open(photo_path).resize((80, 80))
        pos = ((qr_img.size[0] - logo.size[0]) // 2, (qr_img.size[1] - logo.size[1]) // 2)
        qr_img.paste(logo, pos)

    qr_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    qr_img.save(qr_tmp.name)
    qr_tmp.close()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # 标题
    c.setFont('Chinese', 22)
    c.drawCentredString(width/2, height-120, "干部人事档案专项审核证明")

    # 正文（首行缩进2字符）
    style = ParagraphStyle(
        'ChineseStyle',
        fontName='Chinese',
        fontSize=16,
        leading=24,
        firstLineIndent=24,  # 首行缩进2字符
        alignment=4,  # 两端对齐
    )
    text = data.get('paragraph', '').replace('\n', '<br/>')
    p = Paragraph(text, style)
    p.wrapOn(c, width-160, height-160)
    p.drawOn(c, 80, height-380)

    # 落款（右对齐）
    c.setFont('Chinese', 16)
    today = datetime.now().strftime('%Y年%m月%d日')
    c.drawRightString(width-120, 200, "盘州市教育局档案室")
    c.drawRightString(width-120, 175, today)

    # 二维码在左下角
    c.drawImage(qr_tmp.name, 80, 230, width=140, height=140)

    c.showPage()
    c.save()
    buf.seek(0)

    if photo_path:
        os.unlink(photo_path)
    os.unlink(qr_tmp.name)

    return buf

@login_required
def audit_proof_print_api(request):
    rsid = request.GET.get('rsid', '')
    if not rsid:
        return JsonResponse({"code": 400})

    try:
        yhbh = _get_yhbh(request)
        
        # 先检查是否专审通过
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("{CALL ZXSH_RQLSDJB(?, 'SELECTZXSHZM', ?)}", (int(rsid), yhbh))
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        check_data = dict(zip(cols, row)) if row else {}
        cursor.close()
        conn.close()
        
        if check_data.get('ZSZM') != 'yes':
            return JsonResponse({"code": 400, "msg": "该同志档案未专审通过，不能出具证明"})
        
        buf = _generate_proof_pdf(rsid, 'SELECTZXSHZM', yhbh)
        resp = HttpResponse(buf.read(), content_type='application/pdf')
        resp['Content-Disposition'] = 'inline; filename="proof.pdf"'
        return resp
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})


@login_required
def audit_proof_print_admin_api(request):
    rsid = request.GET.get('r', '')
    pwd = request.GET.get('k', '')

    if pwd != '5200':
        return JsonResponse({"code": 403})

    if not rsid:
        return JsonResponse({"code": 400})

    try:
        yhbh = _get_yhbh(request)
        buf = _generate_proof_pdf(rsid, 'SELECTZXSHZM_Admin', yhbh)
        resp = HttpResponse(buf.read(), content_type='application/pdf')
        resp['Content-Disposition'] = 'inline; filename="proof.pdf"'
        return resp
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
