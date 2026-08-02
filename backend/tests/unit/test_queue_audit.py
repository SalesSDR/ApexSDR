"""Static, end-to-end audit that every ARQ task name referenced anywhere in
the app (enqueue_job/enqueue_task call sites, plus FORCE_ADVANCE_PLAN's
dynamic task names) is actually registered in WorkerSettings.functions.
Regression coverage for the class of bug where a task is enqueued by name
but never registered - ARQ accepts the job silently and it never runs."""
import ast
import os

import app.workers.tasks as tasks_module
from app.workers.main import WorkerSettings

SRC_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src", "app")

REGISTERED_TASK_NAMES = {fn.__name__ for fn in WorkerSettings.functions}


def _iter_python_files():
    for root, _dirs, files in os.walk(SRC_APP_DIR):
        for fn in files:
            if fn.endswith(".py"):
                yield os.path.join(root, fn)


def _literal_enqueue_task_names():
    """Every string literal passed as the task-name arg to enqueue_job()/
    enqueue_task() across the whole backend source tree."""
    found = set()
    for path in _iter_python_files():
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            fname = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
            if fname not in ("enqueue_job", "enqueue_task"):
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.add(first.value)
    return found


def test_every_literal_enqueued_task_name_is_registered():
    names = _literal_enqueue_task_names()
    assert names, "audit found zero enqueue call sites - the scan itself is broken"
    missing = names - REGISTERED_TASK_NAMES
    assert not missing, f"enqueued task name(s) not registered in WorkerSettings.functions: {missing}"


def test_force_advance_plan_task_names_are_registered():
    plan_task_names = {task_name for (_status, task_name, _needs_tenant) in tasks_module.FORCE_ADVANCE_PLAN.values() if task_name}
    missing = plan_task_names - REGISTERED_TASK_NAMES
    assert not missing, f"FORCE_ADVANCE_PLAN references unregistered task name(s): {missing}"


def test_send_email_nudge_task_is_registered():
    assert "send_email_nudge_task" in REGISTERED_TASK_NAMES
