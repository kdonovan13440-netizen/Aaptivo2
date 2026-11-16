from pathlib import Path
from .config import settings

ROOT = Path(settings.workspace_dir).resolve()

def safe_path(relative: str) -> Path:
    target = (ROOT / relative).resolve()
    if target != ROOT and ROOT not in target.parents:
        raise ValueError("Path is outside the Aptivo workspace.")
    return target

def list_files(relative: str = ".") -> list[str]:
    folder = safe_path(relative)
    folder.mkdir(parents=True, exist_ok=True)
    return [p.name for p in folder.iterdir()]

def read_text(relative: str) -> str:
    path = safe_path(relative)
    if not path.is_file():
        raise FileNotFoundError(relative)
    return path.read_text(encoding="utf-8")

def write_text(relative: str, content: str) -> str:
    path = safe_path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path.relative_to(ROOT))
