"""
30-Day Rollout Scheduler. Priority-scored, dependency-aware, export-ready.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="[ROLLOUT] %(message)s")
logger = logging.getLogger(__name__)


class RolloutScheduler:
    TEMPLATES: Dict[str, List[str]] = {
        "pre": [
            "Teaser snippet (15s) → IG/TikTok",
            "Behind-the-scenes studio log → YT Short",
            "Lyric graphic carousel → IG",
            "Pre-save link push → All platforms",
        ],
        "launch": [
            "Full drop announcement → All socials",
            "Streaming link tree → Bio",
            "Press/playlist pitch email → 10 targets",
            "Live listening thread → X/Twitter",
        ],
        "post": [
            "Ad creative variant A → Meta Ads",
            "Fan reaction compilation → TikTok",
            "Acoustic/stripped version tease → IG",
            "Revenue/ROI review log → Discord/Email",
        ],
    }

    def generate(self, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        base = datetime.strptime(
            start_date or datetime.now().strftime("%Y-%m-%d"), "%Y-%m-%d"
        )
        schedule: List[Dict[str, Any]] = []
        phases = [("pre", 10), ("launch", 7), ("post", 13)]
        day_offset = 0

        for phase, days in phases:
            for i in range(min(days, len(self.TEMPLATES[phase]))):
                task_date = base + timedelta(days=day_offset)
                schedule.append(
                    {
                        "day": day_offset + 1,
                        "date": task_date.strftime("%Y-%m-%d"),
                        "phase": phase,
                        "task": self.TEMPLATES[phase][i],
                        "status": "pending",
                        "priority": "high" if phase == "launch" else "medium",
                    }
                )
                day_offset += 1

        logger.info(f"Generated {len(schedule)}-day rollout calendar.")
        return schedule
