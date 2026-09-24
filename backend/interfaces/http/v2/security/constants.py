from collections.abc import Callable
from typing import Annotated, Any

from pydantic import AfterValidator


def _constant_time_auth_str(v: str) -> str:
    import hmac

    if not isinstance(v, str):
        raise ValueError("value must be a string")
    return v


ConstantTimeString = Annotated[str, AfterValidator(_constant_time_auth_str)]
