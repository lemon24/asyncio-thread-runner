"""
Run async Python code from sync code.

"""

import asyncio
import contextlib
import sys
import threading

__version__ = "0.1.dev0"


class ThreadRunner:

    def __init__(self, *args, **kwargs):
        self._runner = asyncio.Runner(*args, **kwargs)
        self._thread = None
        self._stack = contextlib.ExitStack()

    def __enter__(self):
        self._lazy_init()
        return self

    def __exit__(self, *exc_info):
        try:
            return self._stack.__exit__(*exc_info)
        finally:
            loop = self.get_loop()
            loop.call_soon_threadsafe(loop.stop)
            self._thread.join()

    def close(self):
        self.__exit__(None, None, None)

    def get_loop(self):
        self._lazy_init()
        return self._runner.get_loop()

    def run(self, coro):
        loop = self.get_loop()
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    def _lazy_init(self):
        if self._thread:
            return

        loop_created = threading.Event()

        def run_forever():
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

    def wrap_context(self, cm=None, *, factory=None):
        if (cm is None) + (factory is None) != 1:
            raise TypeError("exactly one of cm or factory must be given")
        if cm is None:
            cm = self.run(_call_async(factory))
        return self._wrap_context(cm)

    @contextlib.contextmanager
    def _wrap_context(self, cm):
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

    def enter_context(self, cm=None, *, factory=None):
        cm = self.wrap_context(cm, factory=factory)
        return self._stack.enter_context(cm)

    def wrap_iter(self, it):
        it = aiter(it)
        while True:
            try:
                yield self.run(anext(it))
            except StopAsyncIteration:
                break


async def _call_async(callable):
    return callable()
