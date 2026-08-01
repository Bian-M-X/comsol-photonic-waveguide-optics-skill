from __future__ import annotations

from typing import Any

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.models import ModelCard, Validity
from photonic_workflow.models.io import revalidate_internal


def validate_model_card(card: ModelCard) -> dict[str, Any]:
    errors: list[str] = []
    if not card.producer:
        errors.append("producer is required")
    if not card.model_source:
        errors.append("model_source is required")
    if not card.validity_envelope:
        errors.append("validity_envelope is required before release")
    if not card.artifact_ids:
        errors.append("at least one source artifact is required before release")
    return {
        "valid": not errors,
        "errors": errors,
        "fidelity": card.fidelity.value,
        "claim_boundary": "model validation applies only inside the recorded validity envelope",
    }


def compare_model_cards(left: ModelCard, right: ModelCard) -> dict[str, Any]:
    return {
        "same_fidelity": left.fidelity == right.fidelity,
        "same_parameter_axes": left.parameter_axes == right.parameter_axes,
        "same_validity_envelope": left.validity_envelope == right.validity_envelope,
        "same_artifacts": left.artifact_ids == right.artifact_ids,
        "left_revision": left.revision,
        "right_revision": right.revision,
    }


def release_model_card(card: ModelCard) -> ModelCard:
    report = validate_model_card(card)
    if not report["valid"]:
        raise InvalidInputError("model card cannot be released: " + "; ".join(report["errors"]))
    payload = card.model_dump()
    payload["status"] = "released"
    payload["validity"] = Validity.VALID
    payload["revision"] = str(int(card.revision) + 1) if card.revision.isdigit() else card.revision
    payload["provenance"] = [*card.provenance, "model-release-validation"]
    return revalidate_internal(ModelCard, payload)
