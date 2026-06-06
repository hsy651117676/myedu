# mediaplayer.py
import os
import json
import hashlib
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.db import connection
from django.http import HttpResponse

MEDIA_BASE_DIR = getattr(settings, "MEDIA_BASE_DIR", "/mnt/data/media")
ALLOWED_AUDIO = {"mp3", "wav", "flac", "ogg", "aac", "wma"}
ALLOWED_VIDEO = {"mp4", "mkv", "avi", "mov", "wmv", "flv", "webm"}


def _get_first_letter(text):
    if not text:
        return "#"
    ch = text[0]
    if "a" <= ch.lower() <= "z":
        return ch.upper()
    if "0" <= ch <= "9":
        return "0-9"
    try:
        from pypinyin import lazy_pinyin

        py = lazy_pinyin(ch)
        if py and py[0]:
            first = py[0][0].upper()
            if "A" <= first <= "Z":
                return first
    except:
        pass
    return "#"


def _get_table(category):
    if category == "music":
        return "MusicFiles"
    elif category == "movie":
        return "MovieFiles"
    elif category == "tv":
        return "TvFiles"
    return "MusicFiles"


def player_page(request):
    return render(request, "tools/media_player.html")


@login_required
def manage_page(request):
    return render(request, "tools/media_manage.html")


@login_required
def list_api(request):
    category = request.GET.get("category", "music").strip()
    letter = request.GET.get("letter", "").strip()
    keyword = request.GET.get("keyword", "").strip()
    instrument = request.GET.get("instrument", "").strip()
    style = request.GET.get("style", "").strip()
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 20))

    table = _get_table(category)
    with connection.cursor() as cursor:
        where = "WHERE IsActive = 1"
        params = []
        if letter:
            where += " AND FirstLetter = %s"
            params.append(letter)
        if keyword:
            kw = f"%{keyword}%"
            if category == "music":
                where += " AND (Title LIKE %s OR Artist LIKE %s)"
            else:
                where += " AND (Title LIKE %s OR Director LIKE %s)"
            params.extend([kw, kw])
        if instrument and category == "music":
            where += " AND Instrument = %s"
            params.append(instrument)
        if style and category == "music":
            where += " AND Style = %s"
            params.append(style)

        cursor.execute(f"SELECT COUNT(*) FROM {table} {where}", params)
        total = cursor.fetchone()[0]
        offset = (page - 1) * page_size
        cursor.execute(
            f"SELECT * FROM {table} {where} ORDER BY FirstLetter, Title LIMIT %s OFFSET %s",
            params + [page_size, offset],
        )
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        return JsonResponse({"code": 0, "data": rows, "total": total})


def play_api(request):
    file_id = request.GET.get("id", "")
    category = request.GET.get("category", "music").strip()
    if not file_id:
        raise Http404

    table = _get_table(category)
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT FilePath, FileName, MediaType FROM {table} WHERE ID = %s AND IsActive = 1",
            (int(file_id),),
        )
        row = cursor.fetchone()
        if not row:
            raise Http404
        full_path = os.path.join(MEDIA_BASE_DIR, row[0])
        if not os.path.exists(full_path):
            raise Http404
        cursor.execute(
            f"UPDATE {table} SET PlayCount = PlayCount + 1 WHERE ID = %s",
            (int(file_id),),
        )

        ext = row[2] or os.path.splitext(row[0])[1].lstrip(".").lower()
        content_type = f"audio/{ext}" if ext in ALLOWED_AUDIO else f"video/{ext}"
        resp = FileResponse(open(full_path, "rb"), content_type=content_type)
        resp["Content-Disposition"] = f'inline; filename="{row[1]}"'
        resp["Accept-Ranges"] = "bytes"
        return resp


