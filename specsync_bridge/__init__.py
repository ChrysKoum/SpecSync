"""
SpecSync Bridge - Cross-repository API contract synchronization.

Install: pip install specsync-bridge
Usage: specsync-bridge init --role consumer
"""

__version__ = "0.1.0"
__author__ = "SpecSync Team"

from specsync_bridge.models import (
    Contract,
    Endpoint,
    Model,
    Dependency,
    BridgeConfig,
    SyncResult,
    DriftIssue,
)
from specsync_bridge.sync import SyncEngine, sync_dependency, sync_all
from specsync_bridge.extractor import ContractExtractor, extract_provider_contract
from specsync_bridge.detector import BridgeDriftDetector, detect_drift, detect_all_drift

__all__ = [
    # Models
    "Contract",
    "Endpoint", 
    "Model",
    "Dependency",
    "BridgeConfig",
    "SyncResult",
    "DriftIssue",
    # Sync
    "SyncEngine",
    "sync_dependency",
    "sync_all",
    # Extractor
    "ContractExtractor",
    "extract_provider_contract",
    # Detector
    "BridgeDriftDetector",
    "detect_drift",
    "detect_all_drift",
]
