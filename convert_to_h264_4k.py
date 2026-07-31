import os, sys, subprocess

sys.path.insert(0, '/home/hsy/myedu')
os.environ['DJANGO_SETTINGS_MODULE'] = 'myedu.settings'
import django
django.setup()

from django.conf import settings

MEDIA_BASE_DIR = settings.MEDIA_BASE_DIR
TARGET_DIR = os.path.join(MEDIA_BASE_DIR, 'mp4', 'S', '三国演义')
LOG_FILE = '/tmp/ffmpeg_convert.log'

files = sorted([f for f in os.listdir(TARGET_DIR) if f.endswith('.mp4')])
total = len(files)
converted = 0
failed = []

for i, fname in enumerate(files, 1):
    file_path = os.path.join(TARGET_DIR, fname)
    print(f"[{i}/{total}] {fname}", flush=True)
    
    tmp = file_path + ".h264.mp4"
    
    with open(LOG_FILE, 'w') as log:
        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", file_path,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            tmp
        ], stdout=log, stderr=log)
    
    if result.returncode == 0:
        os.replace(tmp, file_path)
        converted += 1
        print(f"  ✓ [{converted}/{total}]")
    else:
        if os.path.exists(tmp): os.remove(tmp)
        failed.append(fname)
        print(f"  ✗")

print(f"\n成功: {converted}, 失败: {len(failed)}")
if failed:
    print("失败:")
    for f in failed:
        print(f"  - {f}")