@login_required
@csrf_exempt
def upload_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})

    uploaded_file = request.FILES.get("file")
    category = request.POST.get("category", "music").strip()
    title = request.POST.get("title", "").strip()
    artist = request.POST.get("artist", "").strip()

    if not uploaded_file:
        return JsonResponse({"code": 400, "msg": "请选择文件"})

    ext = os.path.splitext(uploaded_file.name)[1].lstrip(".").lower()
    os.makedirs(MEDIA_BASE_DIR, exist_ok=True)
    tmp_path = os.path.join(MEDIA_BASE_DIR, "tmp_" + uploaded_file.name)
    with open(tmp_path, "wb+") as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)

    # 分类校验
    if category == "music" and ext not in ALLOWED_AUDIO:
        os.remove(tmp_path)
        return JsonResponse(
            {"code": 400, "msg": f"音乐分类不支持 .{ext} 格式，请选择正确的分类"}
        )
    if category in ("movie", "tv") and ext not in ALLOWED_VIDEO:
        os.remove(tmp_path)
        return JsonResponse(
            {"code": 400, "msg": f"视频分类不支持 .{ext} 格式，请选择正确的分类"}
        )

    md5_value = hashlib.md5(open(tmp_path, "rb").read()).hexdigest()
    table = _get_table(category)

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT ID FROM {table} WHERE MD5Hash = %s AND IsActive = 1", (md5_value,)
        )
        if cursor.fetchone():
            os.remove(tmp_path)
            return JsonResponse({"code": 400, "msg": "文件已存在"})

    # 音频读取ID3标签
    if category == "music":
        try:
            from mutagen.id3 import ID3

            tags = ID3(tmp_path)
            if not title:
                t = tags.get("TIT2")
                if t:
                    title = str(t.text[0]) if hasattr(t, "text") else str(t)
            if not artist:
                a = tags.get("TPE1")
                if a:
                    artist = str(a.text[0]) if hasattr(a, "text") else str(a)
        except:
            try:
                from mutagen.easyid3 import EasyID3

                easy = EasyID3(tmp_path)
                if not title:
                    title = easy.get("title", [""])[0]
                if not artist:
                    artist = easy.get("artist", [""])[0]
            except:
                pass

    # 从文件名解析
    name_no_ext = os.path.splitext(uploaded_file.name)[0]
    if " - " in name_no_ext and not artist and category == "music":
        parts = name_no_ext.split(" - ", 1)
        artist = parts[0].strip()
        if not title:
            title = parts[1].strip()

    if not title:
        title = name_no_ext
    if not artist:
        artist = "未知歌手" if category == "music" else "未知"

    first_letter = _get_first_letter(artist if category == "music" else title)

    # 目录：扩展名/首字母/...
    if category == "music":
        dir_path = os.path.join(MEDIA_BASE_DIR, ext, first_letter, artist)
    elif category == "movie":
        dir_path = os.path.join(MEDIA_BASE_DIR, ext, first_letter)
    else:
        dir_path = os.path.join(MEDIA_BASE_DIR, ext, first_letter, title)
    os.makedirs(dir_path, exist_ok=True)

    file_name = title + "." + ext
    full_path = os.path.join(dir_path, file_name)
    if os.path.exists(full_path):
        i = 1
        while os.path.exists(os.path.join(dir_path, f"{title}_{i}.{ext}")):
            i += 1
        file_name = f"{title}_{i}.{ext}"
        full_path = os.path.join(dir_path, file_name)

    os.rename(tmp_path, full_path)
    file_size = os.path.getsize(full_path)
    duration = 0
    try:
        from mutagen import File as MutagenFile

        audio = MutagenFile(full_path)
        if audio and hasattr(audio.info, "length"):
            duration = int(audio.info.length)
    except:
        pass

    relative_path = os.path.relpath(full_path, MEDIA_BASE_DIR)

    if category == "music":
        instrument = request.POST.get("instrument", "").strip()
        style = request.POST.get("style", "").strip()
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO MusicFiles (Title, Artist, FirstLetter, FilePath, FileName, MediaType, FileSize, Duration, Instrument, Style, MD5Hash)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    title,
                    artist,
                    first_letter,
                    relative_path,
                    file_name,
                    ext,
                    file_size,
                    duration,
                    instrument,
                    style,
                    md5_value,
                ),
            )
    elif category == "movie":
        movie_year = request.POST.get("year", "").strip()
        genre = request.POST.get("genre", "").strip()
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO MovieFiles (Title, Director, FirstLetter, FilePath, FileName, MediaType, FileSize, Duration, Year, Genre, MD5Hash)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    title,
                    artist,
                    first_letter,
                    relative_path,
                    file_name,
                    ext,
                    file_size,
                    duration,
                    movie_year,
                    genre,
                    md5_value,
                ),
            )
    else:
        season = request.POST.get("season", "").strip()
        episode = request.POST.get("episode", "").strip()
        episode_title = request.POST.get("episode_title", "").strip()
        tv_year = request.POST.get("year", "").strip()
        genre = request.POST.get("genre", "").strip()
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO TvFiles (Title, Director, Season, Episode, EpisodeTitle, FirstLetter, FilePath, FileName, MediaType, FileSize, Duration, Year, Genre, MD5Hash)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    title,
                    artist,
                    season,
                    episode,
                    episode_title,
                    first_letter,
                    relative_path,
                    file_name,
                    ext,
                    file_size,
                    duration,
                    tv_year,
                    genre,
                    md5_value,
                ),
            )

    return JsonResponse({"code": 0, "msg": "上传成功"})


