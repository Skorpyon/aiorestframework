from aiohttp.web import Application
from aiohttp.log import web_logger

from .routers import APIUrlDispatcher


__all__ = (
    'APIApplication',
)


class APIApplication(Application):
    def __init__(self, *, logger=web_logger, loop=None, router: APIUrlDispatcher=None,
                 middlewares=(), debug=...):
        if router is None:
            router = APIUrlDispatcher()
        assert isinstance(router, APIUrlDispatcher), router
        super().__init__(
            logger=logger, loop=loop, router=router, middlewares=middlewares, debug=debug)
