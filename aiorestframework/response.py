from aiohttp.web import Response as AiohttpResponse


class Response(AiohttpResponse):
    """
    Response class passed application/json content_type as default
    """

    def __init__(self, *, body=None, status=200,
                 reason=None, text=None, headers=None, content_type=None,
                 charset=None):
        content_type = 'application/json' if content_type is None else content_type
        super().__init__(body=body, status=status, reason=reason, text=text,
                         headers=headers, content_type=content_type,
                         charset=charset)
