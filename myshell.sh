#!/bin/bash
# 创建模板目录和所有文件

DIR=/home/hsy/myedu/templates/archives
mkdir -p $DIR

# 占位内容
PLACEHOLDER='<div v-if="detail.rsid" style="text-align:center;color:#909399;margin-top:150px;">开发中...</div>
<div v-else style="text-align:center;color:#909399;margin-top:150px;">请选择人员</div>'

# person_search.html
cat >$DIR/person_search.html <<'EOF'
<div style="margin-bottom:6px;">
  <el-select v-model="q.unit_id" placeholder="全部" clearable filterable size="small" style="width:100%;" @change="doQuery">
    <el-option label="全部" value="0"></el-option>
    <el-option v-for="u in unitList" :key="u.id" :label="u.name" :value="u.id"></el-option>
  </el-select>
</div>
<div style="margin-bottom:6px;">
  <el-input v-model="q.name" placeholder="输入姓名搜索" size="small" @keyup.enter="doQuery"></el-input>
</div>
<div style="margin-bottom:8px;display:flex;gap:6px;">
  <el-button type="primary" size="small" @click="doQuery">查询</el-button>
  <el-button size="small" @click="resetQuery">重置</el-button>
</div>
<el-table :data="list" border size="small" style="flex:1;" height="100%;" highlight-current-row
  @row-click="selectPerson" @row-dblclick="selectPersonAndLoad">
  <el-table-column label="姓名" prop="姓名" width="70"></el-table-column>
  <el-table-column label="性别" prop="性别" width="45"></el-table-column>
  <el-table-column label="单位" prop="单位" min-width="150"></el-table-column>
</el-table>
<div style="text-align:right;padding-top:4px;">
  <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total"
    :page-sizes="[15,30,50]" layout="total, prev, next" @size-change="doQuery" @current-change="doQuery" small></el-pagination>
</div>
EOF

# person_tree.html
cat >$DIR/person_tree.html <<'EOF'
<div v-for="node in treeData" :key="node.tid">
  <div v-if="node.pid !== '0'" style="padding:3px 4px;cursor:pointer;font-weight:bold;color:#303133;" @click="toggleUnit(node)">
    <span style="font-size:12px;">[[ node.expanded ? '▼' : '▶' ]]</span> [[ node.tname ]]
  </div>
  <template v-if="node.pid !== '0' && node.expanded">
    <div v-for="child in node.children" :key="child.rsid"
         style="padding:3px 4px 3px 24px;cursor:pointer;color:#606266;"
         :style="{ background: currentPerson.rsid == child.rsid ? '#d0e4fc' : '' }"
         @click="selectTreeNode(child)">
      👤 [[ child.tname ]]
    </div>
  </template>
  <div v-if="node.pid === '0'"
       style="padding:3px 4px 3px 8px;cursor:pointer;color:#606266;"
       :style="{ background: currentPerson.rsid == node.rsid ? '#d0e4fc' : '' }"
       @click="selectTreeNode(node)">
    👤 [[ node.tname ]]
  </div>
</div>
<div v-if="treeData.length === 0" style="text-align:center;color:#909399;padding:20px;">加载中...</div>
EOF

