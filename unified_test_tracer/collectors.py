from pathlib import Path
from typing import List


class FileCollector:

    @staticmethod
    def feature_files(paths: List[str]) -> List[Path]:
        files: List[Path] = []
        for raw_path in paths:
            path = Path(raw_path)
            if not path.exists():
                raise FileNotFoundError(f"Feature path does not exist: {path}")
            if path.is_file() and path.suffix == ".feature":
                files.append(path)
            elif path.is_dir():
                files.extend(sorted(path.rglob("*.feature")))
        return sorted({path.resolve() for path in files})

    @staticmethod
    def xml_files(paths: List[str]) -> List[Path]:
        files: List[Path] = []
        for raw_path in paths:
            path = Path(raw_path)
            if not path.exists():
                continue
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                files.extend(sorted(path.rglob("*.xml")))
        return sorted({path.resolve() for path in files})

    @staticmethod
    def json_files(paths: List[str]) -> List[Path]:
        files: List[Path] = []
        for raw_path in paths:
            path = Path(raw_path)
            if not path.exists():
                continue
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                files.extend(sorted(path.rglob("*.json")))
        return sorted({path.resolve() for path in files})
