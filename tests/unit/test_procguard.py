from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from lib.procguard import contain_process_tree

pytestmark = pytest.mark.skipif(os.name != "nt", reason="windows job object containment")

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_contain_process_tree_is_idempotent():
    assert contain_process_tree() is True
    assert contain_process_tree() is True


def test_killed_parent_leaves_no_orphaned_grandchild(tmp_path):
    script = tmp_path / "contained_parent.py"
    script.write_text(
        "import subprocess\n"
        "import sys\n"
        "import time\n"
        "\n"
        "from lib.procguard import contain_process_tree\n"
        "\n"
        "assert contain_process_tree()\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])\n"
        "print(child.pid, flush=True)\n"
        "time.sleep(300)\n",
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}
    parent = subprocess.Popen(
        [sys.executable, str(script)], stdout=subprocess.PIPE, text=True, env=env
    )
    grandchild_pid = 0
    try:
        line = parent.stdout.readline().strip() if parent.stdout else ""
        assert line, "contained parent never reported its child pid"
        grandchild_pid = int(line)
        subprocess.run(
            ["taskkill", "/F", "/PID", str(parent.pid)], check=False, capture_output=True
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            listing = subprocess.run(
                ["tasklist", "/FI", f"PID eq {grandchild_pid}"],
                check=False,
                capture_output=True,
                text=True,
            )
            if str(grandchild_pid) not in listing.stdout:
                return
            time.sleep(0.5)
        pytest.fail(
            f"grandchild pid {grandchild_pid} survived the hard kill of its contained parent"
        )
    finally:
        if grandchild_pid:
            subprocess.run(
                ["taskkill", "/F", "/PID", str(grandchild_pid)],
                check=False,
                capture_output=True,
            )
        parent.kill()
