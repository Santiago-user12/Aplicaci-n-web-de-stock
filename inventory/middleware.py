from django.utils.translation import activate

class UserLanguageMiddleware:
    """Activate each authenticated user's saved UI language."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = request.session.get('django_language', 'es')
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            language = request.user.profile.language
        language = language if language in {'es', 'en'} else 'es'
        request.LANGUAGE_CODE = language
        activate(language)
        response = self.get_response(request)
        response.headers['Content-Language'] = language
        return response
