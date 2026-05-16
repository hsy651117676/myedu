from django.urls import path
from main.views.archives.image import scan_viewer

app_name = 'archive_image'

urlpatterns = [
    path('scan/', scan_viewer.scan_page, name='scan_page'),
    path('api/archive-tree/', scan_viewer.get_archive_tree, name='archive_tree'),
    path('api/scan-check/', scan_viewer.api_check_scan, name='scan_check'),
    path('api/scan-generate-pdf/', scan_viewer.api_generate_pdf, name='scan_generate_pdf'),
    path('api/scan-pdf/', scan_viewer.serve_pdf, name='scan_pdf'),
]
