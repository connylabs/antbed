import os

from antbed.config import config


def test_config_test_env():
    assert config().app.env == "test"


def test_config_fields():
    assert config().sentry.dsn is None
    assert config().server.port == 8080
    assert config().logging.level == "info"
    assert config().conf.app.env == "test"
    assert config().conf.app.prometheus_dir == "/tmp/testprom"
    assert config().conf.name == "antbed-test"


def test_config_reinit():
    conf = config().dump()
    _ = config(reload=True)
    assert config().dump() == conf
    # Changes are ignored without reinit
    config("tests/data/config-2.yaml")
    assert config().dump() == conf
    # Changes are applied after reinit
    config("tests/data/config-2.yaml", reload=True)
    assert config().dump() != conf




def test_config_env_precedence(monkeypatch):
    assert config(reload=True).app.env == "test"
    monkeypatch.setattr(
        os, "environ", {"ANTBED_APP__ENV": "test-3", "ANTBED_CONFIG": "tests/data/test_config.yaml"}
    )
    # Env setting has precedence over config file
    assert config(reload=True).app.env == "test-3"
    # Other env are not affected
    assert config().conf.name == "antbed-test"
    monkeypatch.setattr(
        os, "environ", {"ANTBED_NAME": "antbed-test-3", "ANTBED_CONFIG": "tests/data/test_config.yaml"}
    )
    assert config(reload=True).conf.name == "antbed-test-3"
    assert config(reload=True).conf.app.env == "test"


def test_config_path_failed_path_fallback():
    config("tests/data/config-dontexist.yaml", reload=True)
    assert config().app.env == "dev"
