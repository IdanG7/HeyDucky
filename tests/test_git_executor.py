"""Tests for git command executor with safety constraints."""

import pytest

from heyducky.git_executor import GitCommandBlocked, GitExecutor


def test_status_allowed():
    """'status' is an allowed git subcommand."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("status")


def test_diff_allowed():
    """'diff --staged' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("diff --staged")


def test_log_allowed():
    """'log --oneline -5' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("log --oneline -5")


def test_add_allowed():
    """'add .' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("add .")


def test_commit_allowed():
    """'commit -m message' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("commit -m 'fix bug'")


def test_branch_allowed():
    """'branch' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("branch")


def test_stash_allowed():
    """'stash' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("stash")


def test_blame_allowed():
    """'blame file.py' is allowed."""
    executor = GitExecutor("/tmp")
    assert executor.is_allowed("blame file.py")


def test_push_blocked():
    """'push' is blocked."""
    executor = GitExecutor("/tmp")
    assert not executor.is_allowed("push")


def test_push_force_blocked():
    """'push --force' is blocked."""
    executor = GitExecutor("/tmp")
    assert not executor.is_allowed("push --force")


def test_reset_hard_blocked():
    """'reset --hard' is blocked."""
    executor = GitExecutor("/tmp")
    assert not executor.is_allowed("reset --hard")


def test_clean_f_blocked():
    """'clean -f' is blocked."""
    executor = GitExecutor("/tmp")
    assert not executor.is_allowed("clean -f")


def test_rebase_blocked():
    """'rebase' is blocked."""
    executor = GitExecutor("/tmp")
    assert not executor.is_allowed("rebase")


def test_empty_command_blocked():
    """Empty string is blocked."""
    executor = GitExecutor("/tmp")
    assert not executor.is_allowed("")


def test_run_blocked_raises(tmp_path):
    """Running a blocked command raises GitCommandBlocked."""
    executor = GitExecutor(str(tmp_path))
    with pytest.raises(GitCommandBlocked):
        executor.run("push origin main")


def test_output_truncation(tmp_path):
    """Output is truncated to max_output_chars."""
    executor = GitExecutor(str(tmp_path), max_output_chars=20)
    result = executor.run("version")
    # git version string is typically > 20 chars
    assert len(result) <= 20 + len("\n... (output truncated)")


def test_run_returns_string(tmp_path):
    """run() returns a string."""
    executor = GitExecutor(str(tmp_path))
    result = executor.run("version")
    assert isinstance(result, str)
    assert "git version" in result.lower() or "error" in result.lower()
