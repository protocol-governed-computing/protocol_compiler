"""
exceptions.py — Structured exception types for protocol violations.

Provides uniform error surface for trace integration and violation tracking.

Governed by: CONSTITUTION_STRUCTURE_V0
"""


class StructuredError(Exception):
    """
    Base exception for protocol violations and structural errors.

    Designed for trace system integration - all errors should be categorizable
    and traceable through execution.

    PROTOCOL SURFACE CLOSURE: Errors are first-class protocol citizens.
    Governed by: INVARIANT_NO_UNDECLARED_BEHAVIOR_SURFACE_V0
    """

    def __init__(
        self,
        code: str,
        message: str,
        artifact: str | None = None,
        location: str | None = None,
        details: dict | None = None,
    ):
        """
        Initialize structured error.

        Args:
            code: Error code (e.g., "PROTOCOL_INCOMPLETE", "DOMAIN_REQUIRED")
            message: Human-readable error message
            artifact: Artifact code where error occurred (if applicable)
            location: Location within artifact (e.g., "pipeline[0].capability")
            details: Additional context for debugging
        """
        self.code = code
        self.message = message
        self.artifact = artifact
        self.location = location
        self.details = details or {}

        # Construct exception message
        parts = [f"{code}: {message}"]

        if artifact:
            parts.append(f"Artifact: {artifact}")

        if location:
            parts.append(f"Location: {location}")

        if details:
            parts.append(f"Details: {details}")

        super().__init__(" | ".join(parts))

    def to_dict(self) -> dict:
        """Convert to dictionary for trace logging."""
        return {
            "error_code": self.code,
            "message": self.message,
            "artifact": self.artifact,
            "location": self.location,
            "details": self.details,
        }


class ProtocolIncompleteError(StructuredError):
    """Protocol declaration missing required fields."""

    def __init__(self, message: str, artifact: str | None = None, **kwargs):
        super().__init__(code="PROTOCOL_INCOMPLETE", message=message, artifact=artifact, **kwargs)


class DomainResolutionError(StructuredError):
    """Domain resolution failed."""

    def __init__(self, message: str, artifact: str | None = None, **kwargs):
        super().__init__(code="DOMAIN_RESOLUTION_FAILED", message=message, artifact=artifact, **kwargs)


class LayerResolutionError(StructuredError):
    """Layer resolution failed."""

    def __init__(self, message: str, artifact: str | None = None, **kwargs):
        super().__init__(code="LAYER_RESOLUTION_FAILED", message=message, artifact=artifact, **kwargs)


class BootstrapScopeViolation(StructuredError):
    """Bootstrap logic used outside permitted scope."""

    def __init__(self, message: str, **kwargs):
        super().__init__(code="BOOTSTRAP_SCOPE_VIOLATION", message=message, **kwargs)


class ReferenceNotFoundError(StructuredError):
    """Referenced artifact not found."""

    def __init__(self, message: str, artifact: str | None = None, location: str | None = None, **kwargs):
        super().__init__(code="REFERENCE_NOT_FOUND", message=message, artifact=artifact, location=location, **kwargs)


# Export all exception types
__all__ = [
    "StructuredError",
    "ProtocolIncompleteError",
    "DomainResolutionError",
    "LayerResolutionError",
    "BootstrapScopeViolation",
    "ReferenceNotFoundError",
]
