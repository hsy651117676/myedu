import xlrd
from xlutils.copy import copy
from io import BytesIO

template_path = '/home/hsy/myedu/static/excel_templates/9_1_1.xls'
rb = xlrd.open_workbook(template_path, formatting_info=True)
wb = copy(rb)
ws = wb.get_sheet(0)

output = BytesIO()
wb.save(output)

with open('/tmp/test_copy.xls', 'wb') as f:
    f.write(output.getvalue())

print("文件保存到 /tmp/test_copy.xls")
