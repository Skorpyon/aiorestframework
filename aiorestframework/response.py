import ujson as json
from aiohttp.web import Response as AiohttpResponse


class Response(AiohttpResponse):
    """
    Response class passed application/json content_type as default
    """

    def __init__(self, *, data=None, status=200, body=None,
                 reason=None, text=None, headers=None, content_type=None,
                 charset=None):
        if content_type is None and data is not None:
            content_type = 'application/json'
        if data is not None and not body and not text:
            text = json.dumps(data)
        else:
            text = text

        super().__init__(body=body, status=status, reason=reason, text=text,
                         headers=headers, content_type=content_type,
                         charset=charset)
