from aiohttp.web_urldispatcher import UrlDispatcher

from .views import AbstractGenericViewSet


__all__ = (
    'APIUrlDispatcher'
)


class APIUrlDispatcher(UrlDispatcher):

    def register_viewset(self, path: str, viewset: AbstractGenericViewSet,
                         base_name: str='', detail_postfix: str='') -> None:
        viewset.register_resources(self, path, base_name, detail_postfix)
