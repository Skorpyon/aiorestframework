from functools import wraps

from aiohttp.hdrs import METH_GET, METH_HEAD, METH_OPTIONS

__all__ = (
    'SAFE_METHODS', 'BasePermission', 'AllowAny'
)


SAFE_METHODS = (METH_GET, METH_HEAD, METH_OPTIONS)


def set_permissions(permissions, include_viewset_permissions=False):
    """
    Add permissions classes to handler

    :param func: handler function
    :param permissions: List of permission classes
    :param include_viewset_permissions: Include parent ViewSet permission_classes
    :return: wrapped handler with .permission_classes attribute
    """
    def wrapper(handler):
        assert isinstance(permissions, (tuple, list, set)),\
            'Permissions should be a iterable of Permissions.'
        _permission_classes = []
        for permission in permissions:
            assert issubclass(permission, BasePermission), \
                'Permission class should be inherited from "BasePermission".'
            _permission_classes.append(permission)

        # Bind permission_classes to function
        handler.permission_classes = _permission_classes
        handler.include_viewset_permissions = include_viewset_permissions

        return handler

    return wrapper


class BasePermission(object):
    """
    A base class from which all permission classes should inherit.
    """

    async def check_permission(self, request, handler, view):
        """
        Check permission for request.
        After check detail permission if handler has attr `is_detail_action`.
        """
        has_permission = await self.has_permission(request, handler, view)
        if not has_permission:
            return False
        if getattr(handler, 'is_detail_action', False):
            has_object_permission = await self.has_object_permission(
                request, handler, view)
            return has_object_permission
        else:
            return True

    async def has_permission(self, request, handler, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return True

    async def has_object_permission(self, request, handler, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return True


class AllowAny(BasePermission):
    """
    Allow any access.
    This isn't strictly required, since you could use an empty
    permission_classes list, but it's useful because it makes the intention
    more explicit.
    """

    async def has_permission(self, request, handler, view):
        return True