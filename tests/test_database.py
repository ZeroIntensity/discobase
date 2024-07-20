import discobase


def test_version():
    assert isinstance(discobase.__version__, str)
    assert discobase.__license__ == "MIT"


def test_creation():
    db = discobase.Database("test")
