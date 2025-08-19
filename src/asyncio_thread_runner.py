"""
Run async code from sync code.

See the ThreadRunner class for details.

"""

from __future__ import annotations

import asyncio
import sys
import threading
from contextlib import AbstractAsyncContextManager as AsyncCM
from contextlib import AbstractContextManager as CM
from contextlib import contextmanager
from contextlib import ExitStack
from typing import Any
from typing import final
from typing import Self
from typing import TYPE_CHECKING
from typing import TypeVar


if TYPE_CHECKING:
    import concurrent.futures as cf
    from collections.abc import AsyncIterable
    from collections.abc import Callable
    from collections.abc import Coroutine
    from collections.abc import Iterable
    from collections.abc import Iterator


__version__ = "1.0"


_T = TypeVar('_T')


@final
class ThreadRunner:
    """A context manager that runs an asyncio.Runner in a dedicated thread.

    Keyword arguments are passed to the underlying asyncio.Runner.

    The run() method can be called multiple times and from multiple threads.

    In addition, the wrap_context() and wrap_iter() methods allow
    converting async context managers and iterables to sync wrappers.

    """

    def __init__(self, **kwargs: Any):
        self._runner = asyncio.Runner(**kwargs)
        self._thread: threading.Thread | None = None
        self._stack = ExitStack()

    def __enter__(self) -> Self:
        self._lazy_init()
        return self

    def __exit__(self, *exc_info: Any) -> bool | None:
        thread = self._thread
        if not thread or not thread.is_alive():
            return None
        try:
            return self._stack.__exit__(*exc_info)
        finally:
            loop = self._runner.get_loop()
            loop.call_soon_threadsafe(loop.stop)
            thread.join()

    def close(self) -> None:
        """Shutdown the underlying event loop and thread."""
        self.__exit__(None, None, None)

    def run(self, coro: Coroutine[Any, Any, _T]) -> _T:
        """Run a coroutine and return the result.

        >>> async def double(i):
        ...     return i * 2
        ...
        >>> runner.run(double(2))
        4

        """
        # XXX: what about context=? run_coroutine_threadsafe doesn't have it
        return self.run_as_future(coro).result()

    def run_as_future(self, coro: Coroutine[Any, Any, _T]) -> cf.Future[_T]:
        """Submit a coroutine to the runner event loop.

        Return a threadsafe concurrent.futures.Future to wait for the result.

        """
        self._lazy_init()
        loop = self._runner.get_loop()
        return asyncio.run_coroutine_threadsafe(coro, loop)

    def _lazy_init(self) -> None:
        if self._thread:
            return

        loop_created = threading.Event()

        def run_forever() -> None:
            with self._runner as runner:
                loop = runner.get_loop()
                asyncio.set_event_loop(loop)
                loop_created.set()
                loop.run_forever()

        self._thread = threading.Thread(
            target=run_forever, name='ThreadRunner', daemon=True
        )
        self._thread.start()
        loop_created.wait()

    def wrap_context(self, cm: AsyncCM[_T] | Callable[[], AsyncCM[_T]], /) -> CM[_T]:
        """Convert an async context manager into a sync wrapper.

        If a callable is provided, call it in the event loop thread
        and use the returned async context manager instead.

        >>> @asynccontextmanager
        ... async def make_context():
        ...     print('enter')
        ...     yield 'value'
        ...     print('exit')
        ...
        >>> with runner.wrap_context(make_context()) as target:
        ...     print(target)
        ...
        enter
        value
        exit

        """
        if not isinstance(cm, AsyncCM):
            cm = self.run(_call_async(cm))
        return self._wrap_context(cm)

    @contextmanager
    def _wrap_context(self, cm: AsyncCM[_T]) -> Iterator[_T]:
        # https://snarky.ca/unravelling-the-with-statement/

        aenter = type(cm).__aenter__
        aexit = type(cm).__aexit__
        value = self.run(aenter(cm))

        try:
            yield value
        except BaseException:
            if not self.run(aexit(cm, *sys.exc_info())):
                raise
        else:
            self.run(aexit(cm, None, None, None))

    def enter_context(self, cm: AsyncCM[_T] | Callable[[], AsyncCM[_T]], /) -> _T:
        """Enter an async context manager and return its value.

        Exit the entered context manager when the runner is closed.

        If a callable is provided, call it in the event loop thread
        and use the returned async context manager instead.

        >>> @asynccontextmanager
        ... async def make_context():
        ...     print('enter')
        ...     yield 'value'
        ...     print('exit')
        ...
        >>> with ThreadRunner() as runner:
        ...     print(runner.enter_context(make_context()))
        ...
        enter
        value
        exit

        """
        wrapped = self.wrap_context(cm)
        return self._stack.enter_context(wrapped)

    def wrap_iter(self, it: AsyncIterable[_T]) -> Iterable[_T]:
        """Convert an async iterable into a sync wrapper.

        >>> async def arange(*args):
        ...     for n in range(*args):
        ...         yield n
        ...
        >>> list(runner.wrap_iter(arange(4)))
        [0, 1, 2, 3]

        """
        it = aiter(it)
        while True:
            try:
                yield self.run(anext(it))  # type: ignore[arg-type]
            except StopAsyncIteration:
                break


async def _call_async(callable: Callable[[], _T]) -> _T:
    return callable()
