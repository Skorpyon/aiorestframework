import collections
import copy
import datetime
import decimal
import inspect
import json
import re
import uuid
from collections import OrderedDict

from aiorestframework import exceptions
from aiorestframework import validators as val
from aiorestframework.utils import representation, html
from aiorestframework.utils.functional import cached_property


__all__ = (
    'empty', 'set_value', 'Field', 'BooleanField', 'NullBooleanField',
    'EmailField'
)


class empty:
    """
    This class is used to represent no data being provided for a given input
    or output value.

    It is required because `None` may be a valid input or output value.
    """
    pass


def is_simple_callable(obj):
    """
    True if the object is a callable that takes no arguments.
    """
    if not (inspect.isfunction(obj) or inspect.ismethod(obj)):
        return False

    sig = inspect.signature(obj)
    params = sig.parameters.values()
    return all(
        param.kind == param.VAR_POSITIONAL or
        param.kind == param.VAR_KEYWORD or
        param.default != param.empty
        for param in params
    )


def get_attribute(instance, attrs):
    """
    Similar to Python's built in `getattr(instance, attr)`,
    but takes a list of nested attributes, instead of a single attribute.

    Also accepts either attribute lookup on objects or dictionary lookups.
    """
    for attr in attrs:
        if instance is None:
            # Break out early if we get `None` at any point in a nested lookup.
            return None
        if isinstance(instance, collections.Mapping):
            instance = instance[attr]
        else:
            instance = getattr(instance, attr)
        if is_simple_callable(instance):
            try:
                instance = instance()
            except (AttributeError, KeyError) as exc:
                # If we raised an Attribute or KeyError here it'd get treated
                # as an omitted field in `Field.get_attribute()`. Instead we
                # raise a ValueError to ensure the exception is not masked.
                raise ValueError('Exception raised in callable attribute "{0}"; original exception was: {1}'.format(attr, exc))

    return instance


def set_value(dictionary, keys, value):
    """
    Similar to Python's built in `dictionary[key] = value`,
    but takes a list of nested keys instead of a single key.

    set_value({'a': 1}, [], {'b': 2}) -> {'a': 1, 'b': 2}
    set_value({'a': 1}, ['x'], 2) -> {'a': 1, 'x': 2}
    set_value({'a': 1}, ['x', 'y'], 2) -> {'a': 1, 'x': {'y': 2}}
    """
    if not keys:
        dictionary.update(value)
        return

    for key in keys[:-1]:
        if key not in dictionary:
            dictionary[key] = {}
        dictionary = dictionary[key]

    dictionary[keys[-1]] = value


REGEX_TYPE = type(re.compile(''))

NOT_READ_ONLY_WRITE_ONLY = 'May not set both `read_only` and `write_only`'
NOT_READ_ONLY_REQUIRED = 'May not set both `read_only` and `required`'
NOT_REQUIRED_DEFAULT = 'May not set both `required` and `default`'
USE_READONLYFIELD = 'Field(read_only=True) should be ReadOnlyField'
MISSING_ERROR_MESSAGE = (
    'ValidationError raised by `{class_name}`, but error key `{key}` does '
    'not exist in the `error_messages` dictionary.'
)


