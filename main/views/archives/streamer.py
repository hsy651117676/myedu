"""
档案标签打印（条幅、姓名标签、柜号标签）
"""
import json
import logging
from io import BytesIO
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from main.utils import _get_conn
from main.utils.decorators import archive_perm_required
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

FONT_PATH = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
LINE_SPACING = 1.5
STREAMER_COLS = 5
LABEL_COLS = 3
LABEL_ROWS = 6


@login_required
@archive_perm_required
def page(request):
    return render(request, "archives/streamer.html")


@login_required
@archive_perm_required
def unit_list_api(request):
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT BM, BMMC FROM DEPART WHERE PID > 0 ORDER BY BM")
        rows = [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
def table_api(request):
    unit_id = request.GET.get("unitId", "")
    if not unit_id:
        return JsonResponse({"code": 400})
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 30))
    offset = (page - 1) * page_size

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT COUNT(*)
            FROM USERS_DEPARTMENT
            LEFT JOIN RS_INFO ON USERS_DEPARTMENT.RSID = RS_INFO.RSID
            WHERE USERS_DEPARTMENT.DEPARTMENTID = '{unit_id}'
        """)
        total = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT RS_INFO.RSID, DEPART.BMMC, XM, RYBH, JG, GH, CH,
                   RYBH + ISNULL(JG,'') + ISNULL(GH,'') + ISNULL(CH,'') AS oldValue
            FROM USERS_DEPARTMENT
            LEFT JOIN RS_INFO ON USERS_DEPARTMENT.RSID = RS_INFO.RSID
            LEFT JOIN DEPART ON USERS_DEPARTMENT.DEPARTMENTID = DEPART.BM
            LEFT JOIN YW_INFO ON USERS_DEPARTMENT.RSID = YW_INFO.RSID
            WHERE USERS_DEPARTMENT.DEPARTMENTID = '{unit_id}'
            ORDER BY RYBH
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """)
        rows = [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]
        cursor.close()
        return JsonResponse({"code": 0, "data": rows, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
@archive_perm_required
@csrf_exempt
def save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400})

    rows = data.get("rows", [])
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        for r in rows:
            cursor.execute("UPDATE YW_INFO SET CH=?, GH=? WHERE RSID=?", (
                r.get("CH", ""), r.get("GH", ""), r.get("RSID")))
            cursor.execute("UPDATE RS_INFO SET RYBH=?, JG=? WHERE RSID=?", (
                r.get("RYBH", ""), r.get("JG", ""), r.get("RSID")))
        conn.commit()
        cursor.close()
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


