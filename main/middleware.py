from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)


class LoginJumpMiddleware(MiddlewareMixin):
    """处理iframe环境下的登录跳转"""
    
    # 不需要检查的路径
    EXCLUDED_PATHS = ['/login/', '/register/', '/forgot-pwd/', '/captcha/']
    
    def __init__(self, get_response):
        super().__init__(get_response)
        # 使用reverse避免硬编码URL
        self.login_url = reverse('login')
    
    def process_response(self, request, response):
        # 跳过不需要处理的路径
        if request.path in self.EXCLUDED_PATHS:
            return response
        
        # 检查是否需要iframe跳转
        if self._should_redirect_to_login(request, response):
            logger.info(f"为用户 {request.user} 执行iframe登录跳转")
            return self._create_iframe_redirect()
        
        return response
    
    def _should_redirect_to_login(self, request, response):
        result = (
            not request.user.is_authenticated
            and response.status_code == 302
            and response.get("Location", "").startswith(self.login_url)
        )
        logger.info(f"should_redirect: user_authenticated={request.user.is_authenticated}, "
                    f"status={response.status_code}, location={response.get('Location','')}, "
                    f"result={result}, path={request.path}")
        return result
    def _create_iframe_redirect(self):
        """创建iframe环境下的跳转响应"""
        html_content = (
            '<!DOCTYPE html>'
            '<html>'
            '<head><meta charset="utf-8"></head>'
            '<body>'
            '<script>'
            'if (window.top !== window.self) {'
            '    window.top.location.href = "' + self.login_url + '";'
            '} else {'
            '    window.location.href = "' + self.login_url + '";'
            '}'
            '</script>'
            '</body>'
            '</html>'
        )
        return HttpResponse(html_content, content_type="text/html; charset=utf-8")