class Field:
    _creation_counter = 0

    default_error_messages = {
        'required': 'This field is required.',
        'null': 'This field may not be null.'
    }
    default_validators = []
    default_empty_html = empty
    initial = None
    parent = None

    def __init__(self, label=None, read_only=False, write_only=False,
                 required=None, default=empty, initial=empty, source=None,
                 error_messages=None, validators=None, allow_null=False, **kwargs):
        self._creation_counter = Field._creation_counter
        Field._creation_counter += 1

        # If `required` is unset, then use `True` unless a default is provided.
        if required is None:
            required = default is empty and not read_only

        # Some combinations of keyword arguments do not make sense.
        assert not (read_only and write_only), NOT_READ_ONLY_WRITE_ONLY
        assert not (read_only and required), NOT_READ_ONLY_REQUIRED
        assert not (required and default is not empty), NOT_REQUIRED_DEFAULT
        assert not (read_only and self.__class__ == Field), USE_READONLYFIELD

        self.read_only = read_only
        self.write_only = write_only
        self.required = required
        self.default = default
        self.source = source
        self.initial = self.initial if (initial is empty) else initial
        self.label = label
        self.allow_null = allow_null

        if self.default_empty_html is not empty:
            if default is not empty:
                self.default_empty_html = default

        if validators is not None:
            self.validators = validators[:]

        # These are set up by `.bind()` when the field is added to a serializer
        self.field_name = None
        self.parent = None

        # Collect default error message from self and parent classes
        messages = {}
        for cls in reversed(self.__class__.__mro__):
            messages.update(getattr(cls, 'default_error_messages', {}))
        messages.update(error_messages or {})
        self.error_messages = messages

    def bind(self, field_name, parent):
        """
        Initializes the field name and parent for the field instance.
        Called when a field is added to the parent serializer instance.
        """

        # In order to enforce a consistent style, we error if a redundant
        # 'source' argument has been used. For example:
        # my_field = serializer.CharField(source='my_field')
        assert self.source != field_name, (
            "It is redundant to specify `source='%s'` on field '%s' in "
            "serializer '%s', because it is the same as the field name. "
            "Remove the `source` keyword argument." %
            (field_name, self.__class__.__name__, parent.__class__.__name__)
        )

        self.field_name = field_name
        self.parent = parent

        # `self.label` should default to being based on the field name.
        if self.label is None:
            self.label = field_name.replace('_', ' ').capitalize()

        # self.source should default to being the same as the field name.
        if self.source is None:
            self.source = field_name

        # self.source_attrs is a list of attributes that need to be looked up
        # when serializing the instance, or populating the validated data.
        if self.source == '*':
            self.source_attrs = []
        else:
            self.source_attrs = self.source.split('.')

    # .validators is a lazily loaded property, that gets its default
    # value from `get_validators`.
    @property
    def validators(self):
        if not hasattr(self, '_validators'):
            self._validators = self.get_validators()
        return self._validators

    @validators.setter
    def validators(self, validators):
        self._validators = validators

    def get_validators(self):
        return self.default_validators[:]

    def get_initial(self):
        """
        Return a value to use when the field is being returned as a primitive
        value, without any object instance.
        """
        if callable(self.initial):
            return self.initial()
        return self.initial

    def get_value(self, dictionary):
        """
        Given the *incoming* primitive data, return the value for this field
        that should be validated and transformed to a native value.
        """
        if html.is_html_input(dictionary):
            # HTML forms will represent empty fields as '', and cannot
            # represent None or False values directly.
            if self.field_name not in dictionary:
                if getattr(self.root, 'partial', False):
                    return empty
                return self.default_empty_html
            ret = dictionary[self.field_name]
            if ret == '' and self.allow_null:
                # If the field is blank, and null is a valid value then
                # determine if we should use null instead.
                return '' if getattr(self, 'allow_blank', False) else None
            elif ret == '' and not self.required:
                # If the field is blank, and emptiness is valid then
                # determine if we should use emptiness instead.
                return '' if getattr(self, 'allow_blank', False) else empty
            return ret
        return dictionary.get(self.field_name, empty)

    def get_attribute(self, instance):
        """
        Given the *outgoing* object instance, return the primitive value
        that should be used for this field.
        """
        try:
            return get_attribute(instance, self.source_attrs)
        except (KeyError, AttributeError) as exc:
            if not self.required and self.default is empty:
                raise exceptions.SkipField()
            msg = (
                'Got {exc_type} when attempting to get a value for field '
                '`{field}` on serializer `{serializer}`.\nThe serializer '
                'field might be named incorrectly and not match '
                'any attribute or key on the `{instance}` instance.\n'
                'Original exception text was: {exc}.'.format(
                    exc_type=type(exc).__name__,
                    field=self.field_name,
                    serializer=self.parent.__class__.__name__,
                    instance=instance.__class__.__name__,
                    exc=exc
                )
            )
            raise type(exc)(msg)

    def validate_empty_values(self, data):
        """
        Validate empty values, and either:
        * Raise `ValidationError`, indicating invalid data.
        * Raise `SkipField`, indicating that the field should be ignored.
        * Return (True, data), indicating an empty value that should be
          returned without any further validation being applied.
        * Return (False, data), indicating a non-empty value, that should
          have validation applied as normal.
        """
        if self.read_only:
            return True, self.get_default()

        if data is empty:
            if getattr(self.root, 'partial', False):
                exceptions.SkipField()
            if self.required:
                self.fail('required')
            return True, self.get_default()

        if data is None:
            if not self.allow_null:
                self.fail('null')
            return True, None

        return False, data

    def run_validation(self, data=empty):
        """
        Validate a simple representation and return the internal value.
        The provided data may be `empty` if no representation was included
        in the input.
        May raise `SkipField` if the field should not be included in the
        validated data.
        """
        (is_empty_value, data) = self.validate_empty_values(data)
        if is_empty_value:
            return data
        value = self.to_internal_value(data)
        self.run_validators(value)
        return value

    def run_validators(self, value):
        errors = []
        for validator in self.validators:
            is_valid, key, kwargs = validator(value)
            if is_valid is False:
                errors.append({
                    'detail': self.get_error_detail(key, **kwargs),
                    'code': self.get_error_code(key)
                })
        if errors:
            raise exceptions.ValidationError(detail=errors)

    def get_error_detail(self, key, **kwargs):
        try:
            msg = self.error_messages[key]
        except KeyError:
            class_name = self.__class__.__name__
            msg = MISSING_ERROR_MESSAGE.format(class_name=class_name, key=key)
            raise AssertionError(msg)
        return msg.format(**kwargs)

    def get_error_code(self, key):
        if 'code_map' in self.context and key in self.context['code_map']:
            return self.context['code_map']['key']
        else:
            return key

    def fail(self, key, **kwargs):
        """
        A helper method that simply raises a validation error.
        """
        detail = self.get_error_detail(key, **kwargs)
        api_code = self.get_error_code(key)
        raise exceptions.ValidationError(detail=detail, api_code=api_code)

    def to_internal_value(self, data):
        """
        Transform the *incoming* primitive data into a native value.
        """
        raise NotImplementedError(
            '{cls}.to_internal_value() must be implemented.'.format(
                cls=self.__class__.__name__
            )
        )

    def to_representation(self, value):
        """
        Transform the *outgoing* native value into primitive data.
        """
        raise NotImplementedError(
            '{cls}.to_representation() must be implemented for field '
            '{field_name}. If you do not need to support write operations '
            'you probably want to subclass `ReadOnlyField` instead.'.format(
                cls=self.__class__.__name__,
                field_name=self.field_name,
            )
        )

    @cached_property
    def root(self):
        """
        Returns the top-level serializer for this field.
        """
        root = self
        while root.parent is not None:
            root = root.parent
        return root

    @cached_property
    def context(self):
        """
        Returns the context as passed to the root serializer on initialization.
        """
        return getattr(self.root, '_context', {})

    def __new__(cls, *args, **kwargs):
        """
        When a field is instantiated, we store the arguments that were used,
        so that we can present a helpful representation of the object.
        """
        instance = super(Field, cls).__new__(cls)
        instance._args = args
        instance._kwargs = kwargs
        return instance

    def __deepcopy__(self, memo):
        """
        When cloning fields we instantiate using the arguments it was
        originally created with, rather than copying the complete state.
        """
        # Treat regexes and validators as immutable.
        # See https://github.com/tomchristie/django-rest-framework/issues/1954
        # and https://github.com/tomchristie/django-rest-framework/pull/4489
        args = [
            copy.deepcopy(item) if not isinstance(item, REGEX_TYPE) else item
            for item in self._args
            ]
        kwargs = {
            key: (copy.deepcopy(value) if (
            key not in ('validators', 'regex')) else value)
            for key, value in self._kwargs.items()
            }
        return self.__class__(*args, **kwargs)

    def __repr__(self):
        """
        Fields are represented using their initial calling arguments.
        This allows us to create descriptive representations for serializer
        instances that show all the declared fields on the serializer.
        """
        return representation.field_repr(self)


