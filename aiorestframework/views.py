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
    name: str = ''
    detail_name: str = ''
    detail_postfix: str = 'detail'
    lookup_url_kwarg: str = '{id}'

    def _get_resource_name(self, name: str= '') -> str:
        if not name:
            if not self.name:
                raise RuntimeError('View %s have no name.' % str(self.__class__))
            else:
                name = self.name
        return name

    def _get_resource_name_with_postfix(self, name: str= '', name_postfix: str= '') -> str:
        if name is None:
            name = self._get_resource_name()
        if name_postfix is None:
            if self.detail_postfix is None:
                raise RuntimeError('View %s have no detail_postfix.' % str(self.__class__))
            else:
                name_postfix = self.detail_postfix
        name = '_'.join((name, name_postfix))
        return name

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
                           name: str= '', detail_name: str= '') -> None:
        assert isinstance(dispatcher, UrlDispatcher)

        # Register list resource
        if 'list' in self.bindings and self.bindings['list']:
            list_name = self._get_resource_name(name)
            list_resource = dispatcher.add_resource(path, name=list_name)
            self._build_resource_routes(list_resource, 'list')

        # Register detail resource
        if 'detail' in self.bindings and self.bindings['detail']:
            if not detail_name:
                if self.detail_name:
                    detail_name = self.detail_name
                else:
                    detail_name = self._get_resource_name_with_postfix(name)
            url = '/'.join((path, self.lookup_url_kwarg.lstrip('/')))
            detail_resource = dispatcher.add_resource(url, name=detail_name)
            self._build_resource_routes(detail_resource, 'detail')