@login_required
@csrf_exempt
def delete_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})
    try:
        data = json.loads(request.body)
        file_id = data.get("id")
        category = data.get("category", "music").strip()
    except:
        return JsonResponse({"code": 400})

    table = _get_table(category)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT FilePath FROM {table} WHERE ID = %s", (int(file_id),))
        row = cursor.fetchone()
        if row:
            full_path = os.path.join(MEDIA_BASE_DIR, row[0])
            if os.path.exists(full_path):
                os.remove(full_path)
        cursor.execute(f"DELETE FROM {table} WHERE ID = %s", (int(file_id),))
    return JsonResponse({"code": 0, "msg": "删除成功"})


@login_required
def letters_api(request):
    category = request.GET.get("category", "music").strip()
    table = _get_table(category)
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT DISTINCT FirstLetter FROM {table} WHERE IsActive = 1 ORDER BY FirstLetter"
        )
        letters = [r[0] for r in cursor.fetchall()]
    return JsonResponse({"code": 0, "data": letters})


@login_required
def instruments_api(request):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT Instrument FROM MusicFiles WHERE IsActive = 1 AND Instrument != '' ORDER BY Instrument"
        )
        data = [r[0] for r in cursor.fetchall()]
    return JsonResponse({"code": 0, "data": data})


@login_required
def styles_api(request):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT Style FROM MusicFiles WHERE IsActive = 1 AND Style != '' ORDER BY Style"
        )
        data = [r[0] for r in cursor.fetchall()]
    return JsonResponse({"code": 0, "data": data})


@login_required
@csrf_exempt
def edit_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405})

    file_id = request.POST.get("id", "")
    category = request.POST.get("category", "music").strip()
    title = request.POST.get("title", "").strip()
    artist = request.POST.get("artist", "").strip()

    if not file_id:
        return JsonResponse({"code": 400, "msg": "缺少ID"})
    if not title:
        return JsonResponse({"code": 400, "msg": "标题不能为空"})

    table = _get_table(category)

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT FilePath, FileName, MediaType FROM {table} WHERE ID = %s",
            (int(file_id),),
        )
        row = cursor.fetchone()
        if not row:
            return JsonResponse({"code": 404, "msg": "记录不存在"})

        old_path, old_name, ext = row
        old_full = os.path.join(MEDIA_BASE_DIR, old_path)

        # 新目录
        if not artist:
            artist = "未知歌手" if category == "music" else "未知"
        first_letter = _get_first_letter(artist if category == "music" else title)

        if category == "music":
            new_dir = os.path.join(MEDIA_BASE_DIR, ext, first_letter, artist)
        elif category == "movie":
            new_dir = os.path.join(MEDIA_BASE_DIR, ext, first_letter)
        else:
            new_dir = os.path.join(MEDIA_BASE_DIR, ext, first_letter, title)

        new_name = title + "." + ext
        new_full = os.path.join(new_dir, new_name)

        # 移动文件
        if old_full != new_full:
            os.makedirs(new_dir, exist_ok=True)
            if os.path.exists(old_full):
                if os.path.exists(new_full):
                    i = 1
                    while os.path.exists(os.path.join(new_dir, f"{title}_{i}.{ext}")):
                        i += 1
                    new_name = f"{title}_{i}.{ext}"
                    new_full = os.path.join(new_dir, new_name)
                os.rename(old_full, new_full)

        new_relative = os.path.relpath(new_full, MEDIA_BASE_DIR)

        if category == "music":
            instrument = request.POST.get("instrument", "").strip()
            style = request.POST.get("style", "").strip()
            cursor.execute(
                """UPDATE MusicFiles SET Title=%s, Artist=%s, FirstLetter=%s, FilePath=%s, FileName=%s, Instrument=%s, Style=%s WHERE ID=%s""",
                (
                    title,
                    artist,
                    first_letter,
                    new_relative,
                    new_name,
                    instrument,
                    style,
                    int(file_id),
                ),
            )
        elif category == "movie":
            movie_year = request.POST.get("year", "").strip()
            genre = request.POST.get("genre", "").strip()
            cursor.execute(
                """UPDATE MovieFiles SET Title=%s, Director=%s, FirstLetter=%s, FilePath=%s, FileName=%s, Year=%s, Genre=%s WHERE ID=%s""",
                (
                    title,
                    artist,
                    first_letter,
                    new_relative,
                    new_name,
                    movie_year,
                    genre,
                    int(file_id),
                ),
            )
        else:
            season = request.POST.get("season", "").strip()
            episode = request.POST.get("episode", "").strip()
            episode_title = request.POST.get("episode_title", "").strip()
            tv_year = request.POST.get("year", "").strip()
            genre = request.POST.get("genre", "").strip()
            cursor.execute(
                """UPDATE TvFiles SET Title=%s, Director=%s, Season=%s, Episode=%s, EpisodeTitle=%s, FirstLetter=%s, FilePath=%s, FileName=%s, Year=%s, Genre=%s WHERE ID=%s""",
                (
                    title,
                    artist,
                    season,
                    episode,
                    episode_title,
                    first_letter,
                    new_relative,
                    new_name,
                    tv_year,
                    genre,
                    int(file_id),
                ),
            )

    return JsonResponse({"code": 0, "msg": "保存成功"})


def cover_api(request):
    file_id = request.GET.get("id", "")
    category = request.GET.get("category", "music").strip()
    if not file_id:
        raise Http404

    table = _get_table(category)
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT FilePath FROM {table} WHERE ID = %s AND IsActive = 1",
            (int(file_id),),
        )
        row = cursor.fetchone()
        if not row:
            raise Http404
        full_path = os.path.join(MEDIA_BASE_DIR, row[0])
        if not os.path.exists(full_path):
            raise Http404

    try:
        from mutagen.id3 import ID3

        tags = ID3(full_path)
        for key in tags.keys():
            if key.startswith("APIC"):
                cover = tags[key].data
                mime = tags[key].mime or "image/jpeg"
                return HttpResponse(cover, content_type=mime)
    except:
        pass

    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200"><rect fill="#333" width="200" height="200"/><text fill="#aaa" x="100" y="110" text-anchor="middle" font-size="50">🎵</text></svg>'
    return HttpResponse(svg, content_type="image/svg+xml")
