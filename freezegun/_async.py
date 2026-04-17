import functools
from typing import Any, Callable, TypeVar, cast


_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])


def wrap_coroutine(api: Any, coroutine: _CallableT) -> _CallableT:
    @functools.wraps(coroutine)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        pass

    return cast(_CallableT, wrapper)
