from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import pyodbc
from django.core.cache import cache

def get_db():
    conn = pyodbc.connect(
        "DRIVER={FreeTDS};"
        "SERVER=192.168.1.100;"
        "PORT=1433;"
        "DATABASE=rs_new;"
        "UID=sa;"
        "PWD=Rs_new;"
        "TDS_Version=7.2;"
        "Encrypt=No;"
    )
    cursor = conn.cursor()
    return conn, cursor

@login_required
def person_query(request):
    return render(request, 'people/person_query.html')

@login_required
def person_manage(request):
    return render(request, 'people/person_manage.html')

@login_required
def data_change(request):
    return render(request, 'people/data_change.html')

@login_required
def person_query_api(request):
    name = request.GET.get("name", "").strip()
    idCard = request.GET.get("idCard", "").strip()
    address = request.GET.get("address", "").strip()
    workUnit = request.GET.get("workUnit", "").strip()  # 新增：接收工作单位参数
    page = int(request.GET.get("page", 1))
    pageSize = int(request.GET.get("pageSize", 30))

    try:
        conn, cursor = get_db()
        cursor.execute("{CALL B_population_EDIT('SELECT', 0, ?, ?, '', '', '', '', '', ?, ?, '', '', '', '', ?, ?)}",
            (idCard, name, address, workUnit, page, pageSize)
        )

        data = []
        columns = [col[0] for col in cursor.description]
        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))
            data.append({
                "RSID": row_dict["RSID"],
                "IDCard": row_dict["IDCard"],
                "Name": row_dict["Name"],
                "FormerName": row_dict["FormerName"],
                "Nation": row_dict["Nation"],
                "Gender": row_dict["Gender"],
                "DeathDate": row_dict["DeathDate"],
                "BirthDate": row_dict["BirthDate"],
                "HomeAddress": row_dict["HomeAddress"],
                "WorkUnit": row_dict["WorkUnit"],
                "Telephone": row_dict["Telephone"],
                "fatherID": row_dict["fatherID"],
                "motherID": row_dict["motherID"],
                "SpouseID": row_dict["SpouseID"],
            })
        cursor.nextset()
        total_row = cursor.fetchone()
        total = total_row[0] if total_row else 0
        cursor.close()
        conn.close()
        return JsonResponse({"code": 0, "data": data, "total": total})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})