def _load_data(unit_id, rsids):
    conn = _get_conn()
    cursor = conn.cursor()
    if rsids:
        ids = ",".join([x.strip() for x in rsids.split(",") if x.strip()])
        sql = f"""
            SELECT RS_INFO.RSID, DEPART.BMMC, XM, RYBH, JG, GH, CH
            FROM USERS_DEPARTMENT
            LEFT JOIN RS_INFO ON USERS_DEPARTMENT.RSID = RS_INFO.RSID
            LEFT JOIN DEPART ON USERS_DEPARTMENT.DEPARTMENTID = DEPART.BM
            LEFT JOIN YW_INFO ON USERS_DEPARTMENT.RSID = YW_INFO.RSID
            WHERE RS_INFO.RSID IN ({ids}) ORDER BY RYBH
        """
        cursor.execute(sql)
    else:
        cursor.execute("""
            SELECT RS_INFO.RSID, DEPART.BMMC, XM, RYBH, JG, GH, CH
            FROM USERS_DEPARTMENT
            LEFT JOIN RS_INFO ON USERS_DEPARTMENT.RSID = RS_INFO.RSID
            LEFT JOIN DEPART ON USERS_DEPARTMENT.DEPARTMENTID = DEPART.BM
            LEFT JOIN YW_INFO ON USERS_DEPARTMENT.RSID = YW_INFO.RSID
            WHERE USERS_DEPARTMENT.DEPARTMENTID = ? ORDER BY RYBH
        """, (unit_id,))
    rows = [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return rows


def _load_gh_ch(unit_id):
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT GH, CH FROM BMGL WHERE TID=? AND GH IS NOT NULL AND GH<>''", (unit_id,))
    rows = [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return rows


def _load_names_by_ghch(unit_id, gh, ch):
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT CASE LEN(TNAME) WHEN 2 THEN SUBSTRING(TNAME,1,1)+'  '+SUBSTRING(TNAME,2,10) ELSE TNAME END AS TNAME
        FROM BMGL WHERE TID=? AND GH=? AND CH=? ORDER BY DABH
    """, (unit_id, gh, ch))
    rows = [r[0] for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return rows


# ==================== 条幅打印 ====================

@login_required
@archive_perm_required
def print_streamer_api(request):
    unit_id = request.GET.get("unitId", "")
    rsids = request.GET.get("rsids", "")

    rows = _load_data(unit_id, rsids)
    if not rows:
        return HttpResponse("无数据", content_type="text/plain")

    page_w, page_h = A4
    scale = 2
    pw, ph = int(page_w * scale), int(page_h * scale)
    col_w = pw / STREAMER_COLS

    ft = ImageFont.truetype(FONT_PATH, int(18 *  scale))
    fr = ImageFont.truetype(FONT_PATH, int(50 *  scale))
    fv = ImageFont.truetype(FONT_PATH, int(25 *  scale))
    fj = ImageFont.truetype(FONT_PATH, int(35 *  scale))

    ch_w = fr.getbbox('测')[2] - fr.getbbox('测')[0]
    lg= 3
    th =50
    rh = int(50 * lg)
    jh = int(35 * lg)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    pages = (len(rows) + STREAMER_COLS - 1) // STREAMER_COLS

    for pg in range(pages):
        img = Image.new('RGB', (pw, ph), 'white')
        d = ImageDraw.Draw(img)

        for i in range(STREAMER_COLS):
            idx = pg * STREAMER_COLS + i
            if idx >= len(rows):
                break
            r = rows[idx]
            x0 = i * col_w
            xc = x0 + col_w / 2
            xl = xc - ch_w / 2

            if i < STREAMER_COLS - 1:
                d.line([(x0 + col_w, 0), (x0 + col_w, ph)], fill='black', width=2)

            bmmc = r.get('BMMC', '')
            for ln, line in enumerate([bmmc[i:i+4] for i in range(0, len(bmmc), 4)]):
                w = ft.getbbox(line)[2] - ft.getbbox(line)[0]
                d.text((xc - w/2, 40 + ln * th), line, fill='black', font=ft)

            d.text((xl, 130), '编', fill='red', font=fr)
            d.text((xl, 250), '号', fill='red', font=fr)
            rybh = str(r.get('RYBH', ''))
            w = fv.getbbox(rybh)[2] - fv.getbbox(rybh)[0]
            d.text((xc - w/2, 400), rybh, fill='black', font=fv)

            d.text((xl, 490), '姓', fill='red', font=fr)
            d.text((xl, 610), '名', fill='red', font=fr)
            xm = r.get('XM', '')
            if len(xm) == 2:
                xm = xm[0] + ' ' + xm[1]
            for ci, ch in enumerate(xm):
                w = fr.getbbox(ch)[2] - fr.getbbox(ch)[0]
                d.text((xc - w/2, 760 + ci * rh), ch, fill='black', font=fr)

            d.text((xl, 1200), '籍', fill='red', font=fr)
            d.text((xl, 1340), '贯', fill='red', font=fr)
            for ln, line in enumerate([str(r.get('JG',''))[i:i+2] for i in range(0, len(str(r.get('JG',''))), 2)]):
                w = fj.getbbox(line)[2] - fj.getbbox(line)[0]
                d.text((xc - w/2, 1450 + ln * jh), line, fill='black', font=fj)

        buf_img = BytesIO()
        img.save(buf_img, format='PNG')
        buf_img.seek(0)
        c.drawImage(ImageReader(buf_img), 0, 0, width=page_w, height=page_h)
        c.showPage()

    c.save()
    buf.seek(0)
    return HttpResponse(buf, content_type='application/pdf')


# ==================== 姓名标签打印 ====================

@login_required
@archive_perm_required
def print_label_api(request):
    unit_id = request.GET.get("unitId", "")
    rsids = request.GET.get("rsids", "")
    per_page = LABEL_COLS * LABEL_ROWS

    rows = _load_data(unit_id, rsids)
    if not rows:
        return HttpResponse("无数据", content_type="text/plain")

    page_w, page_h = A4
    cell_w = page_w / LABEL_COLS
    cell_h = page_h / LABEL_ROWS

    font1 = ImageFont.truetype(FONT_PATH, 20)
    font2 = ImageFont.truetype(FONT_PATH, 30)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    pages = (len(rows) + per_page - 1) // per_page

    for pg in range(pages):
        img = Image.new('RGB', (int(page_w), int(page_h)), 'white')
        d = ImageDraw.Draw(img)

        for i in range(per_page):
            idx = pg * per_page + i
            if idx >= len(rows):
                break
            r = rows[idx]
            x = (i % LABEL_COLS) * cell_w + 15
            y = (i // LABEL_COLS) * cell_h

            d.text((x, y), f"柜号:    层号:", fill='red', font=font1)
            d.text((x + 45, y), f"{r.get('GH','')}        {r.get('CH','')}", fill='black', font=font1)
            xm = r.get('XM', '')
            if len(xm) == 2:
                xm = xm[0] + '  ' + xm[1]
            d.text((x, y + cell_h/3), "姓名:", fill='red', font=font2)
            d.text((x + 70, y + cell_h/4), f"{xm}", fill='black', font=font2)

        buf_img = BytesIO()
        img.save(buf_img, format='PNG')
        buf_img.seek(0)
        c.drawImage(ImageReader(buf_img), 0, 0, width=page_w, height=page_h)
        c.showPage()

    c.save()
    buf.seek(0)
    return HttpResponse(buf, content_type='application/pdf')


# ==================== 柜号标签打印 ====================

CABINET_SETTINGS = {
    3: dict(size=40, spacing_h=75, spacing_w=100),
    4: dict(size=35, spacing_h=70, spacing_w=90),
    5: dict(size=28, spacing_h=65, spacing_w=80),
    6: dict(size=24, spacing_h=50, spacing_w=60),
    7: dict(size=22, spacing_h=45, spacing_w=50),
    8: dict(size=20, spacing_h=45, spacing_w=50),
}

@login_required
@archive_perm_required
def print_cabinet_api(request):
    unit_id = request.GET.get("unitId", "")
    direction = request.GET.get("direction", "h")
    page_qty = int(request.GET.get("pageQty", 5))

    gh_ch_rows = _load_gh_ch(unit_id)
    if not gh_ch_rows:
        return HttpResponse("无数据", content_type="text/plain")

    cfg = CABINET_SETTINGS.get(page_qty, CABINET_SETTINGS[5])
    size_font = cfg['size']
    spacing_h = cfg['spacing_h']
    spacing_w = cfg['spacing_w']

    font = ImageFont.truetype(FONT_PATH, size_font)
    font_small = ImageFont.truetype(FONT_PATH, size_font - 3)

    page_w, page_h = A4
    scale = 2
    pw, ph = int(page_w * scale), int(page_h * scale)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    pages = (len(gh_ch_rows) + page_qty - 1) // page_qty

    for pg in range(pages):
        if direction == 'v':
            # 竖排：画在 ph×pw 的画布上，旋转后贴回
            img_rot = Image.new('RGB', (ph, pw), 'white')
            d = ImageDraw.Draw(img_rot)
            col_w = ph / page_qty
        else:
            img = Image.new('RGB', (pw, ph), 'white')
            d = ImageDraw.Draw(img)
            row_h = ph / page_qty

        for i in range(page_qty):
            idx = pg * page_qty + i
            if idx >= len(gh_ch_rows):
                break
            r = gh_ch_rows[idx]
            gh, ch = r['GH'], r['CH']
            names = _load_names_by_ghch(unit_id, gh, ch)

            if direction == 'v':
                x0 = i * col_w
                d.text((x0 + 20, 30), f"柜号{gh}\n层号{ch}", fill='red', font=font_small)
                d.line([(x0 + spacing_w + 30, 0), (x0 + spacing_w + 30, pw)], fill='black', width=1)
                name_h = (pw - spacing_h * 3) / max(len(names), 1)
                for ni, name in enumerate(names):
                    color = 'blue' if ni % 5 == 0 else 'black'
                    d.text((x0 + spacing_w + 40, spacing_h * 2 + ni * name_h), name, fill=color, font=font)
            else:
                y0 = i * row_h
                d.text((15, y0 + 5), f"柜号{gh}  层号{ch}", fill='red', font=font_small)
                d.line([(0, y0 + spacing_h * 2), (pw, y0 + spacing_h * 2)], fill='black', width=1)
                name_w = (pw - spacing_w) / max(len(names), 1)
                for ni, name in enumerate(names):
                    color = 'blue' if ni % 5 == 0 else 'black'
                    d.text((spacing_w + ni * name_w, y0 + spacing_h * 2 + 5), name, fill=color, font=font)

        if direction == 'v':
            img = img_rot.rotate(90, expand=True)
            # 缩放到 A4
            img = img.resize((pw, ph))

        buf_img = BytesIO()
        img.save(buf_img, format='PNG')
        buf_img.seek(0)
        c.drawImage(ImageReader(buf_img), 0, 0, width=page_w, height=page_h)
        c.showPage()

    c.save()
    buf.seek(0)
    return HttpResponse(buf, content_type='application/pdf')
