from .filesystem import safe_path
import pytest

def test_rejects_path_traversal():
    with pytest.raises(ValueError):
        safe_path("../../etc/passwd")
