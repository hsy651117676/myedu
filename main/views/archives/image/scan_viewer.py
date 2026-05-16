"""
档案扫描查看 - 视图层
"""

import os
import logging
from django.http import JsonResponse, FileResponse, Http404
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
from main.db_utils import _get_conn
from main.views.archives.image.scan_service import (
    get_or_generate_pdf,
    check_scan_exists,
    build_pdf_path,
    get_latest_uptime,
    IMAGE_TYPES,
)

logger = logging.getLogger(__name__)


@login_required
def scan_page(request):
    """档案扫描查看页面入口"""
    rsid = request.GET.get('rsid', '')
    return render(request, 'archives/image/scan_viewer.html', {'rsid': rsid})


@login_required
def get_archive_tree(request):
    """
    获取分类树
    一级: CATETREE WHERE PID=-1，同时返回 sub4 和 sub9
    二级: CATETREE WHERE PID=4 或 9
    三级: RS_ARCHINFO WHERE RSID=? AND FL=?
    """
    pid = request.GET.get('pid', '-1')

    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        if pid == '-1':
            # 一级
            cursor.execute(
                "SELECT FL, JBBH + '、' + FLSM AS name, PID FROM CATETREE WHERE PID=-1 ORDER BY FL"
            )
            tree = [{"fl": r[0], "name": r[1], "pid": r[2]} for r in cursor.fetchall()]

            # 子类 4
            cursor.execute(
                "SELECT FL, JBBH + '、' + FLSM AS name, PID FROM CATETREE WHERE PID=4 ORDER BY FL"
            )
            sub4 = [{"fl": r[0], "name": r[1]} for r in cursor.fetchall()]

            # 子类 9
            cursor.execute(
                "SELECT FL, JBBH + '、' + FLSM AS name, PID FROM CATETREE WHERE PID=9 ORDER BY FL"
            )
            sub9 = [{"fl": r[0], "name": r[1]} for r in cursor.fetchall()]

            cursor.close()
            return JsonResponse({"code": 0, "tree": tree, "sub4": sub4, "sub9": sub9})

        elif pid in ('4', '9'):
            # 二级
            cursor.execute(
                f"SELECT FL, JBBH + '、' + FLSM AS name, PID FROM CATETREE WHERE PID={pid} ORDER BY FL"
            )
            rows = [{"fl": r[0], "name": r[1]} for r in cursor.fetchall()]
            cursor.close()
            return JsonResponse({"code": 0, "data": rows})

        else:
            # 三级：具体档案材料
            rsid = request.GET.get('rsid', '')
            if not rsid:
                cursor.close()
                return JsonResponse({"code": 400, "msg": "缺少rsid"})

            cursor.execute(
                """SELECT ARCHID, RSID, XH, CLTM, FYEAR, FMONTH, FDAY, YS, BZ, FL
                   FROM RS_ARCHINFO WHERE RSID=? AND FL=? ORDER BY XH""",
                (int(rsid), int(pid))
            )
            cols = [col[0] for col in cursor.description]
            rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
            cursor.close()
            return JsonResponse({"code": 0, "data": rows})

    except Exception as e:
        logger.error(f"get_archive_tree error: {e}")
        return JsonResponse({"code": 500, "msg": str(e)})
    finally:
        if conn:
            conn.close()


@login_required
def api_check_scan(request):
    """检查是否已扫描"""
    image_type = request.GET.get('image_type', 'YS')
    rsid = request.GET.get('rsid', '')
    fl = request.GET.get('fl', '')
    archid = request.GET.get('archid', '')

    if image_type not in IMAGE_TYPES:
        return JsonResponse({'code': 400, 'msg': f'不支持的图像类型: {image_type}'})

    is_scanned, count = check_scan_exists(image_type, rsid, fl, archid)
    return JsonResponse({'code': 0, 'is_scanned': is_scanned, 'image_count': count})


@login_required
def api_generate_pdf(request):
    """生成/获取PDF"""
    image_type = request.GET.get('image_type', 'YS')
    rsid = request.GET.get('rsid', '')
    fl = request.GET.get('fl', '')
    archid = request.GET.get('archid', '')
    force = request.GET.get('force', '0') == '1'
    page_size = request.GET.get('page_size', settings.SCAN_PDF_PAGE_SIZE)
    vertical = request.GET.get('vertical', '1') == '1'

    if image_type not in IMAGE_TYPES:
        return JsonResponse({'code': 400, 'msg': f'不支持的图像类型: {image_type}'})

    success, result = get_or_generate_pdf(
        image_type=image_type,
        rsid=rsid,
        fl=fl,
        archid=archid,
        page_size=page_size,
        vertical=vertical,
        force_regenerate=force
    )

    if success:
        return JsonResponse({
            'code': 0,
            'success': True,
            'pdf_url': f'/archives/image/api/scan-pdf/?image_type={image_type}&rsid={rsid}&fl={fl}&archid={archid}'
        })
    else:
        return JsonResponse({'code': 0, 'success': False, 'message': result})


@login_required
def serve_pdf(request):
    """提供PDF文件"""
    image_type = request.GET.get('image_type', 'YS')
    rsid = request.GET.get('rsid', '')
    fl = request.GET.get('fl', '')
    archid = request.GET.get('archid', '')

    # 过滤掉可能附加的时间戳等参数
    if '?' in archid:
        archid = archid.split('?')[0]
    if '&' in archid:
        archid = archid.split('&')[0]

    if image_type not in IMAGE_TYPES:
        raise Http404(f'不支持的图像类型: {image_type}')

    latest_uptime, _ = get_latest_uptime(rsid, archid, image_type)

    if latest_uptime is None:
        raise Http404('未扫描或扫描未上传')

    pdf_path = build_pdf_path(image_type, rsid, fl, archid, latest_uptime)

    if not os.path.exists(pdf_path):
        raise Http404('PDF文件不存在，请先生成')

    return FileResponse(open(pdf_path, 'rb'), content_type='application/pdf')
