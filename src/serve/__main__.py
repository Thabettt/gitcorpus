from __future__ import annotations

import os


def refresh_windows_user_credentials() -> None:
    """Fill missing GitHub credentials from the current Windows user profile.

    Windows processes inherit a snapshot of their parent's environment. A server
    restarted from a terminal opened before ``setx`` (or the equivalent registry
    update) otherwise keeps seeing the old credentials until the terminal itself
    is restarted. Explicit process variables still take precedence.
    """
    if os.name != "nt":
        return
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            for name in ("GITHUB_TOKENS", "GITHUB_TOKEN"):
                if os.environ.get(name, "").strip():
                    continue
                try:
                    value, _value_type = winreg.QueryValueEx(key, name)
                except OSError:
                    continue
                if isinstance(value, str) and value.strip():
                    os.environ[name] = os.path.expandvars(value)
    except OSError:
        return


def main() -> None:
    refresh_windows_user_credentials()

    import uvicorn

    from lib.procguard import contain_process_tree

    contain_process_tree()
    url = os.environ.get("DATABASE_URL")
    if url:
        from sqlalchemy import create_engine

        from serve.executor import recover_orphaned_runs

        engine = create_engine(url)
        try:
            recovered = recover_orphaned_runs(engine)
            if recovered:
                print(f"recovered {recovered} orphaned run(s)")
        finally:
            engine.dispose()
    host = os.environ.get("GITCORPUS_HOST", "127.0.0.1")
    port = int(os.environ.get("GITCORPUS_PORT", "8000"))
    uvicorn.run("serve.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
