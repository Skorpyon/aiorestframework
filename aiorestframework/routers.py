from aiohttp.web_urldispatcher import UrlDispatcher

from .views import GenericViewSet


__all__ = (
    'APIUrlDispatcher'
)


class APIUrlDispatcher(UrlDispatcher):

    def register_viewset(self, path: str, viewset: GenericViewSet,
                         base_name: str='', detail_postfix: str='') -> None:
        viewset.register_resources(self, path, base_name, detail_postfix)
