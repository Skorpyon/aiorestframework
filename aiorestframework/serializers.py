import copy
import inspect
import traceback
from collections import Mapping, OrderedDict

from aiorestframework.utils import html, representation
from aiorestframework.utils.functional import cached_property
from .exceptions import SkipField, ValidationError

from .fields import *

from .serializer_helpers import (
    BindingDict, BoundField, NestedBoundField, ReturnDict, ReturnList
)


# We assume that 'validators' are intended for the child serializer,
# rather than the parent serializer.
LIST_SERIALIZER_KWARGS = (
    'read_only', 'write_only', 'required', 'default', 'initial', 'source',
    'label', 'help_text', 'style', 'error_messages', 'allow_empty',
    'instance', 'data', 'partial', 'context', 'allow_null'
)

ALL_FIELDS = '__all__'

NON_FIELD_ERRORS_KEY = 'non_field_errors'  # TODO Move to settings


# BaseSerializer
class BaseSerializer(Field):
    """
    The BaseSerializer class provides a minimal class which may be used
    for writing custom serializer implementations.

    Note that we strongly restrict the ordering of operations/properties
    that may be used on the serializer in order to enforce correct usage.

    In particular, if a `data=` argument is passed then:

    .is_valid() - Available.
    .initial_data - Available.
    .validated_data - Only available after calling `is_valid()`
    .errors - Only available after calling `is_valid()`
    .data - Only available after calling `is_valid()`

    If a `data=` argument is not passed then:

    .is_valid() - Not available.
    .initial_data - Not available.
    .validated_data - Not available.
    .errors - Not available.
    .data - Available.
    """

    def __init__(self, instance=None, data=empty, **kwargs):
        self.instance = instance
        if data is not empty:
            self.initial_data = data
        self.partial = kwargs.pop('partial', False)
        self._context = kwargs.pop('context', {})
        kwargs.pop('many', None)
        super(BaseSerializer, self).__init__(**kwargs)

    def __new__(cls, *args, **kwargs):
        # We override this method in order to automagically create
        # `ListSerializer` classes instead when `many=True` is set.
        if kwargs.pop('many', False):
            return cls.many_init(*args, **kwargs)
        return super(BaseSerializer, cls).__new__(cls, *args, **kwargs)

    @classmethod
    def many_init(cls, *args, **kwargs):
        """
        This method implements the creation of a `ListSerializer` parent
        class when `many=True` is used. You can customize it if you need to
        control which keyword arguments are passed to the parent, and
        which are passed to the child.

        Note that we're over-cautious in passing most arguments to both parent
        and child classes in order to try to cover the general case. If you're
        overriding this method you'll probably want something much simpler, eg:

        @classmethod
        def many_init(cls, *args, **kwargs):
            kwargs['child'] = cls()
            return CustomListSerializer(*args, **kwargs)
        """
        allow_empty = kwargs.pop('allow_empty', None)
        child_serializer = cls(*args, **kwargs)
        list_kwargs = {
            'child': child_serializer,
        }
        if allow_empty is not None:
            list_kwargs['allow_empty'] = allow_empty
        list_kwargs.update({
            key: value for key, value in kwargs.items()
            if key in LIST_SERIALIZER_KWARGS
        })
        meta = getattr(cls, 'Meta', None)
        list_serializer_class = getattr(meta, 'list_serializer_class', ListSerializer)
        return list_serializer_class(*args, **list_kwargs)

    def to_internal_value(self, data):
        raise NotImplementedError('`to_internal_value()` must be implemented.')

    def to_representation(self, instance):
        raise NotImplementedError('`to_representation()` must be implemented.')

    def update(self, instance, validated_data):
        raise NotImplementedError('`update()` must be implemented.')

    def create(self, validated_data):
        raise NotImplementedError('`create()` must be implemented.')

    def save(self, **kwargs):
        assert not hasattr(self, 'save_object'), (
            'Serializer `%s.%s` has old-style version 2 `.save_object()` '
            'that is no longer compatible with REST framework 3. '
            'Use the new-style `.create()` and `.update()` methods instead.' %
            (self.__class__.__module__, self.__class__.__name__)
        )

        assert hasattr(self, '_errors'), (
            'You must call `.is_valid()` before calling `.save()`.'
        )

        assert not self.errors, (
            'You cannot call `.save()` on a serializer with invalid data.'
        )

        # Guard against incorrect use of `serializer.save(commit=False)`
        assert 'commit' not in kwargs, (
            "'commit' is not a valid keyword argument to the 'save()' method. "
            "If you need to access data before committing to the database then "
            "inspect 'serializer.validated_data' instead. "
            "You can also pass additional keyword arguments to 'save()' if you "
            "need to set extra attributes on the saved model instance. "
            "For example: 'serializer.save(owner=request.user)'.'"
        )

        assert not hasattr(self, '_data'), (
            "You cannot call `.save()` after accessing `serializer.data`."
            "If you need to access data before committing to the database then "
            "inspect 'serializer.validated_data' instead. "
        )

        validated_data = dict(
            list(self.validated_data.items()) +
            list(kwargs.items())
        )

        if self.instance is not None:
            self.instance = self.update(self.instance, validated_data)
            assert self.instance is not None, (
                '`update()` did not return an object instance.'
            )
        else:
            self.instance = self.create(validated_data)
            assert self.instance is not None, (
                '`create()` did not return an object instance.'
            )

        return self.instance

    def is_valid(self, raise_exception=False):
        assert hasattr(self, 'initial_data'), (
            'Cannot call `.is_valid()` as no `data=` keyword argument was '
            'passed when instantiating the serializer instance.'
        )

        if not hasattr(self, '_validated_data'):
            try:
                self._validated_data = self.run_validation(self.initial_data)
            except ValidationError as exc:
                self._validated_data = {}
                self._errors = exc.detail
            else:
                self._errors = {}

        if self._errors and raise_exception:
            raise ValidationError(detail=self.errors)

        return not bool(self._errors)

    @property
    def data(self):
        if hasattr(self, 'initial_data') and not hasattr(self, '_validated_data'):
            msg = (
                'When a serializer is passed a `data` keyword argument you '
                'must call `.is_valid()` before attempting to access the '
                'serialized `.data` representation.\n'
                'You should either call `.is_valid()` first, '
                'or access `.initial_data` instead.'
            )
            raise AssertionError(msg)

        if not hasattr(self, '_data'):
            if self.instance is not None and not getattr(self, '_errors', None):
                self._data = self.to_representation(self.instance)
            elif hasattr(self, '_validated_data') and not getattr(self, '_errors', None):
                self._data = self.to_representation(self.validated_data)
            else:
                self._data = self.get_initial()
        return self._data

    @property
    def errors(self):
        if not hasattr(self, '_errors'):
            msg = 'You must call `.is_valid()` before accessing `.errors`.'
            raise AssertionError(msg)
        return self._errors

    @property
    def validated_data(self):
        if not hasattr(self, '_validated_data'):
            msg = 'You must call `.is_valid()` before accessing `.validated_data`.'
            raise AssertionError(msg)
        return self._validated_data


