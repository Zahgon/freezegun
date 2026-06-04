from . import config
from ._async import wrap_coroutine
import asyncio
import copyreg
import dateutil
import datetime
import functools
import sys
import time
import uuid
import calendar
import unittest
import platform
import warnings
import types
import numbers
import inspect
from typing import TYPE_CHECKING, overload
from typing import Any, Awaitable, Callable, Dict, Iterator, List, Optional, Set, Type, TypeVar, Tuple, Union

from dateutil import parser
from dateutil.tz import tzlocal

try:
    from maya import MayaDT  # type: ignore
except ImportError:
    MayaDT = None

if TYPE_CHECKING:
    from typing_extensions import ParamSpec

    P = ParamSpec("P")

T = TypeVar("T")

_TIME_NS_PRESENT = hasattr(time, 'time_ns')
_MONOTONIC_NS_PRESENT = hasattr(time, 'monotonic_ns')
_PERF_COUNTER_NS_PRESENT = hasattr(time, 'perf_counter_ns')
_EPOCH = datetime.datetime(1970, 1, 1)
_EPOCHTZ = datetime.datetime(1970, 1, 1, tzinfo=dateutil.tz.UTC)

T2 = TypeVar("T2")
_Freezable = Union[str, datetime.datetime,  datetime.date,  datetime.timedelta,  types.FunctionType,  Callable[[], Union[str, datetime.datetime, datetime.date, datetime.timedelta]], Iterator[datetime.datetime]]

real_time = time.time
real_localtime = time.localtime
real_gmtime = time.gmtime
real_monotonic = time.monotonic
real_perf_counter = time.perf_counter
real_strftime = time.strftime
real_date = datetime.date
real_datetime = datetime.datetime
real_date_objects = [real_time, real_localtime, real_gmtime, real_monotonic, real_perf_counter, real_strftime, real_date, real_datetime]

if _TIME_NS_PRESENT:
    real_time_ns = time.time_ns
    real_date_objects.append(real_time_ns)

if _MONOTONIC_NS_PRESENT:
    real_monotonic_ns = time.monotonic_ns
    real_date_objects.append(real_monotonic_ns)

if _PERF_COUNTER_NS_PRESENT:
    real_perf_counter_ns = time.perf_counter_ns
    real_date_objects.append(real_perf_counter_ns)

_real_time_object_ids = {id(obj) for obj in real_date_objects}

# time.clock is deprecated and was removed in Python 3.8
real_clock = getattr(time, 'clock', None)

freeze_factories: List[Union["StepTickTimeFactory", "TickingDateTimeFactory", "FrozenDateTimeFactory"]] = []
tz_offsets: List[datetime.timedelta] = []
ignore_lists: List[Tuple[str, ...]] = []
tick_flags: List[bool] = []

try:
    # noinspection PyUnresolvedReferences
    real_uuid_generate_time = uuid._uuid_generate_time  # type: ignore
    uuid_generate_time_attr = '_uuid_generate_time'
except AttributeError:
    # noinspection PyUnresolvedReferences
    if hasattr(uuid, '_load_system_functions'):
        # A no-op after Python ~3.9, being removed in 3.13.
        uuid._load_system_functions()
    # noinspection PyUnresolvedReferences
    real_uuid_generate_time = uuid._generate_time_safe  # type: ignore
    uuid_generate_time_attr = '_generate_time_safe'
except ImportError:
    real_uuid_generate_time = None
    uuid_generate_time_attr = None  # type: ignore

try:
    # noinspection PyUnresolvedReferences
    real_uuid_create = uuid._UuidCreate  # type: ignore
except (AttributeError, ImportError):
    real_uuid_create = None


# keep a cache of module attributes otherwise freezegun will need to analyze too many modules all the time
_GLOBAL_MODULES_CACHE: Dict[str, Tuple[str, List[Tuple[str, Any]]]] = {}










_is_cpython = (
    hasattr(platform, 'python_implementation') and
    platform.python_implementation().lower() == "cpython"
)


call_stack_inspection_limit = 5


def _should_use_real_time() -> bool:
    if not call_stack_inspection_limit:
        return False

    # Means stop() has already been called, so we can now return the real time
    if not ignore_lists:
        return True

    if not ignore_lists[-1]:
        return False

    frame = inspect.currentframe().f_back.f_back  # type: ignore

    for _ in range(call_stack_inspection_limit):
        module_name = frame.f_globals.get('__name__')  # type: ignore
        if module_name and module_name.startswith(ignore_lists[-1]):
            return True

        frame = frame.f_back  # type: ignore
        if frame is None:
            break

    return False


def get_current_time() -> datetime.datetime:
    return freeze_factories[-1]()


def fake_time() -> float:
    if _should_use_real_time():
        return real_time()
    current_time = get_current_time()
    return calendar.timegm(current_time.timetuple()) + current_time.microsecond / 1000000.0

