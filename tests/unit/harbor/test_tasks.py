import json
import os
from pathlib import Path
from typing import Any

import pytest

TASKS_DIR = Path(__file__).resolve().parents[3] / "evals" / "harbor" / "tasks"
# Benchmark datasets of single-reply tasks, with the task name prefix and fixture each uses.
DATASETS = {
    "trail-benchmark-dev": ("trail-benchmark", "trail"),
    "sql-benchmark-dev": ("sql-benchmark", "sql-benchmark"),
    "api-benchmark-dev": ("api-benchmark", "sql-benchmark"),
}
TASKS = sorted(
    path for dataset in DATASETS for path in (TASKS_DIR / dataset).iterdir() if path.is_dir()
)
REFERENCE = TASKS[0]


def _expected(task: Path) -> dict[str, Any]:
    spec: dict[str, Any] = json.loads((task / "tests" / "expected.json").read_text())
    return spec


def _task_config(task: Path) -> tuple[str, str, str]:
    """The task.toml split into its header, its [task] block, and the shared remainder
    with the fixture name blanked so tasks from different datasets compare equal."""
    header, metadata, shared = (task / "task.toml").read_text().split("\n\n", 2)
    _, fixture = DATASETS[task.parent.name]
    return header, metadata, shared.replace(f'fixture = "{fixture}"', 'fixture = ""')


@pytest.mark.parametrize("task", TASKS, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_task_layout_matches_the_shared_files(task: Path) -> None:
    for name in (".gitignore", "tests/test.sh"):
        assert (task / name).read_bytes() == (REFERENCE / name).read_bytes(), name
    header, metadata, shared = _task_config(task)
    reference_header, _, reference_shared = _task_config(REFERENCE)
    assert (header, shared) == (reference_header, reference_shared), "task.toml"
    assert metadata.startswith("[task]\n")
    prefix, fixture = DATASETS[task.parent.name]
    assert f'name = "arize/{prefix}-{task.name}"' in metadata
    assert "keywords" not in metadata
    assert f'fixture = "{fixture}"' in (task / "task.toml").read_text()
    assert 'user = "agent"' in shared
    for name in ("tests/test.sh", "solution/solve.sh"):
        assert os.access(task / name, os.X_OK), f"{name} is not executable"
    assert "environment/" in (task / ".gitignore").read_text().splitlines(), (
        "the staged environment/ must stay out of git and out of the task digest"
    )
    for path in (task / "environment").rglob("*") if (task / "environment").exists() else []:
        assert not path.is_symlink(), f"{path} is a symlink; Docker cannot build from one"
    instruction = (task / "instruction.md").read_text()
    assert "answer.txt" not in instruction, "the reply is graded, not an answer file"
    assert instruction.endswith("\n") and not instruction.endswith("\n\n")


@pytest.mark.parametrize("task", TASKS, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_expected_answer_is_well_formed(task: Path) -> None:
    spec = _expected(task)
    assert spec["source"], "say how the reference value was derived"
    kinds = [key for key in ("exact", "reference") if key in spec]
    assert len(kinds) == 1, "expected.json needs exactly one of 'exact' or 'reference'"
    assert isinstance(spec[kinds[0]], str) and spec[kinds[0]].strip()
    assert set(spec) <= {"exact", "reference", "notes", "source"}, "unknown keys"
