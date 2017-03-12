from functools import wraps

from aiohttp import hdrs
from aiohttp.web import Application
from aiohttp.web_urldispatcher import UrlDispatcher, Resource

from aiorestframework import exceptions
from aiorestframework.permissions import BasePermission
from aiorestframework.settings import api_settings


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
    app_name = ''
    name = ''
    detail_name = ''
    detail_postfix = 'detail'
    lookup_url_kwarg = '{id}'
    permission_classes = []

    def __init__(self):
        if hasattr(self, 'bindings_update'):
            # Update methods bindings if ViewSet have it.
            assert isinstance(self.bindings_update, dict)
            self.bindings.update(self.bindings_update)
        # Build permissions list
        self._permission_classes = []
        for permission in self.permission_classes:
            assert issubclass(permission, BasePermission), \
                'Permission class should be inherited from "BasePermission".'
            self._permission_classes.append(permission)

    def _get_handler(self, handler, action,
                     is_list_action=False, is_detail_action=False):
        """
        Return wrapped handler for given ViewSet action.

        :param handler: ViewSet handler, that proceed given action.
        :param action: Action string name.
        :return: Wrapped handler.
        """
        # Bind action types to handler
        handler.__dict__['is_list_action'] = is_list_action
        handler.__dict__['is_detail_action'] = is_detail_action

        @wraps(handler)
        async def wrapper(request):
            # Bind action name to request
            setattr(request, 'action', action)
            result = await handler(request)
            return result
        return wrapper

    # -----------
    # Permissions
    def _check_permissions_wrapper(self, handler):
        """
        Check if the request should be permitted.
        Raises an appropriate exception if the request is not permitted.
        """
        @wraps(handler)
        async def wrapper(request):
            if hasattr(handler, 'permissions'):
                for permission in handler.permissions:
                    # Check permission
                    has_permission = await permission.check_permission(
                        request, handler, self)
                    if not has_permission:
                        await self.permission_denied(
                            request, message=getattr(permission, 'message', None))
            result = await handler(request)
            return result
        return wrapper

    async def permission_denied(self, request, message):
        raise exceptions.PermissionDenied(detail=message)

    def set_handler_permissions(self, handler):
        """
        Instantiates and returns the list of permissions that this handler requires.
        """
        if hasattr(handler, 'permission_classes'):
            permission_classes = handler.permission_classes
            if handler.include_viewset_permissions is True:
                permission_classes += self._permission_classes
        else:
            permission_classes = self._permission_classes

        permissions = [permission() for permission in permission_classes]
        handler.permissions = permissions

        return handler

    # --------------------------
    # Resources names generation

    def _get_detail_name(self, name, detail_name):
        """
        Method build name for detail handlers based on ViewSet attributes,
        that may be override by passed attrs. If arguments is None, method
        use default values from ViewSet instance attrs.

        :param name: base name (eg "users").
        :param detail_name: detail name, default is "detail".
        :return: Detail resource name (eg "users.detail").
        """
        if not detail_name:
            if self.detail_name:
                detail_name = self.detail_name
            else:
                detail_name = self._get_resource_name_with_postfix(name)
        return detail_name

    def _get_detail_postfix(self, postfix=''):
        """
        Method return passed postfix or, if postfix not passed, return
        default postfix from ViewSet instance. Used for build detail or custom
        names or resources (eg "users.detail", "users.register").

        :param postfix: None or custom postfix.
        :return: Passed postfix or default ViewSet postfix (eg "detail", "register")
        """
        if not postfix:
            if self.detail_postfix is None:
                raise RuntimeError(
                    'View %s have no detail_postfix.' % str(self.__class__))
            else:
                postfix = self.detail_postfix
        return postfix

    def _get_resource_name(self, name=''):
        """
        Build "List's" resources name, based on passed name or default
        ViewSet name (eg "users").

        :param name: Resource name. Use ViewSet.name if not passed.
        :return: string name of resource.
        """
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
        """
        Build "Detail's" resource name, based on passed or default name
        and postfix (eg "users.detail" for `/users/{id}` url,
                        "cars.clean" for `/cars/{id}/clean` url).

        :param name: name of resource or None or ''
        :param postfix: name postfix or None or ''
        :return: resource name with postfix (eg "users.detail", "cars.clean").
        """
        name = self._get_resource_name(name=name)
        postfix = self._get_detail_postfix(postfix)
        name = '.'.join((name, postfix))
        return name

    def _build_methods_list(self, declared):
        """
        Build methods list for declared handlers (eg ["GET", "PUT", "PATCH"]).
        Used for check typos in methods declaration.

        :param declared: string method or methods list.
        :return: List of validated methods in uppercase (eg ["GET", "PATCH"]).
        """
        invalid_http = 'Method {method} is not valid HTTP method.'
        methods = []

        def fail(message):
            raise ValueError(message)

        if isinstance(declared, str):
            declared = declared.upper()
            if declared in hdrs.METH_ALL:
                methods.append(declared)
            else:
                fail(invalid_http.format(method=declared))
        elif isinstance(declared, list):
            for m in declared:
                m = m.upper()
                if m in hdrs.METH_ALL:
                    methods.append(m)
                else:
                    fail(invalid_http.format(method=m))
        else:
            raise ValueError(
                'Methods should be a str or list, got {type} instead.'.format(
                    type=declared.__type__()))

        return methods

    def _build_resource_routes(self, resource, branch,
                               is_list_action=False, is_detail_action=False):
        """
        Add routes with wrapped handlers to aiohttp.Resource

        :param resource: Resource instance.
        :param branch: Dict with handlers names and declared methods.
         eg {'create': ["POST", ], "retrieve": ["GET", ], "update": ["PUT", ]}
        :return: aiohttp.Resource with Routes.
        """
        assert isinstance(branch, dict), "Branch of methods should be a dict."
        for action, declared_methods in branch.items():
            handler = getattr(self, action, None)
            if handler is not None:
                methods = self._build_methods_list(declared_methods)
                for m in methods:
                    wrapped_handler = self._get_handler(
                        handler, action, is_list_action, is_detail_action)

                    # Add permissions to handler if permissions check enabled
                    if api_settings.ENABLE_PERMISSIONS_CHECK:
                        self.set_handler_permissions(wrapped_handler)
                        wrapped_handler = self._check_permissions_wrapper(
                            wrapped_handler)

                    resource.add_route(m, wrapped_handler)

        return resource

    # -----------------------------
    # Bind Resources to Application
    def register_resources(self, dispatcher, path, name='', detail_name=''):
        """
        Main method for create all aiohttp.Resource based on declared handlers
        and methods of ViewSet and bind it to aiohttp.Dispatcher with Routes

        :param dispatcher: app.router.dispatcher
        :param path: base path of ViewSet (eg "/auth", "/users").
        :param name: possible override of ViewSet.name default value.
        :param detail_name: possible override of ViewSet.detail_name value.
        :return: None, just bind Resources to passed Dispatcher
        """
        assert isinstance(dispatcher, UrlDispatcher)

        # Save Application name
        if hasattr(dispatcher, 'app_name') and dispatcher.app_name:
            self.app_name = dispatcher.app_name

        # Register list resource
        branch = self.bindings.get('list', None)
        if branch:
            list_name = self._get_resource_name(name)
            list_resource = dispatcher.add_resource(path, name=list_name)
            self._build_resource_routes(
                list_resource, branch, is_list_action=True)

        # Register detail resource
        branch = self.bindings.get('detail', None)
        if branch:
            detail_name = self._get_detail_name(name, detail_name)
            url = '/'.join((path, self.lookup_url_kwarg.lstrip('/')))
            detail_resource = dispatcher.add_resource(url, name=detail_name)
            self._build_resource_routes(
                detail_resource, branch, is_detail_action=True)

        # Register custom resources
        custom = self.bindings.get('custom', None)
        if custom:
            assert isinstance(custom, dict)
            # Register custom list resources
            custom_list = custom.get('list', None)
            if custom_list:
                assert isinstance(custom_list, dict)
                for action, methods in custom_list.items():
                    list_name = self._get_resource_name_with_postfix(name, action)
                    url = '/'.join((path, action))
                    list_resource = dispatcher.add_resource(url, name=list_name)
                    branch = {action: methods}
                    self._build_resource_routes(
                        list_resource, branch, is_list_action=True)
            # Register custom detail resources
            custom_detail = custom.get('detail', None)
            if custom_detail:
                assert isinstance(custom_detail, dict)
                for action, methods in custom_detail.items():
                    detail_name = self._get_detail_name(name, detail_name)
                    detail_name = self._get_resource_name_with_postfix(
                        name=detail_name, postfix=action)
                    url = '/'.join((path, self.lookup_url_kwarg.lstrip('/')), action)
                    detail_resource = dispatcher.add_resource(url, name=detail_name)
                    branch = {action: methods}
                    self._build_resource_routes\
                        (detail_resource, branch, is_detail_action=True)