if _TIME_NS_PRESENT:


def fake_localtime(t: Optional[float]=None) -> time.struct_time:
    if t is not None:
        return real_localtime(t)
    if _should_use_real_time():
        return real_localtime()
    shifted_time = get_current_time() - datetime.timedelta(seconds=time.timezone)
    return shifted_time.timetuple()


def fake_gmtime(t: Optional[float]=None) -> time.struct_time:
    if t is not None:
        return real_gmtime(t)
    if _should_use_real_time():
        return real_gmtime()
    return get_current_time().timetuple()










if _MONOTONIC_NS_PRESENT:


if _PERF_COUNTER_NS_PRESENT:


def fake_strftime(format: Any, time_to_format: Any=None) -> str:
    if time_to_format is None:
        if not _should_use_real_time():
            time_to_format = fake_localtime()

    if time_to_format is None:
        return real_strftime(format)
    else:
        return real_strftime(format, time_to_format)

if real_clock is not None:


class FakeDateMeta(type):
    @classmethod
    def __instancecheck__(self, obj: Any) -> bool:
        return isinstance(obj, real_date)

    @classmethod
    def __subclasscheck__(cls, subclass: Any) -> bool:
        return issubclass(subclass, real_date)


def datetime_to_fakedatetime(datetime: datetime.datetime) -> "FakeDatetime":
    return FakeDatetime(datetime.year,
                        datetime.month,
                        datetime.day,
                        datetime.hour,
                        datetime.minute,
                        datetime.second,
                        datetime.microsecond,
                        datetime.tzinfo)


def date_to_fakedate(date: datetime.date) -> "FakeDate":
    return FakeDate(date.year,
                    date.month,
                    date.day)


class FakeDate(real_date, metaclass=FakeDateMeta):
    def __add__(self, other: Any) -> "FakeDate":
        result = real_date.__add__(self, other)
        if result is NotImplemented:
            return result
        return date_to_fakedate(result)

    def __sub__(self, other: Any) -> "FakeDate":  # type: ignore
        result = real_date.__sub__(self, other)
        if result is NotImplemented:
            return result  # type: ignore
        if isinstance(result, real_date):
            return date_to_fakedate(result)
        else:
            return result  # type: ignore

    @classmethod
    def today(cls: Type["FakeDate"]) -> "FakeDate":
        result = cls._date_to_freeze() + cls._tz_offset()
        return date_to_fakedate(result)

    @staticmethod
    def _date_to_freeze() -> datetime.datetime:
        return get_current_time()

    @classmethod
    def _tz_offset(cls) -> datetime.timedelta:
        return tz_offsets[-1]

FakeDate.min = date_to_fakedate(real_date.min)
FakeDate.max = date_to_fakedate(real_date.max)


class FakeDatetimeMeta(FakeDateMeta):
    @classmethod
    def __instancecheck__(self, obj: Any) -> bool:
        return isinstance(obj, real_datetime)

    @classmethod
    def __subclasscheck__(cls, subclass: Any) -> bool:
        return issubclass(subclass, real_datetime)


class FakeDatetime(real_datetime, FakeDate, metaclass=FakeDatetimeMeta):
    def __add__(self, other: Any) -> "FakeDatetime":  # type: ignore
        result = real_datetime.__add__(self, other)
        if result is NotImplemented:
            return result
        return datetime_to_fakedatetime(result)

    def __sub__(self, other: Any) -> "FakeDatetime":  # type: ignore
        result = real_datetime.__sub__(self, other)
        if result is NotImplemented:
            return result  # type: ignore
        if isinstance(result, real_datetime):
            return datetime_to_fakedatetime(result)
        else:
            return result  # type: ignore




    @classmethod
    def now(cls, tz: Optional[datetime.tzinfo] = None) -> "FakeDatetime":
        now = cls._time_to_freeze() or real_datetime.now()
        if tz:
            result = tz.fromutc(now.replace(tzinfo=tz)) + cls._tz_offset()
        else:
            result = now + cls._tz_offset()
        return datetime_to_fakedatetime(result)

    def date(self) -> "FakeDate":
        return date_to_fakedate(self)


    @classmethod
    def today(cls) -> "FakeDatetime":
        return cls.now(tz=None)


    @staticmethod
    def _time_to_freeze() -> Optional[datetime.datetime]:
        if freeze_factories:
            return get_current_time()
        return None

    @classmethod
    def _tz_offset(cls) -> datetime.timedelta:
        return tz_offsets[-1]


FakeDatetime.min = datetime_to_fakedatetime(real_datetime.min)
FakeDatetime.max = datetime_to_fakedatetime(real_datetime.max)


def convert_to_timezone_naive(time_to_freeze: datetime.datetime) -> datetime.datetime:
    """
    Converts a potentially timezone-aware datetime to be a naive UTC datetime
    """
    pass