@login_required
@csrf_exempt
def person_save_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST"})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"code": 400, "msg": "参数格式错误"})
    rsid = data.get("RSID")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "请选择人员"})
    try:
        conn, cursor = get_db()
        cursor.execute("SELECT IDCard, Name FROM B_population WHERE RSID=?", (rsid,))
        real_user = cursor.fetchone()
        if not real_user:
            return JsonResponse({"code": 400, "msg": "人员不存在"})
        real_idcard = real_user[0]
        real_name = real_user[1]
        cursor.execute("""
            EXEC B_population_EDIT 
                @TYPE='UPDATE',
                @RSID=?, @IDCard=?, @Name=?, 
                @FormerName=?, @Nation=?, @Gender=?,
                @DeathDate=?, @BirthDate=?, @HomeAddress=?, @WorkUnit=?, @Telephone=?,
                @fatherID=?, @motherID=?, @SpouseID=?
        """, (
            rsid,
            real_idcard,
            real_name,
            data.get("FormerName", ""),
            data.get("Nation", ""),
            data.get("Gender", ""),
            data.get("DeathDate", ""),
            data.get("BirthDate", ""),
            data.get("HomeAddress", ""),
            data.get("WorkUnit", ""),
            data.get("Telephone", ""),
            data.get("fatherID", ""),
            data.get("motherID", ""),
            data.get("SpouseID", "")
        ))
        conn.commit()
        cache.delete(f"family_{rsid}")
        cursor.execute("""
            EXEC B_population_EDIT 
                @TYPE='QUERY', @RSID=?, 
                @IDCard='',@Name='',@FormerName='',@Nation='',@Gender='',
                @DeathDate='',@BirthDate='',@HomeAddress='',@WorkUnit='',@Telephone='',
                @fatherID='',@motherID='',@SpouseID=''
        """, (rsid,))
        family = []
        columns = [col[0] for col in cursor.description]
        for row in cursor.fetchall():
            family.append(dict(zip(columns, row)))
        cache.set(f"family_{rsid}", family, timeout=600)
        conn.close()
        return JsonResponse({"code": 0, "msg": "保存成功"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": "保存失败：" + str(e)})

@login_required
@csrf_exempt
def key_data_update_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "方法错误"})
    if not request.user.is_superuser:
        return JsonResponse({"code": 403, "msg": "无权限，仅超级管理员可操作"})
    data = json.loads(request.body)
    rsid = data.get("RSID")
    new_name = data.get("Name", "").strip()
    new_idcard = data.get("IDCard", "").strip()
    if not rsid or not new_name or not new_idcard:
        return JsonResponse({"code": 400, "msg": "姓名、身份证不能为空"})
    try:
        conn, cursor = get_db()
        cursor.execute("""
            SELECT RSID, IDCard, Name, FormerName, Nation, Gender, DeathDate, BirthDate, 
                   HomeAddress, WorkUnit, Telephone, fatherID, motherID, SpouseID 
            FROM B_population WHERE RSID=?
        """, (rsid,))
        old = cursor.fetchone()
        if not old:
            conn.close()
            return JsonResponse({"code": 404, "msg": "未找到人员"})
        cursor.execute("""
            EXEC B_population_EDIT
                @TYPE='UPDATE',
                @RSID=?,
                @IDCard=?,
                @Name=?,
                @FormerName=?,
                @Nation=?,
                @Gender=?,
                @DeathDate=?,
                @BirthDate=?,
                @HomeAddress=?,
                @WorkUnit=?,
                @Telephone=?,
                @fatherID=?,
                @motherID=?,
                @SpouseID=?
        """, (
            rsid, new_idcard, new_name,
            old.FormerName,
            old.Nation,
            old.Gender,
            old.DeathDate,
            old.BirthDate,
            old.HomeAddress,
            old.WorkUnit,
            old.Telephone,
            old.fatherID,
            old.motherID,
            old.SpouseID
        ))
        conn.commit()
        conn.close()
        return JsonResponse({"code": 0, "msg": "关键数据修改成功"})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})

@login_required
def family_query_api(request):
    rsid = request.GET.get("rsid", "")
    if not rsid:
        return JsonResponse({"code": 400, "msg": "缺少RSID"})
    cache_key = f"family_{rsid}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return JsonResponse({"code": 0, "data": cached_data})
    try:
        conn, cursor = get_db()
        cursor.execute("""
            EXEC B_population_EDIT
                @TYPE='QUERY',
                @RSID=?,
                @IDCard='',@Name='',@FormerName='',@Nation='',@Gender='',
                @DeathDate='',@BirthDate='',@HomeAddress='',@WorkUnit='',@Telephone='',
                @fatherID='',@motherID='',@SpouseID=''
        """, (rsid,))
        family = []
        columns = [col[0] for col in cursor.description]
        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))
            family.append({
                "RSID": row_dict["RSID"],
                "关系": row_dict["关系"],
                "姓名": row_dict["姓名"],
                "民族": row_dict["民族"],
                "性别": row_dict["性别"],
                "出生时间": str(row_dict["出生时间"])[:10] if row_dict["出生时间"] else "",
                "家庭住址": row_dict["家庭住址"],
                "工作单位": row_dict["工作单位"],
                "联系电话": row_dict["联系电话"],
                "身份证号": row_dict["身份证号"],
                "死亡时间": str(row_dict["死亡时间"])[:10] if row_dict["死亡时间"] else "",
                "父亲身份证号": row_dict["父亲身份证号"],
                "母亲身份证号": row_dict["母亲身份证号"],
                "配偶身份证号": row_dict["配偶身份证号"]
            })
        conn.close()
        cache.set(cache_key, family, timeout=600)
        return JsonResponse({"code": 0, "data": family})
    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e)})
