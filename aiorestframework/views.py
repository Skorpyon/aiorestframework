from aiohttp import Response

from .generics import AbstractGenericViewSet


__all__ = (
    'GenericViewSet', 'ListMixin', 'CreateMixin', 'RetrieveMixin',
    'UpdateMixin', 'PartialUpdateMixin', 'DestroyMixin'
)


class GenericViewSet(AbstractGenericViewSet):
    pass


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