def _parse_time_to_freeze(time_to_freeze_str: Optional[_Freezable]) -> datetime.datetime:
    """Parses all the possible inputs for freeze_time
    :returns: a naive ``datetime.datetime`` object
    """
    pass




class TickingDateTimeFactory:

    def __init__(self, time_to_freeze: datetime.datetime, start: datetime.datetime):
        self.time_to_freeze = time_to_freeze
        self.start = start

    def __call__(self) -> datetime.datetime:
        return self.time_to_freeze + (real_datetime.now() - self.start)


    def move_to(self, target_datetime: _Freezable) -> None:
        """Moves frozen date to the given ``target_datetime``"""
        pass


class FrozenDateTimeFactory:

    def __init__(self, time_to_freeze: datetime.datetime):
        self.time_to_freeze = time_to_freeze

    def __call__(self) -> datetime.datetime:
        return self.time_to_freeze


    def move_to(self, target_datetime: _Freezable) -> None:
        """Moves frozen date to the given ``target_datetime``"""
        pass


class StepTickTimeFactory:

    def __init__(self, time_to_freeze: datetime.datetime, step_width: float):
        self.time_to_freeze = time_to_freeze
        self.step_width = step_width

    def __call__(self) -> datetime.datetime:
        return_time = self.time_to_freeze
        self.tick()
        return return_time



    def move_to(self, target_datetime: _Freezable) -> None:
        """Moves frozen date to the given ``target_datetime``"""
        pass


class _freeze_time:
    """
    A class to freeze time for testing purposes.

    This class can be used as a context manager or a decorator to freeze time
    during the execution of a block of code or a function. It provides various
    options to customize the behavior of the frozen time.

    Attributes:
        time_to_freeze (datetime.datetime): The datetime to freeze time at.
        tz_offset (datetime.timedelta): The timezone offset to apply to the frozen time.
        ignore (List[str]): A list of module names to ignore when freezing time.
        tick (bool): Whether to allow time to tick forward.
        auto_tick_seconds (float): The number of seconds to auto-tick the frozen time.
        undo_changes (List[Tuple[types.ModuleType, str, Any]]): A list of changes to undo when stopping the frozen time.
        modules_at_start (Set[str]): A set of module names that were loaded at the start of freezing time.
        as_arg (bool): Whether to pass the frozen time as an argument to the decorated function.
        as_kwarg (str): The name of the keyword argument to pass the frozen time to the decorated function.
        real_asyncio (Optional[bool]): Whether to allow asyncio event loops to see real monotonic time.

    Methods:
        __call__(func): Decorates a function or class to freeze time during its execution.
        decorate_class(klass): Decorates a class to freeze time during its execution.
        __enter__(): Starts freezing time and returns the time factory.
        __exit__(*args): Stops freezing time.
        start(): Starts freezing time and returns the time factory.
        stop(): Stops freezing time and restores the original time functions.
        decorate_coroutine(coroutine): Decorates a coroutine to freeze time during its execution.
        decorate_callable(func): Decorates a callable to freeze time during its execution.
    """

    def __init__(
        self,
        time_to_freeze_str: Optional[_Freezable],
        tz_offset: Union[int, datetime.timedelta],
        ignore: List[str],
        tick: bool,
        as_arg: bool,
        as_kwarg: str,
        auto_tick_seconds: float,
        real_asyncio: Optional[bool],
    ):
        self.time_to_freeze = _parse_time_to_freeze(time_to_freeze_str)
        self.tz_offset = _parse_tz_offset(tz_offset)
        self.ignore = tuple(ignore)
        self.tick = tick
        self.auto_tick_seconds = auto_tick_seconds
        self.undo_changes: List[Tuple[types.ModuleType, str, Any]] = []
        self.modules_at_start: Set[str] = set()
        self.as_arg = as_arg
        self.as_kwarg = as_kwarg
        self.real_asyncio = real_asyncio

    # mypy objects to this because Type is Callable, but Pytype needs it because
    # (unlike mypy's) its inference does not assume class decorators always leave
    # the type unchanged.
    @overload
    def __call__(self, func: Type[T2]) -> Type[T2]:  # type: ignore[overload-overlap]
        ...

    @overload
    def __call__(self, func: "Callable[P, Awaitable[Any]]") -> "Callable[P, Awaitable[Any]]":
        ...

    @overload
    def __call__(self, func: "Callable[P, T]") -> "Callable[P, T]":
        ...

    def __call__(self, func: Union[Type[T2], "Callable[P, Awaitable[Any]]", "Callable[P, T]"]) -> Union[Type[T2], "Callable[P, Awaitable[Any]]", "Callable[P, T]"]:  # type: ignore
        if inspect.isclass(func):
            return self.decorate_class(func)
        elif inspect.iscoroutinefunction(func):
            return self.decorate_coroutine(func)
        elif inspect.isgeneratorfunction(func):
            return self.decorate_generator_function(func) # type: ignore
        return self.decorate_callable(func)  # type: ignore


    def __enter__(self) -> Union[StepTickTimeFactory, TickingDateTimeFactory, FrozenDateTimeFactory]:
        return self.start()

    def __exit__(self, *args: Any) -> None:
        self.stop()




    def _call_with_time_factory(self, time_factory: Union[StepTickTimeFactory, TickingDateTimeFactory, FrozenDateTimeFactory], func: "Callable[P, T]", args: Any, kwargs: Any) -> T:
        """
        Invoke a function and pass in the TimeFactory if necessary

        :args: Original arguments to the function.
        :kwargs: Original keyword arguments. Passed in as a dict in case the keys conflict with the other arguments to this function ('time_factory' or 'func')
        """
        pass




