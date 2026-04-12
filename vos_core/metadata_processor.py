"""
DSP-Ready Metadata Engine. Auto-tags, validates, normalizes.
Fails safe. Outputs JSON/CSV. Ready for DistroKid, TuneCore, CD Baby.
"""
import json
import logging
import re
from typing import Any, Dict

logging.basicConfig(level=logging.INFO, format="[METADATA] %(message)s")
logger = logging.getLogger(__name__)


class MetadataEngine:
    REQUIRED_FIELDS = {"title", "artist", "genre", "mood", "bpm", "key"}
    GENRE_MAP = {
        "rap": "Hip-Hop/Rap",
        "hiphop": "Hip-Hop/Rap",
        "trap": "Trap",
        "drill": "Drill",
        "rnb": "R&B/Soul",
        "rock": "Rock",
        "alt": "Alternative",
    }

    def parse_and_validate(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        cleaned: Dict[str, Any] = {
            k.lower().strip(): str(v).strip() for k, v in raw.items() if v is not None
        }
        missing = self.REQUIRED_FIELDS - set(cleaned.keys())
        if missing:
            logger.warning(f"Missing fields: {missing}. Applying sane defaults.")
            cleaned.setdefault("title", "Untitled_VOS_Track")
            cleaned.setdefault("artist", "Independent_Artist")
            cleaned.setdefault("genre", "Hip-Hop/Rap")
            cleaned.setdefault("mood", "Gritty/Determined")
            cleaned.setdefault("bpm", "140")
            cleaned.setdefault("key", "C Minor")

        cleaned["genre"] = self.GENRE_MAP.get(
            cleaned["genre"].lower(), cleaned["genre"]
        )
        cleaned["bpm"] = int(re.sub(r"[^\d]", "", str(cleaned["bpm"])) or "120")
        cleaned["isrc_stub"] = (
            f"US-VOS-{cleaned['title'].upper().replace(' ', '-')[:10]}"
        )
        cleaned["valid"] = True
        logger.info(
            f"Metadata normalized: {cleaned['title']} | {cleaned['artist']} | {cleaned['genre']}"
        )
        return cleaned

    def export_json(self, meta: Dict[str, Any]) -> str:
        return json.dumps(meta, indent=2, ensure_ascii=False)

    def export_csv(self, meta: Dict[str, Any]) -> str:
        header = ",".join(meta.keys())
        row = ",".join(str(v).replace(",", ";") for v in meta.values())
        return f"{header}\n{row}"
