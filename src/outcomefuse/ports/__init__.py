"""Ports: the narrow boundary the governor core is reached through (AD-1).

A host adapter **proposes** a step and **applies** the returned verdict,
including termination. No host framework type appears above the adapter layer.
"""

from __future__ import annotations

from .approval import (
    ApprovalOutcome,
    ApprovalPort,
    ApprovalRequest,
    Decision,
    ScriptedApprovalPort,
)
from .model import (
    ModelPort,
    ModelRequest,
    ModelResponse,
    ScriptedModelPort,
    StreamingBarred,
)
from .posture import (
    POSTURES,
    REQUIRED_POSTURE,
    PortRegistration,
    PortRegistry,
    Posture,
    PostureError,
)
from .tools import ProbedToolPort, ToolCall, ToolPort, ToolResult

__all__ = [
    "POSTURES",
    "REQUIRED_POSTURE",
    "ApprovalOutcome",
    "ApprovalPort",
    "ApprovalRequest",
    "Decision",
    "ModelPort",
    "ModelRequest",
    "ModelResponse",
    "PortRegistration",
    "PortRegistry",
    "Posture",
    "PostureError",
    "ProbedToolPort",
    "ScriptedApprovalPort",
    "ScriptedModelPort",
    "StreamingBarred",
    "ToolCall",
    "ToolPort",
    "ToolResult",
]
