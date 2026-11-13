from __future__ import annotations

import os
from types import SimpleNamespace


def test_serve_main_is_importable():
    import serve.__main__ as serve_main

    assert callable(serve_main.main)


def test_refresh_windows_user_credentials_fills_missing_values(monkeypatch):
    import serve.__main__ as serve_main

    values = {
        "GITHUB_TOKENS": "one,two,three,four",
        "GITHUB_TOKEN": "single-token",
    }

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *_exc_info):
            return False

    fake_winreg = SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        OpenKey=lambda _root, _name: Key(),
        QueryValueEx=lambda _key, name: (values[name], 1),
    )
    monkeypatch.setattr(serve_main.os, "name", "nt")
    monkeypatch.setitem(__import__("sys").modules, "winreg", fake_winreg)
    monkeypatch.delenv("GITHUB_TOKENS", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    serve_main.refresh_windows_user_credentials()

    assert os.environ["GITHUB_TOKENS"] == "one,two,three,four"
    assert os.environ["GITHUB_TOKEN"] == "single-token"


def test_refresh_windows_user_credentials_preserves_explicit_process_value(monkeypatch):
    import serve.__main__ as serve_main

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *_exc_info):
            return False

    fake_winreg = SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        OpenKey=lambda _root, _name: Key(),
        QueryValueEx=lambda _key, _name: ("user-profile-value", 1),
    )
    monkeypatch.setattr(serve_main.os, "name", "nt")
    monkeypatch.setitem(__import__("sys").modules, "winreg", fake_winreg)
    monkeypatch.setenv("GITHUB_TOKENS", "explicit-process-value")

    serve_main.refresh_windows_user_credentials()

    assert os.environ["GITHUB_TOKENS"] == "explicit-process-value"
