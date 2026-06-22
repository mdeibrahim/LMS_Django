from django.conf import settings
from django.http import HttpResponse


def _origin_allowed(origin):
    allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
    return origin in allowed_origins


class SimpleCorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get('Origin')

        if request.method == 'OPTIONS' and origin and _origin_allowed(origin):
            response = HttpResponse(status=200)
            return self._add_cors_headers(request, response)

        response = self.get_response(request)
        return self._add_cors_headers(request, response)

    def _add_cors_headers(self, request, response):
        origin = request.headers.get('Origin')
        if not origin or not _origin_allowed(origin):
            return response

        response['Access-Control-Allow-Origin'] = origin
        response['Vary'] = self._append_vary(response.get('Vary', ''), 'Origin')
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = (
            request.headers.get('Access-Control-Request-Headers')
            or 'Authorization, Content-Type, X-Requested-With, Accept, Origin'
        )
        response['Access-Control-Max-Age'] = '86400'

        if getattr(settings, 'CORS_ALLOW_CREDENTIALS', False):
            response['Access-Control-Allow-Credentials'] = 'true'

        return response

    @staticmethod
    def _append_vary(existing, value):
        values = [part.strip() for part in existing.split(',') if part.strip()]
        if value not in values:
            values.append(value)
        return ', '.join(values)
