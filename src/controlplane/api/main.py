"""FastAPI entry point for uvicorn.

Usage:
    uvicorn controlplane.api.main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import tempfile
from pathlib import Path

from controlplane.api.app import create_full_app
from controlplane.api.live import configure_live_router, router as live_router
from controlplane.detection.cost_detector import CostDetector, CostDetectorConfig
from controlplane.detection.cost_types import CostBudget, DEFAULT_MODEL_PRICING
from controlplane.detection.evidence_retriever import FixtureEvidenceRetriever
from controlplane.detection.secrets_detector import SecretsDetector
from controlplane.detection.unsafe_content_detector import UnsafeContentDetector
from controlplane.runtime.runtime import ControlPlaneRuntime
from controlplane.traffic.interceptor import TrafficInterceptor
from controlplane.verification.registry import VerifierRegistry
from controlplane.verification.source_retrieval import SourceRetrievalVerifier
from controlplane.verification.source_conflict_resolution import SourceConflictResolutionVerifier
from controlplane.persistence.audit_store import AuditStore

_store = AuditStore(tempfile.mkdtemp())
_registry = VerifierRegistry()

_registry.register(SourceRetrievalVerifier())
_registry.register(SourceConflictResolutionVerifier())

_cost_detector = CostDetector(CostDetectorConfig(
    budget=CostBudget(
        max_input_tokens=10000,
        max_output_tokens=4096,
        max_total_tokens=15000,
        max_latency_ms=30000.0,
        max_estimated_cost_usd=0.50,
    ),
    pricing=DEFAULT_MODEL_PRICING,
))
_secrets_detector = SecretsDetector()
_unsafe_content_detector = UnsafeContentDetector()

_corpus_path = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "factual_verification" / "corpus.json"
_evidence_retriever = FixtureEvidenceRetriever(_corpus_path) if _corpus_path.exists() else None

_runtime = ControlPlaneRuntime(
    registry=_registry,
    audit_store=_store,
    cost_detector=_cost_detector,
    secrets_detector=_secrets_detector,
    unsafe_content_detector=_unsafe_content_detector,
    evidence_retriever=_evidence_retriever,
)

_interceptor = TrafficInterceptor(_runtime, max_events=1000)

app = create_full_app(_runtime, audit_store=_store, traffic_interceptor=_interceptor)

# --- Live model adapter ---
_live_model = None
_openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
_openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()

if _openai_key:
    try:
        from controlplane.gateway.openai_adapter import OpenAIAdapter
        _live_model = OpenAIAdapter(
            api_key=_openai_key,
            model=_openai_model,
            max_tokens=1024,
            temperature=0.0,
            timeout=30.0,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to create OpenAI adapter: %s", exc)
        _live_model = None

configure_live_router(runtime=_runtime, model=_live_model)
app.include_router(live_router)