# Serializer & ListSerializer classes
# -----------------------------------

class SerializerMetaclass(type):
    """
    This metaclass sets a dictionary named `_declared_fields` on the class.

    Any instances of `Field` included as attributes on either the class
    or on any of its superclasses will be include in the
    `_declared_fields` dictionary.
    """

    @classmethod
    def _get_declared_fields(cls, bases, attrs):
        fields = [(field_name, attrs.pop(field_name))
                  for field_name, obj in list(attrs.items())
                  if isinstance(obj, Field)]
        fields.sort(key=lambda x: x[1]._creation_counter)

        # If this class is subclassing another Serializer, add that Serializer's
        # fields.  Note that we loop over the bases in *reverse*. This is necessary
        # in order to maintain the correct order of fields.
        for base in reversed(bases):
            if hasattr(base, '_declared_fields'):
                fields = [
                    (field_name, obj) for field_name, obj
                    in base._declared_fields.items()
                    if field_name not in attrs
                ] + fields

        return OrderedDict(fields)

    def __new__(cls, name, bases, attrs):
        attrs['_declared_fields'] = cls._get_declared_fields(bases, attrs)
        return super(SerializerMetaclass, cls).__new__(cls, name, bases, attrs)


def as_serializer_error(exc):
    assert isinstance(exc, ValidationError)

    detail = exc.detail

    if isinstance(detail, list):
        # Errors raised as a list are non-field errors.
        return {
            NON_FIELD_ERRORS_KEY: detail
        }
    # Errors raised as a string are non-field errors.
    return {
        NON_FIELD_ERRORS_KEY: [detail]
    }


