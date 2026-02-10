"""Tests for the VariablesView watch panel functionality."""

from voice_debugger.widgets.variables import VariablesView


def test_add_watch():
    """Adding a variable name puts it in the watched list."""
    view = VariablesView()
    view.add_watch("x")
    assert "x" in view._watched


def test_add_watch_no_duplicates():
    """Adding the same variable twice does not create duplicates."""
    view = VariablesView()
    view.add_watch("x")
    view.add_watch("x")
    assert view._watched.count("x") == 1


def test_remove_watch():
    """Removing a watched variable leaves others intact."""
    view = VariablesView()
    view.add_watch("x")
    view.add_watch("y")
    view.remove_watch("x")
    assert "x" not in view._watched
    assert "y" in view._watched


def test_remove_watch_nonexistent():
    """Removing a variable that is not watched does not crash."""
    view = VariablesView()
    view.remove_watch("z")  # should not crash
    assert view._watched == []


def test_watched_list_ordering():
    """Watched variables preserve insertion order."""
    view = VariablesView()
    view.add_watch("a")
    view.add_watch("b")
    view.add_watch("c")
    assert view._watched == ["a", "b", "c"]


def test_remove_then_readd():
    """A variable can be re-added after removal."""
    view = VariablesView()
    view.add_watch("x")
    view.remove_watch("x")
    view.add_watch("x")
    assert view._watched == ["x"]
