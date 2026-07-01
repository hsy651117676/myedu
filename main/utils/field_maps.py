# ==================== RS_INFO 字段映射 ====================

RS_INFO_MAP = {
    "姓名": "XM",
    "性别": "XB",
    "民族": "MZ",
    "籍贯": "JG",
    "出生地": "CHUSHENGDI",
    "人员状态": "RYLB",
    "出生年月": "CSNY",
    "参工时间": "WORKTIME",
    "政治面貌": "ZZMM",
    "入党时间": "JOINTIME",
    "工作单位及职务": "JOBUNIT",
    "任职时间": "APPOINTTIME",
    "领导职务": "ZW",
    "是否中层干部": "HSJS",
    "现任职称": "ZYZC",
    "身份证号": "IDCARD",
    "人员身份": "JRSJ",
    "最高学历": "WHCD",
    "联系电话": "SFZH",
    "档案编号": "RYBH",
    "工龄是否间断": "HSGZ",
    "近三年考核": "ZN",
    "退休时间": "TZSJ",
    "去世时间": "QSSJ",
    "年龄": "AGE",
    "工龄": "WORK_AGE",
    "健康状况": "HEALTH",
    "是否受过处分": "DUANQUECAILIAO",
    "全日制学历": "QUANRIZIXUELI",
    "全日制学校": "QUANRIZIYUANXIAO",
    "全日制专业": "QUANRIZIZHUANYE",
    "全日制入学": "RMSJ",
    "全日制毕业": "BYSJ",
    "全日制学位": "QUANRIZIXUEWEI",
    "在职学历": "ZAIZHIXUELI",
    "在职学校": "ZAIZHIYUANXIAO",
    "在职专业": "ZAIZHIZHUANYE",
    "在职入学": "PPSJ",
    "在职毕业": "YGXZ",
    "在职学位": "ZAIZHIXUEWEI",
    "档案整理人": "DANGANZHENGLIREN",
    "数字档案采集人": "SHUZIHUACAIJIREN",
    "档案卷数": "DANGANJUANSHU",
    "报送日期": "BAOSONGRIQI",
    "整理审核人": "DANGANSHENHEREN",
    "数字档案审核人": "SHUZIHUASHENHEREN",
    "档案报送单位": "BAOSONGDANWEI",
    "档案存在问题": "QINGKUANSHUOMI",
    "材料补齐情况": "CS",
    "认定文件内容": "DJYY",
    "档案是否数字化": "ARCHFILE",
    "照片": "DQZP",
}

# 分组
RS_INFO_GROUPS = {
    "base": [
        "姓名", "性别", "民族", "出生地", "籍贯", "人员状态",
        "出生年月", "参工时间", "政治面貌", "入党时间",
        "工作单位及职务", "任职时间", "领导职务",
        "是否中层干部", "现任职称", "身份证号", "人员身份", "最高学历",
        "联系电话", "档案编号", "柜号", "层号",
        "退休时间", "去世时间", "工龄是否间断", "近三年考核",
        "健康状况", "是否受过处分", "年龄", "工龄",
    ],
    "education_full": ["全日制学历", "全日制学校", "全日制专业", "全日制入学", "全日制毕业", "全日制学位"],
    "education_part": ["在职学历", "在职学校", "在职专业", "在职入学", "在职毕业", "在职学位"],
    "archive": ["档案整理人", "数字档案采集人", "档案卷数", "报送日期", "整理审核人", "数字档案审核人", "档案报送单位"],
    "audit": ["档案存在问题", "材料补齐情况", "认定文件内容"],
    "all": [],
}

# ==================== YW_INFO 字段映射 ====================

YW_INFO_MAP = {
    "柜号": "GH",
    "层号": "CH",
    "档案编号": "DABH",
}

# ==================== 专项审核 YW_ZXSHDJ 字段映射 ====================