class Serializer(BaseSerializer, metaclass=SerializerMetaclass):

    default_error_messages = {
        'invalid': 'Invalid data. Expected a dictionary, but got {datatype}.'
    }

    @property
    def fields(self):
        """
        A dictionary of {field_name: field_instance}.
        """
        # `fields` is evaluated lazily. We do this to ensure that we don't
        # have issues importing modules that use ModelSerializers as fields,
        # even if Django's app-loading stage has not yet run.
        if not hasattr(self, '_fields'):
            self._fields = BindingDict(self)
            for key, value in self.get_fields().items():
                self._fields[key] = value
        return self._fields

    @cached_property
    def _writable_fields(self):
        return [
            field for field in self.fields.values()
            if (not field.read_only) or (field.default is not empty)
        ]

    @cached_property
    def _readable_fields(self):
        return [
            field for field in self.fields.values()
            if not field.write_only
        ]

    def get_fields(self):
        """
        Returns a dictionary of {field_name: field_instance}.
        """
        # Every new serializer is created with a clone of the field instances.
        # This allows users to dynamically modify the fields on a serializer
        # instance without affecting every other serializer class.
        return copy.deepcopy(self._declared_fields)

    def get_validators(self):
        """
        Returns a list of validator callables.
        """
        # Used by the lazily-evaluated `validators` property.
        meta = getattr(self, 'Meta', None)
        validators = getattr(meta, 'validators', None)
        return validators[:] if validators else []

    def get_initial(self):
        if hasattr(self, 'initial_data'):
            return OrderedDict([
                (field_name, field.get_value(self.initial_data))
                for field_name, field in self.fields.items()
                if (field.get_value(self.initial_data) is not empty) and
                not field.read_only
            ])

        return OrderedDict([
            (field.field_name, field.get_initial())
            for field in self.fields.values()
            if not field.read_only
        ])

    def get_value(self, dictionary):
        # We override the default field access in order to support
        # nested HTML forms.
        if html.is_html_input(dictionary):
            return html.parse_html_dict(dictionary, prefix=self.field_name) or empty
        return dictionary.get(self.field_name, empty)

    def run_validation(self, data=empty):
        """
        We override the default `run_validation`, because the validation
        performed by validators and the `.validate()` method should
        be coerced into an error dictionary with a 'non_fields_error' key.
        """
        (is_empty_value, data) = self.validate_empty_values(data)
        if is_empty_value:
            return data

        value = self.to_internal_value(data)
        try:
            self.run_validators(value)
            value = self.validate(value)
            assert value is not None, '.validate() should return the validated data'
        except ValidationError as exc:
            raise ValidationError(detail=as_serializer_error(exc))

        return value

    def to_internal_value(self, data):
        """
        Dict of native values <- Dict of primitive datatypes.
        """
        if not isinstance(data, Mapping):
            message = self.error_messages['invalid'].format(
                datatype=type(data).__name__
            )
            raise ValidationError(detail={
                NON_FIELD_ERRORS_KEY: [message]
            }, api_code='invalid')

        ret = OrderedDict()
        errors = OrderedDict()
        fields = self._writable_fields

        for field in fields:
            validate_method = getattr(self, 'validate_' + field.field_name, None)
            primitive_value = field.get_value(data)
            try:
                validated_value = field.run_validation(primitive_value)
                if validate_method is not None:
                    validated_value = validate_method(validated_value)
            except ValidationError as exc:
                message = exc.get_message()
                if isinstance(message, (str, dict)):
                    message = [message, ]
                errors[field.field_name] = message
            except SkipField:
                pass
            else:
                set_value(ret, field.source_attrs, validated_value)

        if errors:
            raise ValidationError(detail=errors)

        return ret

    def to_representation(self, instance):
        """
        Object instance -> Dict of primitive datatypes.
        """
        ret = OrderedDict()
        fields = self._readable_fields

        for field in fields:
            try:
                attribute = field.get_attribute(instance)
            except SkipField:
                continue

            # We skip `to_representation` for `None` values so that fields do
            # not have to explicitly deal with that case.
            if attribute is None:
                ret[field.field_name] = None
            else:
                ret[field.field_name] = field.to_representation(attribute)

        return ret

    def validate(self, attrs):
        return attrs

    def __repr__(self):
        return representation.serializer_repr(self, indent=1)

    # The following are used for accessing `BoundField` instances on the
    # serializer, for the purposes of presenting a form-like API onto the
    # field values and field errors.

    def __iter__(self):
        for field in self.fields.values():
            yield self[field.field_name]

    def __getitem__(self, key):
        field = self.fields[key]
        value = self.data.get(key)
        error = self.errors.get(key) if hasattr(self, '_errors') else None
        if isinstance(field, Serializer):
            return NestedBoundField(field, value, error)
        return BoundField(field, value, error)

    # Include a backlink to the serializer class on return objects.
    # Allows renderers such as HTMLFormRenderer to get the full field info.

    @property
    def data(self):
        ret = super(Serializer, self).data
        return ReturnDict(ret, serializer=self)

    @property
    def errors(self):
        ret = super(Serializer, self).errors
        if isinstance(ret, list) and len(ret) == 1 and getattr(ret[0], 'code', None) == 'null':
            # Edge case. Provide a more descriptive error than
            # "this field may not be null", when no data is passed.
            detail = {'detail': 'No data provided', 'code': 'null'}
            ret = {NON_FIELD_ERRORS_KEY: [detail, ]}
        return ReturnDict(ret, serializer=self)


