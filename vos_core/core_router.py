"""
CORERouter: Central dispatch, self-healing, SAVE3-integrated, synthetic cognitive core.
LLM/Ollama bridge replaced by SyntheticCognitiveCore (v1.0.0).
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .metadata_processor import MetadataEngine
from .rollout_scheduler import RolloutScheduler
from .save3_trust import AuditLedger, SAVE3Trust
from .synthetic_core import SyntheticCognitiveCore
from .version_engine import GodTierVersion

logging.basicConfig(level=logging.INFO, format="[ROUTER] %(message)s")
logger = logging.getLogger(__name__)


class CORERouter:
    def __init__(self, workdir: str = "."):
        self.version = GodTierVersion(str(Path(workdir) / ".vos_version.json"))
        self.audit = AuditLedger(str(Path(workdir) / "vos_audit.jsonl"))
        self.trust = SAVE3Trust(self.audit, confidence_threshold=0.70)
        self.meta_engine = MetadataEngine()
        self.rollout = RolloutScheduler()
        self.synthetic = SyntheticCognitiveCore(
            self.trust, self.audit, self.version, workdir
        )

    def process_input(
        self, raw_input: Dict[str, Any], generate_ai: bool = True
    ) -> Dict[str, Any]:
        version = self.version.version_string
        logger.info(f"Processing input under {version}")

        try:
            meta = self.meta_engine.parse_and_validate(raw_input)
            schedule = self.rollout.generate(meta.get("release_date"))
            ai_prompts = self._generate_prompts(meta)
            trust_status = self.trust.evaluate(
                "core_router",
                "process_complete",
                {"meta_keys": list(meta.keys()), "schedule_days": len(schedule)},
                0.88,
            )

            return {
                "version": version,
                "metadata": meta,
                "rollout_schedule": schedule,
                "ai_prompts": ai_prompts,
                "trust_status": trust_status,
                "audit_log": str(self.audit.log_path),
            }
        except Exception as e:
            logger.critical(f"Router self-heal triggered: {e}")
            self.version.bump("patch", "self_heal")
            return {
                "error": str(e),
                "status": "quarantined",
                "version": self.version.version_string,
            }

    def _generate_prompts(self, meta: Dict[str, Any]) -> Dict[str, str]:
        context = (
            f"{meta['title']} by {meta['artist']} | {meta['genre']} | "
            f"{meta['mood']} | {meta['bpm']}bpm"
        )
        cognitive = self.synthetic.process(context, context)
        prompt_base = self.synthetic.get_synthesis_prompt(cognitive)

        results = {
            "ad_hook": f"{prompt_base} Focus: 15s TikTok. Raw, no filler.",
            "caption_pack": f"{prompt_base} Focus: 3 IG captions + 5 hashtags.",
            "press_pitch": f"{prompt_base} Focus: 4-sentence playlist pitch. Urgent.",
        }
        self.trust.evaluate(
            "synthetic_router",
            "prompt_generation",
            {"prompts": list(results.keys()), "intent": cognitive["intent"]},
            cognitive["confidence"],
        )
        return results
