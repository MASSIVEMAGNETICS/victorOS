"""
VOS App Registry — Every feature is a first-class App on VictorOS.
Each app module exports APP_META (dict) and render(router) (callable).
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass(frozen=True)
class VOSApp:
    id: str
    name: str
    icon: str
    tagline: str
    category: str   # "creator" | "system"
    render: Callable


def load_registry() -> List[VOSApp]:
    """Import all app modules and return the ordered registry."""
    # Imported here to keep registry construction lazy
    from vos_apps import (
        meta_forge,
        rollout_engine,
        creative_core,
        synth_mind,
        audit_vault,
        admin_portal_app,
    )
    modules = [
        meta_forge,
        rollout_engine,
        creative_core,
        synth_mind,
        audit_vault,
        admin_portal_app,
    ]
    apps = []
    for mod in modules:
        m = mod.APP_META
        apps.append(
            VOSApp(
                id=m["id"],
                name=m["name"],
                icon=m["icon"],
                tagline=m["tagline"],
                category=m["category"],
                render=mod.render,
            )
        )
    return apps
