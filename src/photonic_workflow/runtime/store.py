from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from photonic_workflow.compatibility import (
    CURRENT_RUN_CHECKPOINT_SCHEMA_VERSION,
    CURRENT_RUN_EVENT_SCHEMA_VERSION,
)
from photonic_workflow.exceptions import InvalidInputError, PhotonicWorkflowError
from photonic_workflow.models import (
    AcceptanceResult,
    AcceptanceStatus,
    ArtifactRecord,
    ExecutionStatus,
    ProvenanceRecord,
    RunManifest,
    RunSpec,
)
from photonic_workflow.models.io import (
    atomic_write_text,
    contract_json,
    contract_payload,
    parse_contract,
    revalidate_internal,
)
from photonic_workflow.provenance import sha256_file
from photonic_workflow.security import ensure_within_allowed_roots, validate_safe_label

REQUIRED_RUN_FILES = (
    "run.json",
    "events.jsonl",
    "inputs.json",
    "artifacts.json",
    "provenance.json",
    "acceptance.json",
    "stdout.txt",
    "stderr.txt",
    "checkpoint.json",
)
CHECKPOINT_HASHED_FILES = (
    "run.json",
    "inputs.json",
    "artifacts.json",
    "provenance.json",
    "acceptance.json",
    "events.jsonl",
)
EXECUTION_TRANSITIONS = {
    ExecutionStatus.PLANNED: {ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED},
    ExecutionStatus.RUNNING: {
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    },
    ExecutionStatus.SUCCEEDED: set(),
    ExecutionStatus.FAILED: set(),
    ExecutionStatus.CANCELLED: set(),
}


def new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:12]}"


def _strict_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _valid_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _updated_manifest(manifest: RunManifest, **updates: Any) -> RunManifest:
    payload = manifest.model_dump(mode="python")
    # ``status`` is a serialized legacy projection.  The two authoritative
    # fields below must always be allowed to derive it afresh.
    payload.pop("status", None)
    payload.update(updates)
    return revalidate_internal(RunManifest, payload)