def freeze_time(time_to_freeze: Optional[_Freezable]=None, tz_offset: Union[int, datetime.timedelta]=0, ignore: Optional[List[str]]=None, tick: bool=False, as_arg: bool=False, as_kwarg: str='',
                auto_tick_seconds: float=0, real_asyncio: bool=False) -> _freeze_time:
    """
    Freezes time for testing purposes.

    This function can be used as a decorator or a context manager to freeze time
    during the execution of a block of code or a function. It provides various
    options to customize the behavior of the frozen time.

    Args:
        time_to_freeze (Optional[_Freezable]): The datetime to freeze time at.
        tz_offset (Union[int, datetime.timedelta]): The timezone offset to apply to the frozen time.
        ignore (Optional[List[str]]): A list of module names to ignore when freezing time.
        tick (bool): Whether to allow time to tick forward.
        as_arg (bool): Whether to pass the frozen time as an argument to the decorated function.
        as_kwarg (str): The name of the keyword argument to pass the frozen time to the decorated function.
        auto_tick_seconds (float): The number of seconds to auto-tick the frozen time.
        real_asyncio (bool): Whether to allow asyncio event loops to see real monotonic time.

    Returns:
        _freeze_time: An instance of the _freeze_time class.
    """
    acceptable_times: Any = (type(None), str, datetime.date, datetime.timedelta,
             types.FunctionType, types.GeneratorType)

    if MayaDT is not None:
        acceptable_times += MayaDT,

    if not isinstance(time_to_freeze, acceptable_times):
        raise TypeError(('freeze_time() expected None, a string, date instance, datetime '
                         'instance, MayaDT, timedelta instance, function or a generator, but got '
                         'type {}.').format(type(time_to_freeze)))
    if tick and not _is_cpython:
        raise SystemError('Calling freeze_time with tick=True is only compatible with CPython')

    if isinstance(time_to_freeze, types.FunctionType):
        return freeze_time(time_to_freeze(), tz_offset, ignore, tick, as_arg, as_kwarg, auto_tick_seconds, real_asyncio=real_asyncio)

    if isinstance(time_to_freeze, types.GeneratorType):
        return freeze_time(next(time_to_freeze), tz_offset, ignore, tick, as_arg, as_kwarg, auto_tick_seconds, real_asyncio=real_asyncio)

    if MayaDT is not None and isinstance(time_to_freeze, MayaDT):
        return freeze_time(time_to_freeze.datetime(), tz_offset, ignore,
                           tick, as_arg, as_kwarg, auto_tick_seconds, real_asyncio=real_asyncio)

    if ignore is None:
        ignore = []
    ignore = ignore[:]
    if config.settings.default_ignore_list:
        ignore.extend(config.settings.default_ignore_list)

    return _freeze_time(
        time_to_freeze_str=time_to_freeze,
        tz_offset=tz_offset,
        ignore=ignore,
        tick=tick,
        as_arg=as_arg,
        as_kwarg=as_kwarg,
        auto_tick_seconds=auto_tick_seconds,
        real_asyncio=real_asyncio,
    )


# Setup adapters for sqlite
try:
    # noinspection PyUnresolvedReferences
    import sqlite3
except ImportError:
    # Some systems have trouble with this
    pass
else:
    # These are copied from Python sqlite3.dbapi2


    sqlite3.register_adapter(FakeDate, adapt_date)
    sqlite3.register_adapter(FakeDatetime, adapt_datetime)


# Setup converters for pymysql
try:
    import pymysql.converters
except ImportError:
    pass
else:
    pymysql.converters.encoders[FakeDate] = pymysql.converters.encoders[real_date]
    pymysql.converters.conversions[FakeDate] = pymysql.converters.encoders[real_date]
    pymysql.converters.encoders[FakeDatetime] = pymysql.converters.encoders[real_datetime]
    pymysql.converters.conversions[FakeDatetime] = pymysql.converters.encoders[real_datetime]
