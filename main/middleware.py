from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

class LoginJumpMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # 补全括号 + 补全and，彻底修复语法错误
        if (
            request.path != "/login/"
            and not request.user.is_authenticated
            and response.status_code == 302
            and "/login/" in response.get("Location", "")
        ):
            # 单行字符串，完全消除IDE警告，HTTPS+iframe专用跳转
            jump_script = "<script>document.domain = document.domain; top.location.replace('/login/');</script>"
            return HttpResponse(jump_script, content_type="text/html; charset=utf-8")
        return response
