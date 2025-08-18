*you can have a little async (as a treat)*


[![build status](https://github.com/lemon24/asyncio-thread-runner/actions/workflows/tests.yaml/badge.svg)](https://github.com/lemon24/asyncio-thread-runner/actions/workflows/tests.yaml)
[![PyPI status](https://img.shields.io/pypi/v/asyncio-thread-runner.svg)](https://pypi.python.org/pypi/asyncio-thread-runner)


**asyncio-thread-runner** allows you to run async code from sync code.

This is useful when you're doing some sync stuff, but:

* you also need to do some async stuff, **without** making **everything async**
* maybe the sync stuff is an existing application
* maybe you still want to use your favorite sync library
* or maybe you need just a little async, without having to pay the full price

Features:

* unlike [asyncio.run()], it provides a **long-lived event loop**
* unlike [asyncio.Runner], it runs in a dedicated thread, and you can use it from **multiple threads**
* it allows you to use **async context managers** and **iterables** from sync code
* check out [this article](https://death.andgravity.com/asyncio-bridge) for why these are useful


Usage:

```shell
$ pip install asyncio-thread-runner
```

```python
>>> async def double(i):
...     return i * 2
...
>>> from asyncio_thread_runner import ThreadRunner
>>> runner = ThreadRunner()
>>> runner.run(double(2))
4
```


Annotated example:

```python
import aiohttp
from asyncio_thread_runner import ThreadRunner

# you can use ThreadRunner as a context manager,
# or call runner.close() when you're done with it
with ThreadRunner() as runner:

    # aiohttp.ClientSession() should be used as an async context manager,
    # enter_context() will exit the context on runner shutdown;
    # because instantiating ClientSession requires a running event loop,
    # we pass it as a factory instead of calling it in the main thread
    session = runner.enter_context(aiohttp.ClientSession)

    # session.get() returns an async context manager...
    request = session.get('https://death.andgravity.com/asyncio-bridge')
    # which we turn into a normal one with wrap_context()
    with runner.wrap_context(request) as response:

        # response.content is an async iterator;
        # we turn it into a normal iterator with wrap_iter()
        lines = list(runner.wrap_iter(response.content))

    # "got 935 lines"
    print('got', len(lines), 'lines')

```


[asyncio.run()]: https://docs.python.org/3/library/asyncio-runner.html#asyncio.run
[asyncio.Runner]: https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner
