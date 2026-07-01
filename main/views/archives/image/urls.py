from django.urls import path
from main.views.archives.image import scan_viewer
from . import image_editor
from . import scan_upload
from . import ocr_batch

app_name = "archive_image"

urlpatterns = [
    path("scan/", scan_viewer.scan_page, name="scan_page"),
    path("api/scan-check/", scan_viewer.api_check_scan, name="scan_check"),
    path(
        "api/scan-generate-pdf/", scan_viewer.api_generate_pdf, name="scan_generate_pdf"
    ),
    path("api/scan-pdf/", scan_viewer.serve_pdf, name="scan_pdf"),
    path("editor/", image_editor.page, name="image-editor"),
    path("api/upload-scan/", scan_upload.upload_scan_api, name="scan-upload-scan"),
    path("clean-orphans/", scan_upload.clean_orphans_api, name="clean-orphans"),
    path("api/delete-scan/", scan_upload.delete_scan_api, name="scan-delete-scan"),
    path(
        "api/update-page-count/",
        scan_upload.update_page_count_api,
        name="update_page_count",
    ),
    path("ocr-batch/", ocr_batch.page, name="ocr_batch_page"),
    path("api/ocr-unit-list/", ocr_batch.unit_list_api, name="ocr_unit_list"),
    path(
        "api/ocr-category-tree/", ocr_batch.category_tree_api, name="ocr_category_tree"
    ),
    path("api/ocr-unit-persons/", ocr_batch.unit_persons_api, name="ocr_unit_persons"),
    path(
        "api/ocr-existing-count/",
        ocr_batch.existing_count_api,
        name="ocr_existing_count",
    ),
    path("api/ocr-verify/", ocr_batch.ocr_verify_api, name="ocr_verify"),
    path("api/ocr-preview-pdf/", ocr_batch.preview_pdf_api, name="ocr_preview_pdf"),
    path("api/ocr-batch-write/", ocr_batch.batch_write_api, name="ocr_batch_write"),
]
