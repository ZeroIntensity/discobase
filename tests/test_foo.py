import discobase


# This is a sample test
def test_foo():
    assert isinstance(discobase.__version__, str)
    assert discobase.__license__ == "MIT"
    assert 1 != 2
