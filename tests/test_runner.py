import asyncio
import warnings
from contextlib import closing
from contextlib import contextmanager
from contextlib import nullcontext

import pytest

from asyncio_thread_runner import ThreadRunner


async def double(i):
    return i * 2


async def arange(*args):
    for n in range(*args):
        yield n


def identity(x):
    return x


@pytest.mark.parametrize('closing', [identity, closing])
def test_lifecycle(closing):
    runner = ThreadRunner()

    with closing(runner) as target:
        assert target is runner
        assert runner.get_loop() is runner._runner.get_loop()

    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', ".* never awaited")
        with pytest.raises(RuntimeError, match="closed"):
            runner.get_loop()
        with pytest.raises(RuntimeError, match="closed"):
            runner.run(double(2))
        with pytest.raises(RuntimeError, match="closed"):
            runner.wrap_context(nullcontext()).__enter__()
        with pytest.raises(RuntimeError, match="closed"):
            runner.enter_context(nullcontext())


def test_close_calls_exit(monkeypatch):
    def exit(self, *args):
        exit.args = args

    monkeypatch.setattr(ThreadRunner, '__exit__', exit)
    ThreadRunner().close()
    assert exit.args == (None, None, None)


def test_close_repeatedly_is_noop():
    runner = ThreadRunner()
    runner.run(double(2))
    runner.close()
    runner.close()


@pytest.fixture
def runner():
    with ThreadRunner() as runner:
        yield runner


def test_run(runner):
    assert runner.run(double(2)) == 4


def test_wrap_iter(runner):
    even = runner.wrap_iter(arange(0, 6, 2))
    odd = runner.wrap_iter(arange(1, 6, 2))
    assert list(zip(even, odd)) == [(0, 1), (2, 3), (4, 5)]


class make_context:
    def __init__(self, suppress=False):
        self.suppress = suppress
        self.states = []
        self.exc_info = None

    async def __aenter__(self):
        self.states.append('entered')
        return 'target'

    async def __aexit__(self, *exc_info):
        self.states.append('exited')
        self.exc_info = exc_info
        return self.suppress

    def check_exc_info(self, exc):
        exc_type, exc_value, traceback = self.exc_info
        assert exc_type is type(exc)
        assert exc_value is exc
        assert exc.__traceback__ in walk_traceback(traceback)


def walk_traceback(tb):
    rv = []
    while tb:
        rv.append(tb)
        tb = tb.tb_next
    return rv


def _wrap_context(runner):
    return runner.wrap_context


def _enter_context(runner):
    def outer(*args, **kwargs):
        rv = runner.enter_context(*args, **kwargs)

        @contextmanager
        def inner():
            with runner:
                yield rv

        return inner()

    return outer


@pytest.fixture(params=[_wrap_context, _enter_context])
def wrap_context(runner, request):
    return request.param(runner)


def test_wrap_context(wrap_context):
    context = make_context()
    wrapped = wrap_context(context)

    with wrapped as target:
        assert target == 'target'
        assert context.states == ['entered']

    assert context.states == ['entered', 'exited']
    assert context.exc_info == (None, None, None)


def test_wrap_context_factory(runner, wrap_context):
    context = None

    def factory():
        nonlocal context
        context = make_context()
        assert asyncio.get_running_loop() is runner.get_loop()
        return context

    wrapped = wrap_context(factory=factory)

    with wrapped as target:
        assert target == 'target'
        assert context.states == ['entered']

    assert context.states == ['entered', 'exited']
    assert context.exc_info == (None, None, None)


def test_wrap_context_propagate_exception(wrap_context):
    exc = BaseException('propagate')
    context = make_context()
    with pytest.raises(BaseException) as excinfo:
        with wrap_context(context):
            raise exc
    assert excinfo.value is exc
    context.check_exc_info(exc)


def test_wrap_context_suppress_exception(wrap_context):
    exc = BaseException('suppress')
    context = make_context(suppress=True)
    with wrap_context(context):
        raise exc
    context.check_exc_info(exc)


def test_wrap_context_no_args(wrap_context):
    with pytest.raises(TypeError, match='exactly one'):
        wrap_context()


def test_wrap_context_too_many_args(wrap_context):
    with pytest.raises(TypeError, match='exactly one'):
        wrap_context(nullcontext(), factory=nullcontext)