ZXSHDJ_MAP = {
    # 出生年月
    "出生记载是否一致": "cssj1A",
    "出生最早材料类号": "cssj2B",
    "出生最早材料名称": "cssj2C",
    "出生最早材料形成时间": "cssj2D",
    "出生是否有涂改": "cssj5A",
    "出生时间罗列": "cssj",
    # 参工
    "参工记载是否一致": "cjgz1A",
    "参工起薪材料类号": "cjgz3B",
    "参工起薪材料名称": "cjgz3C",
    "参工起薪材料形成时间": "cjgz3D",
    "参工时间罗列": "cjgz",
    # 入党
    "入党材料是否齐全": "rdsj1A",
    "是否补填入党志愿书": "rdsj2A",
    "入党志愿书记载": "rdsj6B",
    "入党时间罗列": "rdsj",
    # 学历
    "学历材料是否齐全": "xlxw1A",
    "是否培训经历填为学历": "xlxw7A",
    "是否低学历填为高学历": "xlxw8A",
    "是否在职填为全日制": "xlxw9A",
    "是否无学位填为有学位": "xlxw10A",
    "学历罗列": "xlxw",
    # 工作经历
    "工作经历材料是否齐全": "gzjl1A",
    "是否破格": "gzjl4A",
    "破格材料是否齐全": "gzjl5A",
    "工作经历罗列": "gzjl",
    # 干部身份
    "干部身份材料是否齐全": "gbsf1A",
    "干部身份罗列": "gbsf",
    # 专业技术
    "专业技术材料是否齐全": "zyjs1A",
    "最高职称": "zyjs1C",
    "最高职称是否被聘": "zyjs2A",
    "专业技术罗列": "zyjs",
    # 奖惩
    "奖惩材料是否齐全": "jcqk1A",
    "奖惩罗列": "jcqk",
    # 民族
    "民族": "mc1A",
    "民族罗列": "mc",
    # 社会关系
    "社会关系是否齐全": "shgx1A",
    "社会关系罗列": "shgx",
    # 其他
    "其他问题": "qtwt",
    "审核意见": "shyj",
    "初审人": "shr1",
    "复审人": "shr2",
    "初审复审时间": "shrtime",
}

# ==================== 认定表 YW_ZXSHDJ 扩展字段 ====================

RDB_MAP = {
    "认定出生年月": "RDBa1",
    "出生认定依据材料": "RDBa2",
    "出生各种时间罗列": "RDBa3",
    "认定参工时间": "RDBb1",
    "参工认定依据材料": "RDBb2",
    "参工各种时间罗列": "RDBb3",
    "认定入党时间": "RDBc1",
    "入党认定依据材料": "RDBc2",
    "入党各种时间罗列": "RDBc3",
    "审核意见结论": "RDBd1",
    "组织人事部门意见": "RDBd2",
    "初审人": "RDBe1",
    "初审时间": "RDBe2",
    "复审人": "RDBe3",
    "复审时间": "RDBe4",
    "党组会时间": "RDBe5",
    "本人签字时间": "RDBe6",
    "本人意见": "RDBe7",
}

# ==================== 工资变动 YW_GZBD ====================

GZBD_MAP = {
    "序号": "sXH",
    "变动原因": "wh",
    "执行时间": "ZXSJ",
    "职务档次": "ZWGZ",
    "职务工资": "ZWJE",
    "级别档次": "JBGZ",
    "级别工资": "JBJE",
    "备注": "BZ",
}

# ==================== 职务变动 YW_ZWBD ====================

ZWBD_MAP = {
    "序号": "sXH",
    "任职时间": "RZSJ",
    "免职时间": "MZSJ",
    "部门": "BMmc",
    "职务": "ZW",
    "批准文号": "rzwh",
}

# ==================== 干部任免表 CADREAPPROVE ====================

CADREAPPROVE_MAP = {
    "ID": "ID",
    "名称": "BMMC",
    "姓名": "XM",
    "现任职务": "XIANRENZHIWU",
    "简历": "JL",
    "健康": "HEALTH",
    "专业技术职务": "ZHUANYEJISHUZHIWU",
    "拟任职务": "NIRENZHIWU",
    "拟免职务": "NIMIANZHIWU",
    "奖惩情况": "JIANGCHENGQINGKUANG",
    "年度考核": "YEARCHECK",
    "任免理由": "RENMIANREASON",
    "呈报单位": "CHENGBAODANWEI",
    "审批机关意见": "SHENPIJIGUANYIJIAN",
}

# ==================== 家庭成员 Z_FamilyMembers ====================

FAMILY_MAP = {
    "称谓": "appellation",
    "姓名": "name",
    "年龄": "nianling",
    "出生年月": "csny",
    "政治面貌": "PoliticalLandscape",
    "工作单位": "workUnit",
}

# ==================== 补充信息 Z_supplement ====================

SUPPLEMENT_MAP = {
    "年度考核结果": "assessmentResults",
    "奖励情况": "reward",
    "简历": "resume",
}

# ==================== 档案目录 RS_ARCHINFO ====================

ARCHINFO_MAP = {
    "编号": "编号",
    "材料名称": "CLTM",
    "年": "FYEAR",
    "月": "FMONTH",
    "日": "FDAY",
    "页数": "YS",
    "备注": "BZ",
    "分类": "FL",
    "序号": "XH",
    "ARCHID": "ARCHID",
}

# ==================== 工具函数 ====================

def to_frontend(db_row: dict, field_map: dict) -> dict:
    """数据库字段名 → 前端中文名"""
    result = {}
    for cn_name, db_field in field_map.items():
        result[cn_name] = db_row.get(db_field, "")
    return result


def to_backend(frontend_data: dict, field_map: dict) -> dict:
    """前端中文名 → 数据库字段名"""
    result = {}
    for cn_name, db_field in field_map.items():
        if cn_name in frontend_data:
            result[db_field] = frontend_data[cn_name]
    return result
