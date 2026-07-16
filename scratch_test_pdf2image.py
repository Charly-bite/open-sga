import os
from pdf2image import convert_from_path

poppler_path = os.path.abspath("poppler-24.08.0/Library/bin")
print("Poppler path:", poppler_path)
print("Exists:", os.path.exists(poppler_path))
test_pdf = "test_label.pdf"  # assuming this exists based on list_dir
try:
    images = convert_from_path(test_pdf, dpi=300, poppler_path=poppler_path)
    print("Success, images:", len(images))
except Exception:
    import traceback

    traceback.print_exc()
