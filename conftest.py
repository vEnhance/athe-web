import pytest
from django.conf import LazySettings


@pytest.fixture(autouse=True)
def use_fast_password_hasher(settings: LazySettings) -> None:
    settings.PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]
