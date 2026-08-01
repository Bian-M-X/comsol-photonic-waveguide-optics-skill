from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    INVALID_INPUT = 2
    UNAVAILABLE_CAPABILITY = 3
    INCOMPATIBLE_VERSION = 4
    EXECUTION_FAILURE = 5
    ACCEPTANCE_REJECTED = 6
    SECURITY_VIOLATION = 7
    TIMEOUT = 8


class PhotonicWorkflowError(Exception):
    exit_code = ExitCode.EXECUTION_FAILURE


class InvalidInputError(PhotonicWorkflowError, ValueError):
    exit_code = ExitCode.INVALID_INPUT


class UnavailableCapabilityError(PhotonicWorkflowError):
    exit_code = ExitCode.UNAVAILABLE_CAPABILITY


class IncompatibleVersionError(PhotonicWorkflowError):
    exit_code = ExitCode.INCOMPATIBLE_VERSION


class ExecutionFailureError(PhotonicWorkflowError):
    exit_code = ExitCode.EXECUTION_FAILURE


class AcceptanceRejectedError(PhotonicWorkflowError):
    exit_code = ExitCode.ACCEPTANCE_REJECTED


class SecurityViolationError(PhotonicWorkflowError):
    exit_code = ExitCode.SECURITY_VIOLATION


class WorkflowTimeoutError(PhotonicWorkflowError):
    exit_code = ExitCode.TIMEOUT
