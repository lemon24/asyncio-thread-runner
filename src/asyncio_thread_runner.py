"""
Run async Python code from sync code.

"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import threading
from typing import Any
from typing import Self
from typing import TYPE_CHECKING
from typing import TypeVar


if TYPE_CHECKING:
    from collections.abc import AsyncIterable
    from collections.abc import Callable
    from collections.abc import Coroutine
    from collections.abc import Iterable
    from collections.abc import Iterator
    from contextlib import AbstractAsyncContextManager
    from contextlib import AbstractContextManager


__version__ = "0.1.dev0"


_T = TypeVar('_T')


class ThreadRunner:

    def __init__(self, *args: Any, **kwargs: Any):
        self._runner = asyncio.Runner(*args, **kwargs)
        self._thread: threading.Thread | None = None
        self._stack = contextlib.ExitStack()

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
            loop = self.get_loop()
            loop.call_soon_threadsafe(loop.stop)
            thread.join()

    def close(self) -> None:
        self.__exit__(None, None, None)

    def get_loop(self) -> asyncio.AbstractEventLoop:
        self._lazy_init()
        return self._runner.get_loop()

    def run(self, coro: Coroutine[Any, Any, _T]) -> _T:
        loop = self.get_loop()
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

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

    def wrap_context(
        self,
        cm: AbstractAsyncContextManager[_T] | None = None,
        *,
        factory: Callable[[], AbstractAsyncContextManager[_T]] | None = None,
    ) -> AbstractContextManager[_T]:
        if (cm is None) + (factory is None) != 1:
            raise TypeError("exactly one of cm or factory must be given")
        if cm is None:
            assert factory is not None
            cm = self.run(_call_async(factory))
        return self._wrap_context(cm)

    @contextlib.contextmanager
    def _wrap_context(self, cm: AbstractAsyncContextManager[_T]) -> Iterator[_T]:
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

    def enter_context(
        self,
        cm: AbstractAsyncContextManager[_T] | None = None,
        *,
        factory: Callable[[], AbstractAsyncContextManager[_T]] | None = None,
    ) -> _T:
        wrapped = self.wrap_context(cm, factory=factory)
        return self._stack.enter_context(wrapped)

    def wrap_iter(self, it: AsyncIterable[_T]) -> Iterable[_T]:
        it = aiter(it)
        while True:
            try:
                yield self.run(anext(it))  # type: ignore[arg-type]
            except StopAsyncIteration:
                break


async def _call_async(callable: Callable[[], _T]) -> _T:
    return callable()
