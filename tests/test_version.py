
from antbed import __version__
from antbed.version import VERSION


def test_current_version():
    assert VERSION.app_version == __version__

def test_setversion():
    VERSION.set_version("1.2.3")
    assert VERSION.app_version == "1.2.3"


def test_version_str():
    VERSION.set_version("1.2.3")
    assert str(VERSION).startswith("Running 1.2.3, with CPython")


def test_version_dict():
    VERSION.set_version("1.2.3")
    d = VERSION.to_dict()
    assert d["version"] == "1.2.3"
    assert "sha" in d
    assert "python" in d
    assert "system" in d
    assert "version" in d["python"]
    assert "implementation" in d["python"]

