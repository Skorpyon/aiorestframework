from .generics import AbstractGenericViewSet


__all__ = (

)

L_BINDINGS = {
    'list': {
        'list': 'get'
    }
}

C_BINDINGS = {
    'list': {

    }
}


class GenericViewSet(AbstractGenericViewSet):
    bindings: dict = {}


class ListViewSet(object):
    pass