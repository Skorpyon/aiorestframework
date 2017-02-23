from typing import Iterable, Dict

from aiohttp import errors

from aiorestframework import status


__all__ = (
    'APIError', 'MethodNotAllowed'
)


class APIError(errors.HttpProcessingError):
    """Basic API Error"""

    default_http_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'A server error occurred.'
    default_api_code = 'error'
    default_headers = None

    def __init__(self, *, detail=None, code: int=None, headers=None):
        if code is None:
            code = self.default_http_code
        if not detail:
            detail = self.get_detail()
        if headers is None:
            headers = self.default_headers

        super().__init__(code=code, message=detail, headers=headers)

    def get_detail(self, *args, **kwargs) -> Dict:
        return {
            'detail': self.default_detail,
            'code': self.default_api_code
        }


class MethodNotAllowed(APIError):
    """Method not allowed error"""

    default_http_code = status.HTTP_405_METHOD_NOT_ALLOWED
    default_detail = 'Method "{method}" not allowed.'
    default_code = 'method_not_allowed'

    def __init__(self, method, allowed_methods, detail=None, code: int=None, headers=None):
        if detail is None:
            detail = self.get_detail(method=method)
        if headers is None or isinstance(headers, dict) and 'Allow' not in headers:
            allow = {'Allow': ','.join(sorted(allowed_methods.upper()))}
            if headers is None:
                headers = allow
            else:
                headers.update(allow)

        super().__init__(detail=detail, code=code, headers=headers)

    def get_detail(self, method: str) -> Dict:
        return {
            'detail': self.default_detail.format(method=method.upper()),
            'code': self.default_api_code
        }
