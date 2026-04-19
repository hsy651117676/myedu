from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse

def login_required_top(view_func):
    @login_required(login_url='/login/')
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            next_url = request.build_absolute_uri()
            login_url = f"{reverse('login')}?next={next_url}"
            return HttpResponseRedirect(login_url)
        return wrapper(request, *args, **kwargs)
    return wrapped_view
