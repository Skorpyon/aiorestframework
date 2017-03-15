import ujson as json
from aiohttp.web import Response as AiohttpResponse


class Response(AiohttpResponse):
    """
    Response class passed application/json content_type as default
    """

    def __init__(self, *, data=None, status=200, body=None,
                 reason=None, text=None, headers=None, content_type=None,
                 charset=None):
        content_type = 'application/json' if content_type is None else content_type
        text = json.dumps(data) if (data and not body and not text) else text
        super().__init__(body=body, status=status, reason=reason, text=text,
                         headers=headers, content_type=content_type,
                         charset=charset)