# Boolean types...

class BooleanField(Field):
    default_error_messages = {
        'invalid': '"{input}" is not a valid boolean.'
    }
    initial = False
    TRUE_VALUES = {
        't', 'T',
        'true', 'True', 'TRUE',
        'on', 'On', 'ON',
        '1', 1,
        True
    }
    FALSE_VALUES = {
        'f', 'F',
        'false', 'False', 'FALSE',
        'off', 'Off', 'OFF',
        '0', 0, 0.0,
        False
    }

    def __init__(self, **kwargs):
        assert 'allow_null' not in kwargs,\
            '`allow_null` is not a valid option. Use `NullBooleanField` instead.'
        super(BooleanField, self).__init__(**kwargs)

    def to_internal_value(self, data):
        try:
            if data in self.TRUE_VALUES:
                return True
            elif data in self.FALSE_VALUES:
                return False
        except TypeError:  # Input is an unhashable type
            pass
        self.fail('invalid', input=data)

    def to_representation(self, value):
        if value in self.TRUE_VALUES:
            return True
        elif value in self.FALSE_VALUES:
            return False
        return bool(value)


class NullBooleanField(Field):
    default_error_messages = {
        'invalid': '"{input}" is not a valid boolean.'
    }
    initial = None
    TRUE_VALUES = {'t', 'T', 'true', 'True', 'TRUE', '1', 1, True}
    FALSE_VALUES = {'f', 'F', 'false', 'False', 'FALSE', '0', 0, 0.0, False}
    NULL_VALUES = {'n', 'N', 'null', 'Null', 'NULL', '', None}

    def __init__(self, **kwargs):
        assert 'allow_null' not in kwargs, '`allow_null` is not a valid option.'
        kwargs['allow_null'] = True
        super(NullBooleanField, self).__init__(**kwargs)

    def to_internal_value(self, data):
        if data in self.TRUE_VALUES:
            return True
        elif data in self.FALSE_VALUES:
            return False
        elif data in self.NULL_VALUES:
            return None
        self.fail('invalid', input=data)

    def to_representation(self, value):
        if value in self.NULL_VALUES:
            return None
        if value in self.TRUE_VALUES:
            return True
        elif value in self.FALSE_VALUES:
            return False
        return bool(value)


