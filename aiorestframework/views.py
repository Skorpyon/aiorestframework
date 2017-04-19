
from .generics import GenericViewSet


__all__ = (
    'BaseViewSet', 'ListMixin', 'CreateMixin', 'RetrieveMixin',
    'UpdateMixin', 'PartialUpdateMixin', 'DestroyMixin'
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


class BaseViewSet(GenericViewSet):
    bindings = BASE_BINDINGS


class ListMixin:
    async def list(self, request):
        raise NotImplementedError('"list" handler should be override.')


class CreateMixin:
    async def create(self, request):
        raise NotImplementedError('"create" handler should be override.')


class RetrieveMixin(object):
    async def retrieve(self, request):
        raise NotImplementedError('"retrieve" handler should be override.')


class UpdateMixin:
    async def update(self, request):
        raise NotImplementedError('"update" handler should be override.')


class PartialUpdateMixin:
    async def partial_update(self, request):
        raise NotImplementedError('"partial_update" handler should be override.')


class DestroyMixin:
    async def destroy(self, request):
        raise NotImplementedError('"destroy" handler should be override.')