# Nucleo puro do perfil Web da Range Engine (marco B de docs/web-profile-validation-plan.md).
# Nao importa bpy, nao executa nem importa scripts analisados e nao faz I/O de rede.
# Os coletores bpy (marco C) alimentam estas funcoes; a UI apenas exibe o Report.

from .results import (
    EVIDENCE_CONFIRMED, EVIDENCE_POTENTIAL, EVIDENCE_UNVALIDATED,
    SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING,
    Finding, Report,
)

__all__ = (
    "EVIDENCE_CONFIRMED", "EVIDENCE_POTENTIAL", "EVIDENCE_UNVALIDATED",
    "SEVERITY_ERROR", "SEVERITY_INFO", "SEVERITY_WARNING",
    "Finding", "Report",
)
