from django.http import HttpResponseForbidden
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return HttpResponseForbidden("Vous n'avez pas les droits d'accès nécessaires pour accéder à cette page.")

        return view_func(request, *args, **kwargs)

    return _wrapped_view