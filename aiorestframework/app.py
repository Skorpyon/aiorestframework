from aiohttp.web import Application
from aiohttp.log import web_logger

from .routers import APIUrlDispatcher


__all__ = (
    'APIApplication',
)


class APIApplication(Application):
    def __init__(self, *, name='', logger=web_logger, loop=None,
                 router=None, middlewares=(), debug=...):
        self.name = name
        if router is None:
            router = APIUrlDispatcher()
        assert isinstance(router, APIUrlDispatcher), router
        setattr(router, 'app_name', name)
        super().__init__(logger=logger, loop=loop, router=router,
                         middlewares=middlewares, debug=debug)
