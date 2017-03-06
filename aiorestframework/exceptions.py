from typing import Iterable, Dict

import ujson
from aiohttp import errors

from aiorestframework import status


__all__ = (
    'SkipField', 'APIError', 'MethodNotAllowed', 'ValidationError'
)


class SkipField(Exception):
    pass


class APIError(errors.HttpProcessingError):
    """Basic API Error"""

    default_http_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'A server error occurred.'
    default_api_code = 'error'
    default_headers = None

    def __init__(self, *, detail=None, api_code=None, code=None, headers=None):
        self.detail = self.get_detail(detail=detail)
        self.api_code = self.default_api_code if api_code is None else api_code

        if code is None:
            code = self.default_http_code
        if headers is None:
            headers = self.default_headers

        message = self.get_message()
        super().__init__(code=code, message=message, headers=headers)

    def get_detail(self, *, detail, **kwargs):
        if detail is not None:
            return detail
        else:
            return self.default_detail

    def get_message(self):
        if isinstance(self.detail, (list, dict, set)):
            return self.detail
        else:
            return {
                'detail': self.detail,
                'code': self.api_code
            }


class MethodNotAllowed(APIError):
    """Method not allowed error"""

    default_http_code = status.HTTP_405_METHOD_NOT_ALLOWED
    default_detail = 'Method "{method}" not allowed.'
    default_api_code = 'method_not_allowed'

    def __init__(self, method, allowed_methods, detail=None, api_code=None,
                 code=None, headers=None):
        self.detail = self.get_detail(detail, method=method)
        if headers is None or isinstance(headers, dict)\
                and 'Allow' not in headers:
            allow = {'Allow': ','.join(sorted(allowed_methods.upper()))}
            if headers is None:
                headers = allow
            else:
                headers.update(allow)

        super().__init__(detail=detail, api_code=api_code, code=code,
                         headers=headers)

    def get_detail(self, detail, method, **kwargs):
        if detail is not None:
            return detail
        else:
            return self.default_detail.format(method=method.upper())


class ValidationError(APIError):
    """ Validation Error"""

    default_http_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Bad request."
    default_api_code = 'invalid'