# person_basic.html
cat >$DIR/person_basic.html <<'EOF'
<div v-if="detail.rsid">
  <el-descriptions :column="3" border size="small">
    <el-descriptions-item label="姓名">[[ detail.姓名 ]]</el-descriptions-item>
    <el-descriptions-item label="性别">[[ detail.性别 ]]</el-descriptions-item>
    <el-descriptions-item label="民族">[[ detail.民族 ]]</el-descriptions-item>
    <el-descriptions-item label="出生地">[[ detail.出生地 ]]</el-descriptions-item>
    <el-descriptions-item label="籍贯">[[ detail.籍贯 ]]</el-descriptions-item>
    <el-descriptions-item label="人员状态">[[ detail.人员状态 ]]</el-descriptions-item>
    <el-descriptions-item label="出生年月">[[ detail.出生年月 ]]</el-descriptions-item>
    <el-descriptions-item label="年龄">[[ detail.年龄 ]]</el-descriptions-item>
    <el-descriptions-item label="参工时间">[[ detail.参工时间 ]]</el-descriptions-item>
    <el-descriptions-item label="工龄">[[ detail.工龄 ]]</el-descriptions-item>
    <el-descriptions-item label="政治面貌">[[ detail.政治面貌 ]]</el-descriptions-item>
    <el-descriptions-item label="入党时间">[[ detail.入党时间 ]]</el-descriptions-item>
    <el-descriptions-item label="工作单位及职务" :span="3">[[ detail.工作单位及职务 ]]</el-descriptions-item>
    <el-descriptions-item label="任职时间">[[ detail.任职时间 ]]</el-descriptions-item>
    <el-descriptions-item label="领导职务">[[ detail.领导职务 ]]</el-descriptions-item>
    <el-descriptions-item label="是否中层干部">[[ detail.是否中层干部 ]]</el-descriptions-item>
    <el-descriptions-item label="现任职称">[[ detail.现任职称 ]]</el-descriptions-item>
    <el-descriptions-item label="身份证号">[[ detail.身份证号 ]]</el-descriptions-item>
    <el-descriptions-item label="人员身份">[[ detail.人员身份 ]]</el-descriptions-item>
    <el-descriptions-item label="最高学历">[[ detail.最高学历 ]]</el-descriptions-item>
    <el-descriptions-item label="联系电话">[[ detail.联系电话 ]]</el-descriptions-item>
    <el-descriptions-item label="档案编号">[[ detail.档案编号 ]]</el-descriptions-item>
    <el-descriptions-item label="柜号">[[ detail.柜号 ]]</el-descriptions-item>
    <el-descriptions-item label="层号">[[ detail.层号 ]]</el-descriptions-item>
    <el-descriptions-item label="退休时间">[[ detail.退休时间 ]]</el-descriptions-item>
    <el-descriptions-item label="去世时间">[[ detail.去世时间 ]]</el-descriptions-item>
    <el-descriptions-item label="工龄是否间断">[[ detail.工龄是否间断 ]]</el-descriptions-item>
    <el-descriptions-item label="近三年考核" :span="2">[[ detail.近三年考核 ]]</el-descriptions-item>
    <el-descriptions-item label="是否受过处分" :span="3">[[ detail.是否受过处分 ]]</el-descriptions-item>
  </el-descriptions>

  <el-divider content-position="left">全日制教育</el-divider>
  <el-descriptions :column="3" border size="small">
    <el-descriptions-item label="学历">[[ detail.全日制学历 ]]</el-descriptions-item>
    <el-descriptions-item label="学校">[[ detail.全日制学校 ]]</el-descriptions-item>
    <el-descriptions-item label="专业">[[ detail.全日制专业 ]]</el-descriptions-item>
    <el-descriptions-item label="入学时间">[[ detail.全日制入学 ]]</el-descriptions-item>
    <el-descriptions-item label="毕业时间">[[ detail.全日制毕业 ]]</el-descriptions-item>
    <el-descriptions-item label="学位">[[ detail.全日制学位 ]]</el-descriptions-item>
  </el-descriptions>

  <el-divider content-position="left">在职教育</el-divider>
  <el-descriptions :column="3" border size="small">
    <el-descriptions-item label="学历">[[ detail.在职学历 ]]</el-descriptions-item>
    <el-descriptions-item label="学校">[[ detail.在职学校 ]]</el-descriptions-item>
    <el-descriptions-item label="专业">[[ detail.在职专业 ]]</el-descriptions-item>
    <el-descriptions-item label="入学时间">[[ detail.在职入学 ]]</el-descriptions-item>
    <el-descriptions-item label="毕业时间">[[ detail.在职毕业 ]]</el-descriptions-item>
    <el-descriptions-item label="学位">[[ detail.在职学位 ]]</el-descriptions-item>
  </el-descriptions>

  <el-divider content-position="left">档案整理及数字化</el-divider>
  <el-descriptions :column="3" border size="small">
    <el-descriptions-item label="档案整理人">[[ detail.档案整理人 ]]</el-descriptions-item>
    <el-descriptions-item label="数字档案采集人">[[ detail.数字档案采集人 ]]</el-descriptions-item>
    <el-descriptions-item label="档案卷数">[[ detail.档案卷数 ]]</el-descriptions-item>
    <el-descriptions-item label="报送日期">[[ detail.报送日期 ]]</el-descriptions-item>
    <el-descriptions-item label="整理审核人">[[ detail.整理审核人 ]]</el-descriptions-item>
    <el-descriptions-item label="数字档案审核人">[[ detail.数字档案审核人 ]]</el-descriptions-item>
    <el-descriptions-item label="档案报送单位" :span="3">[[ detail.档案报送单位 ]]</el-descriptions-item>
  </el-descriptions>

  <el-divider content-position="left">专项审核情况</el-divider>
  <el-descriptions :column="1" border size="small">
    <el-descriptions-item label="档案存在问题">[[ detail.档案存在问题 ]]</el-descriptions-item>
    <el-descriptions-item label="材料补齐情况">[[ detail.材料补齐情况 ]]</el-descriptions-item>
    <el-descriptions-item label="认定文件内容">[[ detail.认定文件内容 ]]</el-descriptions-item>
  </el-descriptions>
</div>
<div v-else style="text-align:center;color:#909399;margin-top:150px;">请选择人员</div>
EOF

# 其余8个占位标签
for f in person_salary person_position person_audit person_identify person_preaudit person_cadre person_directory person_supplement person_family; do
  echo "$PLACEHOLDER" >$DIR/${f}.html
done

echo "所有模板创建完成"
ls -la $DIR/
