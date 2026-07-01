# fix_sanguo_faststart.py
import os, sys, subprocess

sys.path.insert(0, "/home/hsy/myedu")
os.environ["DJANGO_SETTINGS_MODULE"] = "myedu.settings"
import django

django.setup()

from django.conf import settings
from django.db import connection

MEDIA_BASE_DIR = settings.MEDIA_BASE_DIR
TARGET_DIR = os.path.join(MEDIA_BASE_DIR, "mp4", "S", "三国演义")
LOG_FILE = "/tmp/ffmpeg_fix.log"

fixed = 0
failed = []

for fname in sorted(os.listdir(TARGET_DIR)):
    if not fname.endswith(".mp4"):
        continue

    file_path = os.path.join(TARGET_DIR, fname)
    rel = os.path.relpath(file_path, MEDIA_BASE_DIR)

    with connection.cursor() as cur:
        cur.execute("SELECT IsFastStart FROM TvFiles WHERE FilePath=%s", (rel,))
        row = cur.fetchone()
        if row and row[0] == 1:
            print(f"⏭ 已处理: {fname}")
            continue

    size_mb = os.path.getsize(file_path) // 1024 // 1024
    print(f"处理: {fname} ({size_mb}MB)", end=" ", flush=True)

    # 临时文件必须用 .mp4 后缀，ffmpeg 才能识别输出格式
    tmp = file_path + ".fix.mp4"

    with open(LOG_FILE, "w") as log:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                file_path,
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                tmp,
            ],
            stdout=log,
            stderr=log,
        )

    if result.returncode == 0:
        os.replace(tmp, file_path)
        with connection.cursor() as cur:
            cur.execute("UPDATE TvFiles SET IsFastStart=1 WHERE FilePath=%s", (rel,))
        fixed += 1
        print("✓")
    else:
        if os.path.exists(tmp):
            os.remove(tmp)
        failed.append(fname)
        print(f"✗")

print(f"\n成功: {fixed}, 失败: {len(failed)}")
