"""MonitoringService — read-only aggregation over AuditStore.

Provides summary statistics and interaction detail for operator visibility.
Reads exclusively from AuditStore. Never creates, modifies, or deletes records.

Architecture:

    AuditStore → MonitoringService → Monitoring API

The service scans persisted AuditRecords and computes:
- Total interactions checked
- Findings by dimension (Performance, Cost, Responsibility)
- Terminal decisions (ALLOW, MODIFY, BLOCK, ESCALATE)
- Latency (when available from MODEL_RUNTIME observation)
- Interaction detail with findings, decisions, intervention, outcome
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from controlplane.persistence.audit_store import AuditStore
from controlplane.schemas.audit_record import AuditRecord
from controlplane.schemas.enums import DecisionAction, FindingDimension, InterventionAction

logger = logging.getLogger(__name__)


class MonitoringService:
    """Read-only monitoring layer over AuditStore.

    Never writes to AuditStore. Never creates detections, decisions,
    or interventions. Strictly a read/query layer.
    """

    def __init__(self, audit_store: AuditStore) -> None:
        """Initialize with an existing AuditStore.

        Args:
            audit_store: The durable JSON AuditStore to read from.
        """
        self._audit_store = audit_store

    def get_summary(self) -> dict[str, Any]:
        """Compute aggregate summary across all persisted interactions.

        Returns:
            Dict with total_interactions, findings_by_dimension,
            decisions, and latency stats.
        """
        records = self._load_all_records()

        total = len(records)

        # Findings by dimension
        performance_findings = 0
        cost_findings = 0
        responsibility_findings = 0

        # Findings by state within each dimension
        performance_states: dict[str, int] = {}
        cost_states: dict[str, int] = {}
        responsibility_states: dict[str, int] = {}

        # Terminal decisions
        allow_count = 0
        modify_count = 0
        block_count = 0
        escalate_count = 0

        # Latency
        model_latencies: list[float] = []
        controlplane_latencies: list[float] = []
        total_latencies: list[float] = []

        for record in records:
            # Count findings by dimension
            for finding in record.findings:
                dim = finding.dimension
                state_val = finding.state.value

                if dim == FindingDimension.PERFORMANCE:
                    performance_findings += 1
                    performance_states[state_val] = performance_states.get(state_val, 0) + 1
                elif dim == FindingDimension.COST:
                    cost_findings += 1
                    cost_states[state_val] = cost_states.get(state_val, 0) + 1
                elif dim == FindingDimension.RESPONSIBILITY:
                    responsibility_findings += 1
                    responsibility_states[state_val] = responsibility_states.get(state_val, 0) + 1

            # Terminal decision
            final_decision = self._get_terminal_decision(record)
            intervention_action = self._get_intervention_action(record)

            if intervention_action == InterventionAction.MODIFY:
                modify_count += 1
            elif final_decision == DecisionAction.BLOCK:
                block_count += 1
            elif final_decision == DecisionAction.ESCALATE:
                escalate_count += 1
            else:
                allow_count += 1

            # Latency from MODEL_RUNTIME observation
            latency = self._extract_latency(record)
            if latency is not None:
                model_latencies.append(latency.get("model_latency_ms", 0))
                controlplane_latencies.append(latency.get("controlplane_latency_ms", 0))
                total_latencies.append(latency.get("total_latency_ms", 0))

        return {
            "total_interactions": total,
            "findings": {
                "performance": performance_findings,
                "cost": cost_findings,
                "responsibility": responsibility_findings,
            },
            "performance_states": performance_states,
            "cost_states": cost_states,
            "responsibility_states": responsibility_states,
            "decisions": {
                "allow": allow_count,
                "modify": modify_count,
                "block": block_count,
                "escalate": escalate_count,
            },
            "latency": {
                "model_latency_ms": {
                    "min": min(model_latencies) if model_latencies else None,
                    "max": max(model_latencies) if model_latencies else None,
                    "avg": sum(model_latencies) / len(model_latencies) if model_latencies else None,
                    "count": len(model_latencies),
                },
                "controlplane_latency_ms": {
                    "min": min(controlplane_latencies) if controlplane_latencies else None,
                    "max": max(controlplane_latencies) if controlplane_latencies else None,
                    "avg": sum(controlplane_latencies) / len(controlplane_latencies) if controlplane_latencies else None,
                    "count": len(controlplane_latencies),
                },
                "total_latency_ms": {
                    "min": min(total_latencies) if total_latencies else None,
                    "max": max(total_latencies) if total_latencies else None,
                    "avg": sum(total_latencies) / len(total_latencies) if total_latencies else None,
                    "count": len(total_latencies),
                },
            },
        }

    def list_interactions(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        use_case: str | None = None,
        dimension: str | None = None,
        decision: str | None = None,
        model: str | None = None,
    ) -> list[dict[str, Any]]:
        """List recent interactions with optional filtering.

        Returns lightweight interaction summaries for operator review.
        """
        records = self._load_all_records()

        results = []
        for record in records:
            # Apply filters
            if use_case is not None:
                if record.interaction.context.use_case != use_case:
                    continue

            if dimension is not None:
                has_dimension = any(
                    f.dimension.value == dimension for f in record.findings
                )
                if not has_dimension:
                    continue

            if decision is not None:
                terminal = self._get_terminal_decision(record)
                intervention = self._get_intervention_action(record)
                if decision == "modify":
                    if intervention != InterventionAction.MODIFY:
                        continue
                elif terminal.value != decision:
                    continue

            if model is not None:
                if record.interaction.model != model:
                    continue

            terminal_decision = self._get_terminal_decision(record)
            intervention_action = self._get_intervention_action(record)

            results.append(
                {
                    "interaction_id": str(record.interaction_id),
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "model": record.interaction.model,
                    "provider": record.interaction.provider,
                    "use_case": record.interaction.context.use_case,
                    "decision": terminal_decision.value,
                    "intervention": intervention_action.value if intervention_action else None,
                    "findings_count": len(record.findings),
                    "has_findings": len(record.findings) > 0,
                    "dimensions": list(set(
                        f.dimension.value for f in record.findings
                    )),
                }
            )

        # Sort by created_at descending
        results.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return results[offset : offset + limit]

    def get_interaction(self, interaction_id: UUID) -> dict[str, Any] | None:
        """Get full detail for a single interaction.

        Returns the complete audit record data, or None if not found.
        """
        record = self._audit_store.get(interaction_id)
        if record is None:
            return None

        terminal_decision = self._get_terminal_decision(record)
        intervention_action = self._get_intervention_action(record)

        # Findings by dimension
        findings_by_dimension: dict[str, list[dict[str, Any]]] = {}
        for finding in record.findings:
            dim = finding.dimension.value
            if dim not in findings_by_dimension:
                findings_by_dimension[dim] = []
            findings_by_dimension[dim].append(
                {
                    "finding_id": str(finding.finding_id),
                    "detector_id": finding.detector_id,
                    "detector_version": finding.detector_version,
                    "dimension": finding.dimension.value,
                    "finding_type": finding.finding_type,
                    "state": finding.state.value if hasattr(finding.state, "value") else str(finding.state),
                    "explanation": finding.explanation,
                    "evidence": finding.evidence.model_dump() if finding.evidence else None,
                    "measurement": finding.measurement.model_dump() if finding.measurement else None,
                }
            )

        # Decision history
        decision_history = []
        for d in record.decisions:
            decision_history.append(
                {
                    "decision_id": str(d.decision_id),
                    "decision": d.decision.value,
                    "reason_codes": d.reason_codes,
                    "required_assurance": d.required_assurance,
                    "current_assurance": d.current_assurance,
                    "selected_verifier": d.selected_verifier,
                }
            )

        # Intervention
        intervention_detail = None
        if record.intervention:
            intervention_detail = {
                "intervention_id": str(record.intervention.intervention_id),
                "action": record.intervention.action.value,
                "modification_type": record.intervention.modification_type,
                "modification_detail": record.intervention.modification_detail,
                "blocked_reason": record.intervention.blocked_reason,
                "escalation_reason": record.intervention.escalation_reason,
            }

        # Outcome
        outcome_detail = None
        if record.outcome:
            outcome_detail = {
                "outcome_id": str(record.outcome.outcome_id),
                "outcome_type": record.outcome.outcome_type,
                "description": record.outcome.description,
                "evidence": record.outcome.evidence,
            }

        # Latency
        latency = self._extract_latency(record)

        return {
            "interaction_id": str(record.interaction_id),
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "model": record.interaction.model,
            "provider": record.interaction.provider,
            "use_case": record.interaction.context.use_case,
            "request_text": record.interaction.request_text,
            "response_text": record.interaction.response_text,
            "context": {
                "use_case": record.interaction.context.use_case,
                "consequence": record.interaction.context.consequence.value,
                "reversibility": record.interaction.context.reversibility.value,
                "downstream_action": record.interaction.context.downstream_action.value,
                "data_sensitivity": record.interaction.context.data_sensitivity.value,
                "latency_budget_ms": record.interaction.context.latency_budget_ms,
            },
            "findings": [
                {
                    "finding_id": str(f.finding_id),
                    "interaction_id": str(record.interaction.interaction_id),
                    "detector_id": f.detector_id,
                    "detector_version": f.detector_version,
                    "dimension": f.dimension.value,
                    "finding_type": f.finding_type,
                    "state": f.state.value if hasattr(f.state, "value") else str(f.state),
                    "observation_ids": [str(oid) for oid in f.observation_ids] if f.observation_ids else [],
                    "explanation": f.explanation,
                    "latency_ms": f.latency_ms,
                    "cost_usd": f.cost_usd,
                    "detected_at": f.detected_at.isoformat() if f.detected_at else None,
                    "evidence": {
                        "claim_text": f.evidence.claim_text,
                        "source_ids": f.evidence.source_ids,
                        "source_quality": f.evidence.source_quality,
                        "counter_evidence": f.evidence.counter_evidence,
                        "quality_assessment": f.evidence.quality_assessment,
                    },
                    "measurement": {
                        "input_tokens": f.measurement.input_tokens,
                        "output_tokens": f.measurement.output_tokens,
                        "model_calls": f.measurement.model_calls,
                        "tool_calls": f.measurement.tool_calls,
                        "latency_ms": f.measurement.latency_ms,
                        "estimated_cost_usd": f.measurement.estimated_cost_usd,
                    },
                    "ambiguity": {
                        "reasons": f.ambiguity.reasons,
                        "conflicting_sources": f.ambiguity.conflicting_sources,
                        "evidence_gaps": f.ambiguity.evidence_gaps,
                    },
                }
                for f in record.findings
            ] if record.findings else [],
            "findings_by_dimension": findings_by_dimension,
            "decision_history": decision_history,
            "terminal_decision": terminal_decision.value,
            "intervention": intervention_detail,
            "outcome": outcome_detail,
            "verification_events": record.verification_events,
            "latency": latency,
            "policy_id": str(record.policy_id),
            "policy_version": record.policy_version,
            "policy_snapshot": record.policy_snapshot,
            "released_response": record.released_response,
            "audit_id": str(record.audit_id),
            "frozen_v1_version": record.frozen_v1_version,
        }

    def _load_all_records(self) -> list[AuditRecord]:
        """Load all non-corrupt AuditRecords from the store."""
        records = []
        for file_path in sorted(self._audit_store.storage_dir.glob("*.json")):
            try:
                import json
                json_str = file_path.read_text(encoding="utf-8")
                data = json.loads(json_str)
                record = AuditRecord.model_validate(data)
                records.append(record)
            except Exception as exc:
                logger.warning("Skipping corrupt audit file %s: %s", file_path, exc)
                continue
        # Sort by created_at descending
        records.sort(key=lambda r: r.created_at or r.interaction.created_at, reverse=True)
        return records

    @staticmethod
    def _get_terminal_decision(record: AuditRecord) -> DecisionAction:
        """Extract the terminal decision from an AuditRecord."""
        if record.interaction.final_decision_id:
            for d in record.decisions:
                if d.decision_id == record.interaction.final_decision_id:
                    return d.decision
        # Fallback: last decision
        if record.decisions:
            return record.decisions[-1].decision
        return DecisionAction.ALLOW

    @staticmethod
    def _get_intervention_action(record: AuditRecord) -> InterventionAction | None:
        """Extract the intervention action from an AuditRecord."""
        if record.intervention:
            return record.intervention.action
        return None

    @staticmethod
    def _extract_latency(record: AuditRecord) -> dict[str, float] | None:
        """Extract latency from MODEL_RUNTIME observation, if present."""
        for obs in record.observations:
            if obs.observation_type.value == "model_runtime":
                payload = obs.payload
                if isinstance(payload, dict):
                    return {
                        "model_latency_ms": payload.get("model_latency_ms", 0),
                        "controlplane_latency_ms": payload.get("controlplane_latency_ms", 0),
                        "total_latency_ms": payload.get("total_latency_ms", 0),
                    }
        return None