# String types...

class CharField(Field):
    default_error_messages = {
        'invalid': 'Not a valid string.',
        'blank': 'This field may not be blank.',
        'max_length': 'Ensure this field has no more than {max_length} characters.',
        'min_length': 'Ensure this field has at least {min_length} characters.'
    }
    initial = ''

    def __init__(self, **kwargs):
        self.allow_blank = kwargs.pop('allow_blank', False)
        self.trim_whitespace = kwargs.pop('trim_whitespace', True)
        self.max_length = kwargs.pop('max_length', None)
        self.min_length = kwargs.pop('min_length', None)
        super(CharField, self).__init__(**kwargs)
        if self.max_length is not None:
            self.validators.append(val.MaxLengthValidator(self.max_length))
        if self.min_length is not None:
            self.validators.append(val.MinLengthValidator(self.min_length))

    def run_validation(self, data=empty):
        # Test for the empty string here so that it does not get validated,
        # and so that subclasses do not need to handle it explicitly
        # inside the `to_internal_value()` method.
        if data == '' or (self.trim_whitespace and str(data).strip() == ''):
            if not self.allow_blank:
                self.fail('blank')
            return ''
        return super(CharField, self).run_validation(data)

    def to_internal_value(self, data):
        # We're lenient with allowing basic numerics to be coerced into strings,
        # but other types should fail. Eg. unclear if booleans should represent as `true` or `True`,
        # and composites such as lists are likely user error.
        if isinstance(data, bool) or not isinstance(data, (str, int, float)):
            self.fail('invalid')
        value = str(data)
        return value.strip() if self.trim_whitespace else value

    def to_representation(self, value):
        return str(value)


class EmailField(CharField):
    default_error_messages = {
        'invalid': 'Enter a valid email address.'
    }

    def __init__(self, **kwargs):
        super(EmailField, self).__init__(**kwargs)
        validator = val.EmailValidator()
        self.validators.append(validator)