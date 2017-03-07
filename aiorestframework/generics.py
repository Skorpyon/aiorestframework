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

    def _get_detail_name(self, name, detail_name):
        if not detail_name:
            if self.detail_name:
                detail_name = self.detail_name
            else:
                detail_name = self._get_resource_name_with_postfix(name)
        return detail_name

    def _get_detail_postfix(self, postfix=''):
        if not postfix:
            if self.detail_postfix is None:
                raise RuntimeError(
                    'View %s have no detail_postfix.' % str(self.__class__))
            else:
                postfix = self.detail_postfix
        return postfix

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

    def _get_resource_name_with_postfix(self, name='', postfix=''):
        name = self._get_resource_name(name=name)
        postfix = self._get_detail_postfix(postfix)
        name = '.'.join((name, postfix))
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
        for action, declared_methods in branch.items():
            handler = getattr(self, action, None)
            if handler is not None:
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
        branch = self.bindings.get('list', None)
        if branch:
            list_name = self._get_resource_name(name)
            list_resource = dispatcher.add_resource(path, name=list_name)
            self._build_resource_routes(list_resource, branch)

        # Register detail resource
        branch = self.bindings.get('detail', None)
        if branch:
            detail_name = self._get_detail_name(name, detail_name)
            url = '/'.join((path, self.lookup_url_kwarg.lstrip('/')))
            detail_resource = dispatcher.add_resource(url, name=detail_name)
            self._build_resource_routes(detail_resource, branch)

        # Register custom resources
        custom = self.bindings.get('custom', None)
        if custom:
            # Register custom list resources
            custom_list = custom.get('list', None)
            if custom_list:
                for action, methods in custom_list.items():
                    list_name = self._get_resource_name_with_postfix(name, action)
                    url = '/'.join((path, action))
                    list_resource = dispatcher.add_resource(url, name=list_name)
                    branch = {action: methods}
                    self._build_resource_routes(list_resource, branch)
            # Register custom detail resources
            custom_detail = custom.get('detail', None)
            if custom_detail:
                for action, methods in custom_detail.items():
                    detail_name = self._get_detail_name(name, detail_name)
                    detail_name = self._get_resource_name_with_postfix(
                        name=detail_name, postfix=action)
                    url = '/'.join((path, self.lookup_url_kwarg.lstrip('/')), action)
                    detail_resource = dispatcher.add_resource(url, name=detail_name)
                    branch = {action: methods}
                    self._build_resource_routes(detail_resource, branch)