# There's some replication of `ListField` here,
# but that's probably better than obfuscating the call hierarchy.

class ListSerializer(BaseSerializer):
    child = None
    many = True

    default_error_messages = {
        'not_a_list': 'Expected a list of items but got type "{input_type}".',
        'empty': 'This list may not be empty.'
    }

    def __init__(self, *args, **kwargs):
        self.child = kwargs.pop('child', copy.deepcopy(self.child))
        self.allow_empty = kwargs.pop('allow_empty', True)
        assert self.child is not None, '`child` is a required argument.'
        assert not inspect.isclass(self.child), '`child` has not been instantiated.'
        super(ListSerializer, self).__init__(*args, **kwargs)
        self.child.bind(field_name='', parent=self)

    def get_initial(self):
        if hasattr(self, 'initial_data'):
            return self.to_representation(self.initial_data)
        return []

    def get_value(self, dictionary):
        """
        Given the input dictionary, return the field value.
        """
        # We override the default field access in order to support
        # lists in HTML forms.
        if html.is_html_input(dictionary):
            return html.parse_html_list(dictionary, prefix=self.field_name)
        return dictionary.get(self.field_name, empty)

    def run_validation(self, data=empty):
        """
        We override the default `run_validation`, because the validation
        performed by validators and the `.validate()` method should
        be coerced into an error dictionary with a 'non_fields_error' key.
        """
        (is_empty_value, data) = self.validate_empty_values(data)
        if is_empty_value:
            return data

        value = self.to_internal_value(data)
        try:
            self.run_validators(value)
            value = self.validate(value)
            assert value is not None, '.validate() should return the validated data'
        except ValidationError as exc:
            raise ValidationError(detail=as_serializer_error(exc))

        return value

    def to_internal_value(self, data):
        """
        List of dicts of native values <- List of dicts of primitive datatypes.
        """
        if html.is_html_input(data):
            data = html.parse_html_list(data)

        if not isinstance(data, list):
            message = self.error_messages['not_a_list'].format(
                input_type=type(data).__name__
            )
            raise ValidationError(detail={
                'not_field_errors': [message, ]
            }, api_code='not_a_list')

        if not self.allow_empty and len(data) == 0:
            message = self.error_messages['empty']
            raise ValidationError(detail={
                NON_FIELD_ERRORS_KEY: [message]
            }, code='empty')

        ret = []
        errors = []

        for item in data:
            try:
                validated = self.child.run_validation(item)
            except ValidationError as exc:
                errors.append(exc.detail)
            else:
                ret.append(validated)
                errors.append({})

        if any(errors):
            raise ValidationError(detail=errors)

        return ret

    def to_representation(self, data):
        """
        List of object instances -> List of dicts of primitive datatypes.
        """
        # Dealing with nested relationships, data can be a Manager,
        # so, first get a queryset from the Manager if needed
        iterable = data

        return [
            self.child.to_representation(item) for item in iterable
        ]

    def validate(self, attrs):
        return attrs

    def update(self, instance, validated_data):
        raise NotImplementedError(
            "Serializers with many=True do not support multiple update by "
            "default, only multiple create. For updates it is unclear how to "
            "deal with insertions and deletions. If you need to support "
            "multiple update, use a `ListSerializer` class and override "
            "`.update()` so you can specify the behavior exactly."
        )

    def create(self, validated_data):
        return [
            self.child.create(attrs) for attrs in validated_data
        ]

    def save(self, **kwargs):
        """
        Save and return a list of object instances.
        """
        # Guard against incorrect use of `serializer.save(commit=False)`
        assert 'commit' not in kwargs, (
            "'commit' is not a valid keyword argument to the 'save()' method. "
            "If you need to access data before committing to the database then "
            "inspect 'serializer.validated_data' instead. "
            "You can also pass additional keyword arguments to 'save()' if you "
            "need to set extra attributes on the saved model instance. "
            "For example: 'serializer.save(owner=request.user)'.'"
        )

        validated_data = [
            dict(list(attrs.items()) + list(kwargs.items()))
            for attrs in self.validated_data
        ]

        if self.instance is not None:
            self.instance = self.update(self.instance, validated_data)
            assert self.instance is not None, (
                '`update()` did not return an object instance.'
            )
        else:
            self.instance = self.create(validated_data)
            assert self.instance is not None, (
                '`create()` did not return an object instance.'
            )

        return self.instance

    def is_valid(self, raise_exception=False):
        # This implementation is the same as the default,
        # except that we use lists, rather than dicts, as the empty case.
        assert hasattr(self, 'initial_data'), (
            'Cannot call `.is_valid()` as no `data=` keyword argument was '
            'passed when instantiating the serializer instance.'
        )

        if not hasattr(self, '_validated_data'):
            try:
                self._validated_data = self.run_validation(self.initial_data)
            except ValidationError as exc:
                self._validated_data = []
                self._errors = exc.detail
            else:
                self._errors = []

        if self._errors and raise_exception:
            raise ValidationError(detail=self.errors)

        return not bool(self._errors)

    def __repr__(self):
        return representation.list_repr(self, indent=1)

    # Include a backlink to the serializer class on return objects.
    # Allows renderers such as HTMLFormRenderer to get the full field info.

    @property
    def data(self):
        ret = super(ListSerializer, self).data
        return ReturnList(ret, serializer=self)

    @property
    def errors(self):
        ret = super(ListSerializer, self).errors
        if isinstance(ret, list) and len(ret) == 1 and getattr(ret[0], 'code', None) == 'null':
            # Edge case. Provide a more descriptive error than
            # "this field may not be null", when no data is passed.
            detail = {'detail': 'No data provided', 'code': 'null'}
            ret = {NON_FIELD_ERRORS_KEY: [detail, ]}
        if isinstance(ret, dict):
            return ReturnDict(ret, serializer=self)
        return ReturnList(ret, serializer=self)
