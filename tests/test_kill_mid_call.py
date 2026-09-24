"""Chapter 29: killing the wrong process should look exactly as
weak as it is: it kills only what was actually asked for."""

import psutil
import pytest

import kill_mid_call


@pytest.fixture
def process_tree():
    started = [
        psutil.Popen(["python", "-c", "import time; time.sleep(30)"])
        for _ in range(2)
    ]
    yield started
    for p in started:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass


def test_wrapper_mode_kills_only_the_named_pid(process_tree):
    target, other = process_tree

    killed = kill_mid_call.kill_worker(target, "wrapper")

    assert killed == [target.pid]
    assert other.is_running()


def test_tree_mode_kills_the_named_pid_and_its_children():
    parent = psutil.Popen(["python", "-c",
        "import subprocess, time; "
        "subprocess.Popen(['python', '-c', 'import time; time.sleep(30)']); "
        "time.sleep(30)"])
    try:
        parent.wait(timeout=1)
    except psutil.TimeoutExpired:
        pass
    children = []
    for _ in range(20):
        children = parent.children(recursive=True)
        if children:
            break
        import time as _t
        _t.sleep(0.1)
    assert children, "the parent never spawned its own child in time"

    killed = kill_mid_call.kill_worker(parent, "tree")
    gone, alive = psutil.wait_procs([parent, *children], timeout=3)

    assert parent.pid in killed
    assert all(c.pid in killed for c in children)
    assert alive == []
    assert len(gone) == 1 + len(children)
