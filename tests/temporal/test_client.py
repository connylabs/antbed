import pytest
from temporalio.client import Client

from antbed.temporal.client import GTClient, TClient


@pytest.mark.asyncio
async def test_tclient_creation():
    client_wrapper = TClient()
    client = await client_wrapper.client()
    assert isinstance(client, Client)
    assert client.config()['service_client'].config.target_host == "localhost:7233"


@pytest.mark.asyncio
async def test_gtclient_singleton():
    # Clear instance for clean test
    GTClient.reinit()
    instance1 = GTClient()
    client1 = await instance1.client()

    instance2 = GTClient()
    client2 = await instance2.client()

    assert instance1 is instance2
    assert client1 is client2
