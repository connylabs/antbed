from typer.testing import CliRunner

from antbed.cmd.main import app
from antbed.version import VERSION

runner = CliRunner()




def test_app_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert VERSION.app_version in result.stdout


def test_app_default_config():
    result = runner.invoke(app, ["default-config"])
    assert result.exit_code == 0
    assert "antbed:" in result.stdout
    assert "server:" in result.stdout
    assert "temporalio:" in result.stdout


def test_tikcount():
    result = runner.invoke(app, ["tikcount"], input="hello world")
    assert result.exit_code == 0
    assert '"tokens": 2' in result.stdout
    assert '"model": "gpt-4o"' in result.stdout


def test_tikcount_text_output():
    result = runner.invoke(app, ["tikcount", "--output", "text"], input="hello world")
    assert result.exit_code == 0
    assert "2" in result.stdout.strip()
