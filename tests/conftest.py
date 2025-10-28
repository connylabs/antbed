import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalloop.converters.pydantic import pydantic_data_converter

from antbed.config import config

LOCAL_DIR = os.path.dirname(__file__)

def pytest_addoption(parser):
    parser.addoption(
        "--workflow-environment",
        default="local",
        help="Which workflow environment to use ('local', 'time-skipping', or target to existing server)",
    )


@pytest_asyncio.fixture(scope="session")
async def env(request) -> AsyncGenerator[WorkflowEnvironment]:
    env_type = request.config.getoption("--workflow-environment")
    if env_type == "local":
        env = await WorkflowEnvironment.start_local(
            dev_server_extra_args=[
                "--dynamic-config-value",
                "frontend.enableExecuteMultiOperation=true",
            ]
        )
    elif env_type == "time-skipping":
        env = await WorkflowEnvironment.start_time_skipping()
    else:
        env = WorkflowEnvironment.from_client(await Client.connect(env_type))
    yield env
    await env.shutdown()


@pytest_asyncio.fixture
async def client(env: WorkflowEnvironment) -> Client:
    client = env.client
    new_config = client.config()
    new_config["data_converter"] = pydantic_data_converter
    cli = Client(**new_config)
    return cli


@pytest.fixture
def app():
    from antbed.server.server import serve

    app = serve()
    return app


@pytest.fixture(autouse=True)
def reset_config():
    config(reload=True)
