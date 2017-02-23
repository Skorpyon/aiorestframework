from aiohttp import hdrs
from aiohttp.web_urldispatcher import UrlDispatcher, Resource

from .exceptions import *


__all__ = (
    'AbstractGenericViewSet',
)


class AbstractGenericViewSet:

    bindings: dict = {
        'list': {
            'get': 'list',
            'post': 'create',
            'delete': 'destroy_all'
        },
        'detail': {
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        },
        'custom': {}
    }
    base_name: str = ''
    base_detail_name: str = 'detail'
    lookup_url_kwarg: str = '{id}'

    def _get_resource_name(self, base_name: str=None) -> str:
        if base_name is None:
            if self.base_name is None:
                raise RuntimeError('View %s have no base_name.' % str(self.__class__))
            else:
                base_name = self.base_name
        return base_name

    def _get_resource_name_with_postfix(self, base_name: str='', name_postfix: str='') -> str:
        if base_name is None:
            base_name = self._get_resource_name()
        if name_postfix is None:
            if self.base_detail_name is None:
                raise RuntimeError('View %s have no base_detail_name.' % str(self.__class__))
            else:
                name_postfix = self.base_detail_name
        base_name = '_'.join((base_name, name_postfix))
        return base_name

    def _build_resource_routes(self, resource, branch: str) -> Resource:
        if branch not in self.bindings:
            raise NotImplementedError('%s views not implemented in %s' % (branch, self.__class__))
        for m in hdrs.METH_ALL:
            m = m.lower()
            if m in self.bindings[branch]:
                handler = getattr(self, self.bindings[branch][m], None)
                if handler is not None and callable(handler):
                    resource.add_route(m, handler)
        return resource

    def register_resources(self, dispatcher: UrlDispatcher, path: str,
                           base_name: str=None, detail_postfix: str=None) -> None:
        assert isinstance(dispatcher, UrlDispatcher)

        # Register list resource
        if 'list' in self.bindings and self.bindings['list']:
            name = self._get_resource_name(base_name)
            list_resource = dispatcher.add_resource(path, name=name)
            self._build_resource_routes(list_resource, 'list')

        # Register detail resource
        if 'detail' in self.bindings and self.bindings['detail']:
            name = self._get_resource_name_with_postfix(base_name, detail_postfix)
            url = '/'.join((path, self.lookup_url_kwarg))
            detail_resource = dispatcher.add_resource(url, name=name)
            self._build_resource_routes(detail_resource, 'detail')
