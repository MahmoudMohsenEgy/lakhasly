from pathlib import Path

class LocalAssetStore:
    def __init__(self, base_dir: str):
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._n = 0

    def allocate(self, suffix: str) -> str:
        self._n += 1
        return str(self._base / f"asset_{self._n}{suffix}")

    def read_bytes(self, path: str) -> bytes:
        return Path(path).read_bytes()

    def write_text(self, path: str, text: str) -> None:
        Path(path).write_text(text, encoding="utf-8")
