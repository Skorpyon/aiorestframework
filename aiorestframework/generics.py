import functools

from aiohttp import hdrs
from aiohttp.web import Application
from aiohttp.web_urldispatcher import UrlDispatcher, Resource

from .exceptions import *


__all__ = (
    'AbstractGenericViewSet',
)

BASE_BINDINGS = {
    'list': {
        'list': 'get',
        'create': 'post',
        'destroy_all': 'delete'
    },
    'detail': {
        'retrieve': 'get',
        'update': 'put',
        'partial': 'put',
        'partial_update': 'patch',
        'destroy': 'delete'
    },
    'custom': {}
}


class AbstractGenericViewSet:

    bindings = BASE_BINDINGS
    bindings_update = {}
    app_name = ''
    name = ''
    detail_name = ''
    detail_postfix = 'detail'
    lookup_url_kwarg = '{id}'

    def __init__(self):
        if self.bindings_update:
            assert isinstance(self.bindings_update, dict)
            self.bindings.update(self.bindings_update)

    def _get_wrapped_handler(self, func, action):
        @functools.wraps(func)
        async def wrapper(request):
            request['rest'] = {}
            request['rest']['action'] = action
            result = await func(request)
            return result
        return wrapper

    def _get_resource_name(self, name=''):
        if not name:
            if not self.name:
                raise RuntimeError(
                    'View %s have no name.' % str(self.__class__))
            else:
                name = self.name
        if self.app_name:
            name = '.'.join((self.app_name, name))
        return name

    def _get_resource_name_with_postfix(self, name='', name_postfix=''):
        name = self._get_resource_name(name=name)
        if not name_postfix:
            if self.detail_postfix is None:
                raise RuntimeError(
                    'View %s have no detail_postfix.' % str(self.__class__))
            else:
                name_postfix = self.detail_postfix
        name = '.'.join((name, name_postfix))
        return name

    def _build_methods_list(self, declared):
        if isinstance(declared, str):
            declared = declared.upper()
            methods = [declared, ] if declared in hdrs.METH_ALL else []
        elif isinstance(declared, list):
            methods = [m.upper() for m in declared if m.upper() in hdrs.METH_ALL]
        else:
            raise ValueError(
                'Methods should be a str or list, got {} instead.'.format(
                    declared.__type__()))

        return methods

    def _build_resource_routes(self, resource, branch):
        if branch not in self.bindings:
            raise NotImplementedError(
                '%s views not implemented in %s' % (branch, self.__class__))
        for action in self.bindings[branch]:
            handler = getattr(self, action, None)
            if handler is not None:
                declared_methods = self.bindings[branch][action]
                methods = self._build_methods_list(declared_methods)
                for m in methods:
                    wrapped_handler = self._get_wrapped_handler(handler, action)
                    resource.add_route(m, wrapped_handler)

        return resource

    def register_resources(self, dispatcher, path, name='', detail_name=''):
        assert isinstance(dispatcher, UrlDispatcher)

        # Save Application name
        if hasattr(dispatcher, 'app_name') and dispatcher.app_name:
            self.app_name = dispatcher.app_name

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