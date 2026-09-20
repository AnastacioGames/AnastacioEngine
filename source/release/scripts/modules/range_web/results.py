# Resultados das regras Web: gravidade e evidencia sao eixos independentes (plano, secao 4).

import json

from .i18n import _

SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"
SEVERITY_INFO = "INFO"

EVIDENCE_CONFIRMED = "CONFIRMED"
EVIDENCE_POTENTIAL = "POTENTIAL"
EVIDENCE_UNVALIDATED = "UNVALIDATED"

_SEVERITIES = (SEVERITY_ERROR, SEVERITY_WARNING, SEVERITY_INFO)
_EVIDENCES = (EVIDENCE_CONFIRMED, EVIDENCE_POTENTIAL, EVIDENCE_UNVALIDATED)

REPORT_SCHEMA_VERSION = 1


class Finding:
    """Um resultado. `location` e um dict livre: source (arquivo/datablock), line, rna_path, chain."""

    __slots__ = ("rule_id", "rule_version", "severity", "evidence", "message", "fix",
                 "location", "capability")

    def __init__(self, rule_id, severity, evidence, message, fix="", location=None,
                 capability="", rule_version=1):
        if severity not in _SEVERITIES:
            raise ValueError("gravidade invalida: %r" % (severity,))
        if evidence not in _EVIDENCES:
            raise ValueError("evidencia invalida: %r" % (evidence,))
        # Erro exige prova; uma hipotese de scanner nunca vira erro (plano, secao 4).
        if severity == SEVERITY_ERROR and evidence == EVIDENCE_POTENTIAL:
            raise ValueError("ERROR nao pode ter evidencia POTENTIAL (%s)" % rule_id)
        self.rule_id = rule_id
        self.rule_version = rule_version
        self.severity = severity
        self.evidence = evidence
        self.message = message
        self.fix = fix
        self.location = dict(location or {})
        self.capability = capability

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "severity": self.severity,
            "evidence": self.evidence,
            "message": self.message,
            "fix": self.fix,
            "location": self.location,
            "capability": self.capability,
        }

    def __repr__(self):
        return "Finding(%s, %s/%s, %r)" % (self.rule_id, self.severity, self.evidence, self.message)


class Report:
    def __init__(self, snapshot_hash=""):
        self.snapshot_hash = snapshot_hash
        self.findings = []

    def add(self, finding):
        self.findings.append(finding)

    def extend(self, findings):
        for f in findings:
            self.add(f)

    def by_severity(self, severity):
        return [f for f in self.findings if f.severity == severity]

    @property
    def errors(self):
        return self.by_severity(SEVERITY_ERROR)

    @property
    def blocks_export(self):
        return bool(self.errors)

    def summary(self):
        """Texto curto. Com zero erros nunca afirma que o jogo funciona."""
        e = len(self.errors)
        w = len(self.by_severity(SEVERITY_WARNING))
        if e:
            return _("%d error(s), %d warning(s)") % (e, w)
        if w:
            return _("No incompatibility detected (%d warning(s))") % w
        return _("No incompatibility detected")

    def to_dict(self):
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "snapshot_hash": self.snapshot_hash,
            "summary": self.summary(),
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
