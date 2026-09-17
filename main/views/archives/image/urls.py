from django.urls import path
from main.views.archives.image import scan_viewer
from . import image_editor
from . import scan_upload
from . import ocr_batch
from . import ocr_batch_new
from . import scan_stats

app_name = "archive_image"

urlpatterns = [
    path("scan/", scan_viewer.scan_page, name="scan_page"),
    path("api/scan-check/", scan_viewer.api_check_scan, name="scan_check"),
    path(
        "api/scan-generate-pdf/", scan_viewer.api_generate_pdf, name="scan_generate_pdf"
    ),
    path(
        "api/batch-generate-pdf/",
        scan_viewer.api_batch_generate_pdf,
        name="batch_generate_pdf",
    ),
    path("api/scan-pdf/", scan_viewer.serve_pdf, name="scan_pdf"),
    path("editor/", image_editor.page, name="image-editor"),
    path("api/upload-scan/", scan_upload.upload_scan_api, name="scan-upload-scan"),
    path("clean-orphans/", scan_upload.clean_orphans_api, name="clean-orphans"),
    path("api/delete-scan/", scan_upload.delete_scan_api, name="scan-delete-scan"),
    path("api/download-zip/", scan_viewer.api_download_zip, name="download_zip"),
    path(
        "api/update-page-count/",
        scan_upload.update_page_count_api,
        name="update_page_count",
    ),
    #  按单位同类材料自动扫描归档
    path("ocr-batch/", ocr_batch.page, name="ocr_batch_page"),
    path("api/ocr-unit-list/", ocr_batch.unit_list_api),
    path("api/ocr-category-tree/", ocr_batch.category_tree_api),
    path("api/ocr-unit-persons/", ocr_batch.unit_persons_api),
    path("api/ocr-existing-count/", ocr_batch.existing_count_api),
    path("api/ocr-detect-structure/", ocr_batch.detect_structure_api),
    path("api/ocr-verify/", ocr_batch.ocr_verify_api),
    path("api/ocr-retry/", ocr_batch.retry_ocr_api),
    path("api/ocr-preview-pdf/", ocr_batch.preview_pdf_api),
    path("api/ocr-single-write/", ocr_batch.single_write_api),
    path("api/ocr-batch-write/", ocr_batch.batch_write_api),
    path("ocr-batch-new/", ocr_batch_new.page, name="ocr_batch_new_page"),
    path("api/ocr-new-unit-list/", ocr_batch_new.unit_list_api),
    path("api/ocr-new-category-tree/", ocr_batch_new.category_tree_api),
    path("api/ocr-new-unit-persons/", ocr_batch_new.unit_persons_api),
    path("api/ocr-new-existing-count/", ocr_batch_new.existing_count_api),
    path("api/ocr-new-detect-structure/", ocr_batch_new.detect_structure_api),
    path("api/ocr-new-verify/", ocr_batch_new.ocr_verify_api),
    path("api/ocr-new-preview-pdf/", ocr_batch_new.preview_pdf_api),
    path("api/ocr-new-single-write/", ocr_batch_new.single_write_api),
    path("api/ocr-new-batch-write/", ocr_batch_new.batch_write_api),
    path("scan-stats/", scan_stats.page, name="scan_stats_page"),
    path("api/scan-stats-unit-list/", scan_stats.unit_list_api),
    path("api/scan-stats-data/", scan_stats.stats_api),
]