class RunStore:
    """A checkpoint-last, single-writer Phase-A run store.

    Each individual JSON write is atomic. A complete update becomes trusted
    only after its final checkpoint is written and ``recover`` validates every
    hashed structured file. Multiple processes must not mutate the same run.
    """

    def __init__(self, project_root: Path, allowed_roots: list[Path] | None = None) -> None:
        self.project_root = project_root.resolve()
        self.allowed_roots = [root.resolve() for root in (allowed_roots or [self.project_root])]
        ensure_within_allowed_roots(self.project_root, self.allowed_roots)
        self.runs_root = self.project_root / "runs"

    def run_dir(self, run_id: str) -> Path:
        validate_safe_label(run_id)
        return ensure_within_allowed_roots(self.runs_root / run_id, self.allowed_roots)

    def create(self, spec: RunSpec, *, run_id: str | None = None) -> RunManifest:
        selected_id = run_id or new_run_id()
        directory = self.run_dir(selected_id)
        if directory.exists():
            raise InvalidInputError(f"run already exists: {selected_id}")
        self.runs_root.mkdir(parents=True, exist_ok=True)
        staging = ensure_within_allowed_roots(
            self.runs_root / f".{selected_id}.{uuid.uuid4().hex}.tmp",
            self.allowed_roots,
        )
        staging.mkdir()
        try:
            (staging / "runtime").mkdir()
            manifest = RunManifest(
                stable_id=selected_id,
                name=spec.name,
                revision=spec.revision,
                source="photonic runtime",
                provenance=[spec.stable_id],
                validity="unknown",
                run_spec_id=spec.stable_id,
            )
            atomic_write_text(staging / "run.json", contract_json(manifest))
            atomic_write_text(staging / "inputs.json", contract_json(spec))
            atomic_write_text(staging / "artifacts.json", "[]\n")
            atomic_write_text(staging / "provenance.json", "[]\n")
            atomic_write_text(staging / "acceptance.json", "[]\n")
            atomic_write_text(staging / "stdout.txt", "")
            atomic_write_text(staging / "stderr.txt", "")
            atomic_write_text(staging / "events.jsonl", "")
            self._event_in_directory(
                staging,
                "run_created",
                {"run_spec_id": spec.stable_id},
            )
            self._checkpoint_directory(staging, selected_id)
            staging.replace(directory)
            return manifest
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def load(self, run_id: str) -> RunManifest:
        path = self.run_dir(run_id) / "run.json"
        try:
            payload = json.loads(
                path.read_text(encoding="utf-8"),
                parse_constant=_reject_json_constant,
            )
        except FileNotFoundError as exc:
            raise InvalidInputError(f"run not found: {run_id}") from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise InvalidInputError(f"invalid run manifest {path}: {exc}") from exc
        model = parse_contract(payload, "RunManifest")
        assert isinstance(model, RunManifest)
        return model

    def transition_execution(
        self,
        run_id: str,
        target: ExecutionStatus,
        *,
        error: str | None = None,
    ) -> RunManifest:
        manifest = self.load(run_id)
        if target not in EXECUTION_TRANSITIONS[manifest.execution_status]:
            raise InvalidInputError(
                f"invalid run transition: {manifest.execution_status.value} -> {target.value}"
            )
        updates: dict[str, Any] = {"execution_status": target}
        if target == ExecutionStatus.RUNNING:
            updates["started_at"] = datetime.now(UTC)
        elif target == ExecutionStatus.SUCCEEDED:
            updates["finished_at"] = datetime.now(UTC)
            updates["error"] = None
        elif target == ExecutionStatus.FAILED:
            updates["finished_at"] = datetime.now(UTC)
            updates["error"] = error or "execution failed"
        elif target == ExecutionStatus.CANCELLED:
            updates["finished_at"] = datetime.now(UTC)
        manifest = _updated_manifest(manifest, **updates)
        atomic_write_text(self.run_dir(run_id) / "run.json", contract_json(manifest))
        self._event(run_id, "execution_transition", {"target": target.value, "error": error})
        self._checkpoint(run_id)
        return manifest

    def record_artifact(self, run_id: str, artifact: ArtifactRecord) -> ArtifactRecord:
        directory = self.run_dir(run_id)
        artifact_path = ensure_within_allowed_roots(
            self.project_root / artifact.relative_path,
            self.allowed_roots,
        )
        if not artifact_path.is_file():
            raise InvalidInputError(f"artifact file does not exist: {artifact.relative_path}")
        if artifact.sha256 and sha256_file(artifact_path) != artifact.sha256:
            raise InvalidInputError(f"artifact hash mismatch: {artifact.relative_path}")
        records = self._load_list(directory / "artifacts.json")
        records.append(contract_payload(artifact))
        atomic_write_text(directory / "artifacts.json", _strict_json(records))
        manifest = self.load(run_id)
        if artifact.stable_id not in manifest.artifact_ids:
            manifest = _updated_manifest(
                manifest,
                artifact_ids=[*manifest.artifact_ids, artifact.stable_id],
            )
            atomic_write_text(directory / "run.json", contract_json(manifest))
        self._event(run_id, "artifact_recorded", {"artifact_id": artifact.stable_id})
        self._checkpoint(run_id)
        return artifact

    def record_provenance(self, run_id: str, record: ProvenanceRecord) -> None:
        path = self.run_dir(run_id) / "provenance.json"
        records = self._load_list(path)
        records.append(contract_payload(record))
        atomic_write_text(path, _strict_json(records))
        self._event(run_id, "provenance_recorded", {"provenance_id": record.stable_id})
        self._checkpoint(run_id)

    def record_acceptance(self, run_id: str, results: list[AcceptanceResult]) -> RunManifest:
        manifest = self.load(run_id)
        if manifest.execution_status != ExecutionStatus.SUCCEEDED:
            raise InvalidInputError("acceptance can be recorded only after successful execution")
        accepted = bool(results) and all(result.passed for result in results)
        manifest = _updated_manifest(
            manifest,
            acceptance_status=(
                AcceptanceStatus.ACCEPTED if accepted else AcceptanceStatus.REJECTED
            ),
            validity="valid" if accepted else "invalid",
        )
        path = self.run_dir(run_id) / "acceptance.json"
        atomic_write_text(path, _strict_json([contract_payload(item) for item in results]))
        atomic_write_text(self.run_dir(run_id) / "run.json", contract_json(manifest))
        self._event(
            run_id,
            "acceptance_recorded",
            {"acceptance_status": manifest.acceptance_status.value},
        )
        self._checkpoint(run_id)
        return manifest

    def recover(self, run_id: str) -> dict[str, Any]:
        directory = self.run_dir(run_id)
        missing = [name for name in REQUIRED_RUN_FILES if not (directory / name).exists()]
        mismatches: list[str] = []
        checkpoint_path = directory / "checkpoint.json"
        checkpoint: dict[str, Any] = {}
        if checkpoint_path.exists():
            try:
                raw_checkpoint = json.loads(
                    checkpoint_path.read_text(encoding="utf-8"),
                    parse_constant=_reject_json_constant,
                )
                if not isinstance(raw_checkpoint, dict):
                    raise ValueError("checkpoint root must be an object")
                checkpoint = raw_checkpoint
            except (json.JSONDecodeError, ValueError):
                mismatches.append("checkpoint.json is invalid JSON")
            if checkpoint:
                self._validate_checkpoint(
                    run_id,
                    directory,
                    checkpoint,
                    mismatches,
                )

        manifest = self._validate_structured_state(directory, run_id, mismatches)
        return {
            "run_id": run_id,
            "recoverable": not missing and not mismatches,
            "missing": missing,
            "mismatches": mismatches,
            "manifest": contract_payload(manifest) if manifest is not None else None,
        }

    def latest_trusted_run(self) -> RunManifest | None:
        if not self.runs_root.exists():
            return None
        candidates: list[RunManifest] = []
        for directory in self.runs_root.iterdir():
            if not directory.is_dir():
                continue
            try:
                manifest = self.load(directory.name)
            except InvalidInputError:
                continue
            if (
                manifest.execution_status == ExecutionStatus.SUCCEEDED
                and manifest.acceptance_status == AcceptanceStatus.ACCEPTED
                and self.recover(directory.name)["recoverable"]
            ):
                candidates.append(manifest)
        return max(candidates, key=lambda item: item.finished_at or item.created_at) if candidates else None

    @staticmethod
    def _load_list(path: Path) -> list[dict[str, Any]]:
        try:
            payload = json.loads(
                path.read_text(encoding="utf-8"),
                parse_constant=_reject_json_constant,
            )
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            raise InvalidInputError(f"invalid run state file: {path}") from exc
        if not isinstance(payload, list):
            raise InvalidInputError(f"run state file must contain an array: {path}")
        return payload

    def _validate_checkpoint(
        self,
        run_id: str,
        directory: Path,
        checkpoint: dict[str, Any],
        mismatches: list[str],
    ) -> None:
        expected_fields = {"schema_version", "run_id", "updated_at", "hashes"}
        if set(checkpoint) != expected_fields:
            mismatches.append("checkpoint.json fields do not match schema 1.0")
        if checkpoint.get("schema_version") != CURRENT_RUN_CHECKPOINT_SCHEMA_VERSION:
            mismatches.append("checkpoint.json schema_version is incompatible")
        if checkpoint.get("run_id") != run_id:
            mismatches.append("checkpoint.json run_id does not match its directory")
        if not _valid_iso_datetime(checkpoint.get("updated_at")):
            mismatches.append("checkpoint.json updated_at is invalid")

        hashes = checkpoint.get("hashes")
        if not isinstance(hashes, dict):
            mismatches.append("checkpoint.json hashes must be an object")
            return
        expected_names = set(CHECKPOINT_HASHED_FILES)
        actual_names = set(hashes)
        for name in sorted(expected_names - actual_names):
            mismatches.append(f"checkpoint hash is missing: {name}")
        for name in sorted(actual_names - expected_names):
            mismatches.append(f"checkpoint hash is unexpected: {name}")
        for name in sorted(expected_names & actual_names):
            expected = hashes[name]
            if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
                mismatches.append(f"checkpoint hash is invalid: {name}")
                continue
            candidate = directory / name
            if candidate.is_file() and sha256_file(candidate) != expected:
                mismatches.append(f"hash changed: {name}")

    def _validate_structured_state(
        self,
        directory: Path,
        run_id: str,
        mismatches: list[str],
    ) -> RunManifest | None:
        manifest: RunManifest | None = None
        input_spec: RunSpec | None = None
        artifacts: list[ArtifactRecord] | None = None
        acceptance: list[AcceptanceResult] | None = None

        run_path = directory / "run.json"
        if run_path.is_file():
            try:
                manifest = self.load(run_id)
            except (PhotonicWorkflowError, OSError, json.JSONDecodeError, ValueError) as exc:
                mismatches.append(f"run.json is invalid: {exc}")

        inputs_path = directory / "inputs.json"
        if inputs_path.is_file():
            try:
                payload = json.loads(
                    inputs_path.read_text(encoding="utf-8"),
                    parse_constant=_reject_json_constant,
                )
                parsed = parse_contract(payload)
                if not isinstance(parsed, RunSpec):
                    raise InvalidInputError("inputs.json must contain a RunSpec contract")
                input_spec = parsed
            except (PhotonicWorkflowError, OSError, json.JSONDecodeError, ValueError) as exc:
                mismatches.append(f"inputs.json is invalid: {exc}")

        artifacts = self._validate_contract_array(
            directory / "artifacts.json",
            ArtifactRecord,
            "ArtifactRecord",
            mismatches,
        )
        self._validate_contract_array(
            directory / "provenance.json",
            ProvenanceRecord,
            "ProvenanceRecord",
            mismatches,
        )
        acceptance = self._validate_contract_array(
            directory / "acceptance.json",
            AcceptanceResult,
            "AcceptanceResult",
            mismatches,
        )
        self._validate_events(directory / "events.jsonl", mismatches)

        if (
            manifest is not None
            and input_spec is not None
            and manifest.run_spec_id != input_spec.stable_id
        ):
            mismatches.append("run.json run_spec_id does not match inputs.json")
        if manifest is not None and artifacts is not None:
            artifact_ids = [artifact.stable_id for artifact in artifacts]
            if len(artifact_ids) != len(set(artifact_ids)):
                mismatches.append("artifacts.json contains duplicate stable_id values")
            if manifest.artifact_ids != artifact_ids:
                mismatches.append("run.json artifact_ids do not match artifacts.json")
        if manifest is not None and acceptance is not None:
            if manifest.acceptance_status == AcceptanceStatus.PENDING and acceptance:
                mismatches.append(
                    "pending run has acceptance results in acceptance.json"
                )
            if manifest.acceptance_status == AcceptanceStatus.ACCEPTED and (
                not acceptance or not all(result.passed for result in acceptance)
            ):
                mismatches.append(
                    "accepted run requires non-empty passing acceptance results"
                )
            if manifest.acceptance_status == AcceptanceStatus.REJECTED and (
                acceptance and all(result.passed for result in acceptance)
            ):
                mismatches.append(
                    "rejected run cannot contain only passing acceptance results"
                )
        return manifest

    @staticmethod
    def _validate_contract_array(
        path: Path,
        expected_class: type[ArtifactRecord]
        | type[ProvenanceRecord]
        | type[AcceptanceResult],
        expected_type: str,
        mismatches: list[str],
    ) -> list[Any] | None:
        if not path.is_file():
            return None
        try:
            payload = json.loads(
                path.read_text(encoding="utf-8"),
                parse_constant=_reject_json_constant,
            )
            if not isinstance(payload, list):
                raise InvalidInputError("root must be an array")
            records: list[Any] = []
            for index, item in enumerate(payload):
                try:
                    record = parse_contract(item, expected_type)
                except PhotonicWorkflowError as exc:
                    raise InvalidInputError(f"item {index}: {exc}") from exc
                if not isinstance(record, expected_class):
                    raise InvalidInputError(
                        f"item {index} is not {expected_class.__name__}"
                    )
                records.append(record)
            return records
        except (PhotonicWorkflowError, OSError, json.JSONDecodeError, ValueError) as exc:
            mismatches.append(f"{path.name} is invalid: {exc}")
            return None

    @staticmethod
    def _validate_events(path: Path, mismatches: list[str]) -> None:
        if not path.is_file():
            return
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            mismatches.append(f"events.jsonl is invalid: {exc}")
            return
        if not lines:
            mismatches.append("events.jsonl contains no events")
            return
        expected_fields = {"schema_version", "timestamp", "event", "data"}
        for index, line in enumerate(lines, start=1):
            if not line.strip():
                mismatches.append(f"events.jsonl line {index} is blank")
                continue
            try:
                event = json.loads(line, parse_constant=_reject_json_constant)
            except (json.JSONDecodeError, ValueError) as exc:
                mismatches.append(f"events.jsonl line {index} is invalid JSON: {exc}")
                continue
            if not isinstance(event, dict) or set(event) != expected_fields:
                mismatches.append(
                    f"events.jsonl line {index} fields do not match schema 1.0"
                )
                continue
            if event.get("schema_version") != CURRENT_RUN_EVENT_SCHEMA_VERSION:
                mismatches.append(
                    f"events.jsonl line {index} schema_version is incompatible"
                )
            if not _valid_iso_datetime(event.get("timestamp")):
                mismatches.append(f"events.jsonl line {index} timestamp is invalid")
            if not isinstance(event.get("event"), str) or not event["event"].strip():
                mismatches.append(f"events.jsonl line {index} event is invalid")
            if not isinstance(event.get("data"), dict):
                mismatches.append(f"events.jsonl line {index} data must be an object")

    def _event(self, run_id: str, event: str, data: dict[str, Any]) -> None:
        self._event_in_directory(self.run_dir(run_id), event, data)

    @staticmethod
    def _event_in_directory(
        directory: Path,
        event: str,
        data: dict[str, Any],
    ) -> None:
        payload = {
            "schema_version": CURRENT_RUN_EVENT_SCHEMA_VERSION,
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "data": data,
        }
        with (directory / "events.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _checkpoint(self, run_id: str) -> None:
        self._checkpoint_directory(self.run_dir(run_id), run_id)

    @staticmethod
    def _checkpoint_directory(directory: Path, run_id: str) -> None:
        hashes = {
            name: sha256_file(directory / name)
            for name in CHECKPOINT_HASHED_FILES
            if (directory / name).is_file()
        }
        payload = {
            "schema_version": CURRENT_RUN_CHECKPOINT_SCHEMA_VERSION,
            "run_id": run_id,
            "updated_at": datetime.now(UTC).isoformat(),
            "hashes": hashes,
        }
        atomic_write_text(directory / "checkpoint.json", _strict_json(payload))
