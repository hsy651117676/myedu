"""
档案扫描查看 - 视图层
"""

import os
import glob
import logging
from django.http import JsonResponse, FileResponse, Http404
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
from main.utils import _get_conn
from main.views.archives.image.scan_service import (
    get_or_generate_pdf,
    check_scan_exists,
    build_pdf_path,
    build_pdf_dir,
    IMAGE_TYPES,
)

from main.utils.decorators import archive_perm_required
logger = logging.getLogger(__name__)


@login_required
@archive_perm_required
def scan_page(request):
    """档案扫描查看页面入口"""
    return render(request, 'archives/image/scan_viewer.html')


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
    image_type = request.GET.get('image_type', 'YS')
    rsid = request.GET.get('rsid', '')
    fl = request.GET.get('fl', '')
    archid = request.GET.get('archid', '')

    if '?' in archid:
        archid = archid.split('?')[0]
    if '&' in archid:
        archid = archid.split('&')[0]

    if image_type not in IMAGE_TYPES:
        raise Http404

    pdf_dir = build_pdf_dir(image_type, rsid, fl, archid)

    if not os.path.exists(pdf_dir):
        raise Http404('PDF不存在')

    pattern = os.path.join(pdf_dir, f"{fl}_*.pdf")
    matches = sorted(glob.glob(pattern), reverse=True)

    if not matches:
        raise Http404('PDF不存在')

    response = FileResponse(open(matches[0], 'rb'), content_type='application/pdf')
    response['Cache-Control'] = 'public, max-age=3600'
    return response

