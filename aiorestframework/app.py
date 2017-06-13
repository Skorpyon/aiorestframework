from aiohttp.web import Application
from aiohttp.log import web_logger

from .routers import APIUrlDispatcher


__all__ = (
    'APIApplication',
)


class APIApplication(Application):
    def __init__(self, *, name='', logger=web_logger, router=None,
                 middlewares=(), handler_args=None, client_max_size=1024**2,
                 loop=None, debug=...):
        self.name = name
        if router is None:
            router = APIUrlDispatcher()
        assert isinstance(router, APIUrlDispatcher), router
        setattr(router, 'app_name', name)
        super().__init__(
            logger=logger, router=router, middlewares=middlewares,
            handler_args=handler_args, client_max_size=client_max_size,
            loop=loop, debug=debug)
