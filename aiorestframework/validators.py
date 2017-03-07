import re
from urllib.parse import urlsplit, urlunsplit

from aiohttp.helpers import is_ip_address

from aiorestframework.utils.functional import SimpleLazyObject
from aiorestframework.exceptions import ValidationError


def _lazy_re_compile(regex, flags=0):
    """Lazily compile a regex with flags."""
    def _compile():
        # Compile the regex if it was not passed pre-compiled.
        if isinstance(regex, str):
            return re.compile(regex, flags)
        else:
            assert not flags, "flags must be empty if regex is passed pre-compiled"
            return regex
    return SimpleLazyObject(_compile)


class BaseValidator:
    api_code = 'invalid'
    default_message = 'Invalid value.'

    def __init__(self, *args, message=None, **kwargs):
        self.message = message

    def __call__(self, value):
        raise NotImplementedError('"validate" should be override.')

    def _get_message(self):
        return self.message if self.message is not None else self.get_message()

    def get_message(self):
        return self.default_message

    def fail(self):
        raise ValidationError(detail=self._get_message(),
                              api_code=self.api_code)


class MaxValueValidator(BaseValidator):
    api_code = 'max_value'
    default_message = 'Ensure this value is less than or equal to {max_value}.'

    def __init__(self, max_value, **kwargs):
        self.max_value = max_value
        super().__init__(**kwargs)

    def __call__(self, value):
        if value > self.max_value:
            self.fail()

    def get_message(self):
        return self.default_message.format(max_value=self.max_value)


class MinValueValidator(BaseValidator):
    api_code = 'min_value'
    default_message = 'Ensure this value is greater than or equal to {min_value}.'

    def __init__(self, min_value, **kwargs):
        self.min_value = min_value
        super().__init__(**kwargs)

    def __call__(self, value):
        if value < self.min_value:
            self.fail()

    def get_message(self):
        return self.default_message.format(min_value=self.min_value)


class MaxLengthValidator(BaseValidator):
    api_code = 'max_length'
    default_message = 'Ensure this field has no more than {max_length} characters.'

    def __init__(self, max_length, **kwargs):
        self.max_length = max_length
        assert (max_length > 0), '`max_length` should be more than zero.'
        super().__init__(**kwargs)

    def __call__(self, value):
        if len(value) > self.max_length:
            self.fail()

    def get_message(self):
        return self.default_message.format(max_length=self.max_length)


class MinLengthValidator(BaseValidator):
    api_code = 'min_length'
    default_message = 'Ensure this field has at least {min_length} characters.'

    def __init__(self, min_length, **kwargs):
        self.min_length = min_length
        assert (min_length > 0), '`min_length` should be more than zero.'
        super().__init__(**kwargs)

    def __call__(self, value):
        if len(value) < self.min_length:
            self.fail()

    def get_message(self):
        return self.default_message.format(min_length=self.min_length)


class EmailValidator(BaseValidator):
    api_code = 'invalid'
    default_message = 'Enter a valid email address.'

    user_regex = _lazy_re_compile(
        r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*\Z"  # dot-atom
        r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-\011\013\014\016-\177])*"\Z)',  # quoted-string
        re.IGNORECASE)
    domain_regex = _lazy_re_compile(
        # max length for domain name labels is 63 characters per RFC 1034
        r'((?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+)(?:[A-Z0-9-]{2,63}(?<!-))\Z',
        re.IGNORECASE)
    literal_regex = _lazy_re_compile(
        # literal form, ipv4 or ipv6 address (SMTP 4.1.3)
        r'\[([A-f0-9:\.]+)\]\Z',
        re.IGNORECASE)
    domain_whitelist = ['localhost']

    def __init__(self, whitelist=None, **kwargs):
        if whitelist is not None:
            self.domain_whitelist = whitelist
        super().__init__(**kwargs)

    def __call__(self, value):
        value = str(value)

        if not value or '@' not in value:
            self.fail()

        user_part, domain_part = value.rsplit('@', 1)

        if not self.user_regex.match(user_part):
            self.fail()

        if (domain_part not in self.domain_whitelist and
                not self.validate_domain_part(domain_part)):
            # Try for possible IDN domain-part
            try:
                domain_part = domain_part.encode('idna').decode('ascii')
                if self.validate_domain_part(domain_part):
                    return
            except UnicodeError:
                pass
            self.fail()

        return

    def validate_domain_part(self, domain_part):
        if self.domain_regex.match(domain_part):
            return True
        print('Domain part: %s' % domain_part)
        literal_match = self.literal_regex.match(domain_part)
        if literal_match:
            ip_address = literal_match.group(1)
            try:
                return is_ip_address(ip_address)
            except ValueError:
                pass
        return False


class RegexValidator(BaseValidator):
    regex = ''
    api_code = 'invalid'
    default_message = 'This value does not match the required pattern.'
    inverse_match = False
    flags = 0

    def __init__(self, regex=None, inverse_match=None, flags=None, **kwargs):
        if regex is not None:
            self.regex = regex
        if inverse_match is not None:
            self.inverse_match = inverse_match
        if flags is not None:
            self.flags = flags
        if self.flags and not isinstance(self.regex, str):
            raise TypeError("If the flags are set, regex must be a regular "
                            "expression string.")

        self.regex = _lazy_re_compile(self.regex, self.flags)
        super().__init__(**kwargs)

    def __call__(self, value):
        """
        Validates that the input matches the regular expression
        if inverse_match is False, otherwise raises ValidationError.
        """
        if not (self.inverse_match is not bool(self.regex.search(
                str(value)))):
            self.fail()


slug_re = _lazy_re_compile(r'^[-a-zA-Z0-9_]+\Z')
validate_slug = RegexValidator(
    slug_re,
    message="Enter a valid 'slug' consisting of letters, numbers, underscores or hyphens."
)

slug_unicode_re = _lazy_re_compile(r'^[-\w]+\Z', re.U)
validate_unicode_slug = RegexValidator(
    slug_unicode_re,
    message="Enter a valid 'slug' consisting of Unicode letters, numbers, underscores, or hyphens."
)

ipv4_re = _lazy_re_compile(r'^(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\Z')
validate_ipv4_address = RegexValidator(ipv4_re, message='Enter a valid IPv4 address.')


def validate_ipv6_address(value):
    try:
        if is_ip_address(value):
            return
        else:
            pass
    except ValueError:
        pass

    raise ValidationError(detail='Enter a valid IPv6 address.', api_code='invalid')


def validate_ipv46_address(value):
    try:
        validate_ipv4_address(value)
    except ValidationError:
        try:
            validate_ipv6_address(value)
        except ValidationError:
            raise ValidationError(detail='Enter a valid IPv4 or IPv6 address.', api_code='invalid')

ip_address_validator_map = {
    'both': ([validate_ipv46_address], 'Enter a valid IPv4 or IPv6 address.'),
    'ipv4': ([validate_ipv4_address], 'Enter a valid IPv4 address.'),
    'ipv6': ([validate_ipv6_address], 'Enter a valid IPv6 address.'),
}


def ip_address_validators(protocol, unpack_ipv4):
    """
    Depending on the given parameters returns the appropriate validators for
    the GenericIPAddressField.

    This code is here, because it is exactly the same for the model and the form field.
    """
    if protocol != 'both' and unpack_ipv4:
        raise ValueError(
            "You can only use `unpack_ipv4` if `protocol` is set to 'both'")
    try:
        return ip_address_validator_map[protocol.lower()]
    except KeyError:
        raise ValueError("The protocol '%s' is unknown. Supported: %s"
                         % (protocol, list(ip_address_validator_map)))


class URLValidator(RegexValidator):
    api_code = 'invalid'
    default_message = 'Enter a valid URL.'

    ul = '\u00a1-\uffff'  # unicode letters range (must be a unicode string, not a raw string)

    # IP patterns
    ipv4_re = r'(?:25[0-5]|2[0-4]\d|[0-1]?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}'
    ipv6_re = r'\[[0-9a-f:\.]+\]'  # (simple regex, validated later)

    # Host patterns
    hostname_re = r'[a-z' + ul + r'0-9](?:[a-z' + ul + r'0-9-]{0,61}[a-z' + ul + r'0-9])?'
    # Max length for domain name labels is 63 characters per RFC 1034 sec. 3.1
    domain_re = r'(?:\.(?!-)[a-z' + ul + r'0-9-]{1,63}(?<!-))*'
    tld_re = (
        '\.'                                # dot
        '(?!-)'                             # can't start with a dash
        '(?:[a-z' + ul + '-]{2,63}'         # domain label
        '|xn--[a-z0-9]{1,59})'              # or punycode label
        '(?<!-)'                            # can't end with a dash
        '\.?'                               # may have a trailing dot
    )
    host_re = '(' + hostname_re + domain_re + tld_re + '|localhost)'

    regex = _lazy_re_compile(
        r'^(?:[a-z0-9\.\-\+]*)://'  # scheme is validated separately
        r'(?:\S+(?::\S*)?@)?'  # user:pass authentication
        r'(?:' + ipv4_re + '|' + ipv6_re + '|' + host_re + ')'
        r'(?::\d{2,5})?'  # port
        r'(?:[/?#][^\s]*)?'  # resource path
        r'\Z', re.IGNORECASE)
    schemes = ['http', 'https', 'ftp', 'ftps']

    def __init__(self, schemes=None, **kwargs):
        super(URLValidator, self).__init__(**kwargs)
        if schemes is not None:
            self.schemes = schemes

    def __call__(self, value):
        value = str(value)
        # Check first if the scheme is valid
        scheme = value.split('://')[0].lower()
        if scheme not in self.schemes:
            self.fail()

        # Then check full URL
        try:
            super(URLValidator, self).__call__(value)
        except ValidationError as e:
            # Trivial case failed. Try for possible IDN domain
            if value:
                try:
                    scheme, netloc, path, query, fragment = urlsplit(value)
                except ValueError:  # for example, "Invalid IPv6 URL"
                    self.fail()
                try:
                    netloc = netloc.encode('idna').decode('ascii')  # IDN -> ACE
                except UnicodeError:  # invalid domain part
                    raise e
                url = urlunsplit((scheme, netloc, path, query, fragment))
                super(URLValidator, self).__call__(url)
            else:
                raise
        else:
            # Now verify IPv6 in the netloc part
            host_match = re.search(r'^\[(.+)\](?::\d{2,5})?$', urlsplit(value).netloc)
            if host_match:
                potential_ip = host_match.groups()[0]
                try:
                    if is_ip_address(potential_ip) is False:
                        self.fail()
                except ValueError:
                    self.fail()
            url = value

        # The maximum length of a full host name is 253 characters per RFC 1034
        # section 3.1. It's defined to be 255 bytes or less, but this includes
        # one byte for the length of the name and one byte for the trailing dot
        # that's used to indicate absolute names in DNS.
        if len(urlsplit(value).netloc) > 253:
            self.fail()
