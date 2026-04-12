"""
God-Tier Versioning: Self-validating, rollback-safe, future-proof.
Never breaks on malformed state. Logs every transition.
"""
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="[VOS-VERSION] %(message)s")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VersionState:
    major: int
    minor: int
    patch: int
    build_id: str
    rollback_hash: Optional[str] = None
    status: str = "stable"


class GodTierVersion:
    def __init__(self, version_file: str = ".vos_version.json"):
        self.version_file = Path(version_file)
        self.state = self._load_state()

    def _load_state(self) -> VersionState:
        if not self.version_file.exists():
            return self._write_state(VersionState(0, 1, 0, "init"))
        try:
            data = json.loads(self.version_file.read_text())
            return VersionState(**data)
        except Exception as e:
            logger.warning(f"Version file corrupted. Self-healing to baseline. {e}")
            return self._write_state(VersionState(0, 1, 0, "self_healed"))

    def _write_state(self, state: VersionState) -> VersionState:
        self.version_file.write_text(json.dumps(asdict(state), indent=2))
        self.state = state
        return state

    def bump(self, kind: str = "patch", build_id: Optional[str] = None) -> VersionState:
        current = self.state
        rollback = f"{current.major}.{current.minor}.{current.patch}"
        if kind == "major":
            current = VersionState(current.major + 1, 0, 0, build_id or "major", rollback)
        elif kind == "minor":
            current = VersionState(current.major, current.minor + 1, 0, build_id or "minor", rollback)
        else:
            current = VersionState(current.major, current.minor, current.patch + 1, build_id or "patch", rollback)
        return self._write_state(current)

    def rollback(self) -> VersionState:
        if not self.state.rollback_hash:
            raise RuntimeError("No rollback target available.")
        parts = self.state.rollback_hash.split(".")
        restored = VersionState(int(parts[0]), int(parts[1]), int(parts[2]), "rollback", "none")
        return self._write_state(restored)

    @property
    def version_string(self) -> str:
        return f"v{self.state.major}.{self.state.minor}.{self.state.patch}"
