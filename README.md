# Discobase

*This is a temporary README*

## Installation

### One-Time Installs

You need to run the following commands after running locally:

```
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install pre-commit
$ pre-commit install
$ pip install hatch
$ pip install -e .
```

### Other Commands

- `source .venv/bin/activate`: activates the virtual environment (for Mac and Linux).
- `.\.venv\Scripts\activate`: activates the virtual environment (for Windows).
- `hatch test`: runs unit tests. Note that you need the `TEST_BOT_TOKEN` environment variable set.
- `ruff format`: Formats your code.
