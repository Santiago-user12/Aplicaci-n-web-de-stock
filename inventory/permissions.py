from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from .models import UserProfile

def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied
            try:
                role = request.user.profile.role
            except UserProfile.DoesNotExist:
                role = 'viewer'
            if request.user.is_superuser or role in allowed_roles:
                return view(request, *args, **kwargs)
            return render(request, '403.html', status=403, context={'allowed_roles': allowed_roles})
        return wrapped
    return decorator
