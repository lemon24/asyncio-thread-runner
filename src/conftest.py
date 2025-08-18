from contextlib import asynccontextmanager

import pytest

from asyncio_thread_runner import ThreadRunner


@pytest.fixture(autouse=True)
def setup_doctest_namespace(request, doctest_namespace):
    runner = ThreadRunner()
    request.addfinalizer(runner.close)
    doctest_namespace['runner'] = runner
    doctest_namespace['asynccontextmanager'] = asynccontextmanager
