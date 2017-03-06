import re

from aiohttp.helpers import is_ip_address

from aiorestframework.utils.functional import SimpleLazyObject


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

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, value):
        raise NotImplementedError('"validate" should be override.')


class MaxValueValidator(BaseValidator):
    api_code = 'max_limit'

    def __init__(self, max_limit, **kwargs):
        self.max_limit = max_limit
        super().__init__(**kwargs)

    def __call__(self, value):
        return [
            value <= self.max_limit,
            self.api_code,
            {'max_limit': self.max_limit}
        ]


class MinValueValidator(BaseValidator):
    api_code = 'min_limit'

    def __init__(self, min_limit, **kwargs):
        self.min_limit = min_limit
        super().__init__(**kwargs)

    def __call__(self, value):
        return [
            value >= self.min_limit,
            self.api_code,
            {'min_limit': self.min_limit}
        ]


class MaxLengthValidator(BaseValidator):
    api_code = 'max_length'

    def __init__(self, max_length, **kwargs):
        self.max_length = max_length
        assert (max_length > 0), '`max_length` should be more than zero.'
        super().__init__(**kwargs)

    def __call__(self, value):
        return [
            len(value) <= self.max_length,
            self.api_code,
            {'max_length': self.max_length}
        ]


class MinLengthValidator(BaseValidator):
    api_code = 'min_length'

    def __init__(self, min_length, **kwargs):
        self.min_length = min_length
        assert (min_length > 0), '`min_length` should be more than zero.'
        super().__init__(**kwargs)

    def __call__(self, value):
        return [
            len(value) >= self.min_length,
            self.api_code,
            {'min_length': self.min_length}
        ]


class EmailValidator(BaseValidator):
    api_code = 'invalid'
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

    success = [True, api_code, {}]
    fail = [False, api_code, {}]

    def __init__(self, whitelist=None, **kwargs):
        if whitelist is not None:
            self.domain_whitelist = whitelist
        super().__init__(**kwargs)

    def __call__(self, value):
        value = str(value)

        if not value or '@' not in value:
            return self.fail

        user_part, domain_part = value.rsplit('@', 1)

        if not self.user_regex.match(user_part):
            return self.fail

        if (domain_part not in self.domain_whitelist and
                not self.validate_domain_part(domain_part)):
            # Try for possible IDN domain-part
            try:
                domain_part = domain_part.encode('idna').decode('ascii')
                if self.validate_domain_part(domain_part):
                    return self.success
            except UnicodeError:
                pass
            return self.fail

        return self.success

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
