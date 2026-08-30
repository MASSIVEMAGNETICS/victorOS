"""
VOS Core Module — Victor Operating System for Creators
Version: 0.1.0
SAVE3: Embedded
God-Tier Versioning: Active
"""
__version__ = "0.1.0"
__author__ = "Brandon 'Bando Bandz' Emery | Massive Magnetics"
__license__ = "MIT (Core) / Commercial (UI/Extensions)"

from .version_engine import GodTierVersion
from .save3_trust import SAVE3Trust, AuditLedger
from .metadata_processor import MetadataEngine
from .rollout_scheduler import RolloutScheduler
from .synthetic_core import SyntheticCognitiveCore
from .core_router import CORERouter
from .physiology import (
    CONSTITUTIONAL_INVARIANTS,
    ActionProposal,
    CapabilityLease,
    DecisionStatus,
    GateDecision,
    GovernanceMode,
    PhysiologyReceiptLedger,
    VictorPhysiologyRuntime,
    VictorPhysiologyState,
)

__all__ = [
    "GodTierVersion",
    "SAVE3Trust",
    "AuditLedger",
    "MetadataEngine",
    "RolloutScheduler",
    "SyntheticCognitiveCore",
    "CORERouter",
    "CONSTITUTIONAL_INVARIANTS",
    "ActionProposal",
    "CapabilityLease",
    "DecisionStatus",
    "GateDecision",
    "GovernanceMode",
    "PhysiologyReceiptLedger",
    "VictorPhysiologyRuntime",
    "VictorPhysiologyState",
]
