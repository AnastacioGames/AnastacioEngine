# Interpretacao do relatorio de pre-voo enviado pelo navegador (marco E). Puro: recebe o dict
# JSON produzido pela pagina de teste e devolve Findings; nao abre navegador nem rede.
#
# Formato (schema "range-web-preflight", versao 1); campos ausentes significam "nao sondado" e
# nunca viram erro por si:
#   cross_origin_isolated: bool
#   webgl: {version: 0|1|2, missing_extensions: [str], error: str}
#   files: [{name, status (int|null), mime, error, expected_sha256, sha256}]
#   context_lost: bool
#   runtime_initialized: bool
#   runtime_aborted: str
#   runtime_failure: str
#   shader_errors: [{material, stage, log}]
#   python_errors: [{kind: "ImportError"|"FileNotFoundError"|..., module, file, text}]

import json

from .i18n import Msg
from .results import EVIDENCE_CONFIRMED, SEVERITY_ERROR, Finding

PREFLIGHT_SCHEMA = "range-web-preflight"
PREFLIGHT_SCHEMA_VERSION = 2
_SUPPORTED_SCHEMA_VERSIONS = (1, PREFLIGHT_SCHEMA_VERSION)

_WASM_MIME = "application/wasm"


def _err(rule_id, message, fix="", location=None, capability=""):
    return Finding(rule_id, SEVERITY_ERROR, EVIDENCE_CONFIRMED, message, fix=fix,
                   location=location, capability=capability)


def load_preflight(path, runtime_manifest=None):
    """Le o JSON gravado pela pagina de pre-voo e devolve seus Findings; arquivo ilegivel vira WEB-DEPLOY-002."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return [_err("WEB-DEPLOY-002", Msg("Could not read the preflight report: %s", exc),
                     fix="Generate the report with PREFLIGHT_OUT=file.json in verify-package.cjs.",
                     location={"source": str(path)})]
    return check_preflight(data, runtime_manifest)


def check_preflight(data, runtime_manifest=None):
    """Findings de um relatorio de pre-voo. `runtime_manifest` (opcional) diz se o build exige threads."""
    if not isinstance(data, dict) or data.get("schema") != PREFLIGHT_SCHEMA:
        return [_err("WEB-DEPLOY-002", "Preflight report missing or with an unknown schema.",
                     fix="Run the Web test with the preflight page of the package.")]
    if data.get("schema_version") not in _SUPPORTED_SCHEMA_VERSIONS:
        return [_err("WEB-DEPLOY-002", Msg("Incompatible preflight report version: %r.", data.get("schema_version")))]

    findings = []
    findings += _check_isolation(data, runtime_manifest)
    findings += _check_webgl(data)
    findings += _check_files(data)
    findings += _check_runtime(data)
    findings += _check_context(data)
    findings += _check_shaders(data)
    findings += _check_python(data)
    return findings


def _check_isolation(data, runtime_manifest):
    threads = ((runtime_manifest or {}).get("capabilities", {}).get("threads", {}).get("state"))
    if threads in (None, "disabled") or data.get("cross_origin_isolated") is not False:
        return []
    return [_err("WEB-DEPLOY-001",
                 "A threaded build requires origin isolation, but the page is not isolated.",
                 fix="Serve with Cross-Origin-Opener-Policy: same-origin and "
                     "Cross-Origin-Embedder-Policy: require-corp. The serial binary is a different build.",
                 capability="threads")]


def _check_webgl(data):
    gl = data.get("webgl")
    if gl is None:
        return []
    out = []
    if gl.get("version", 0) < 2:
        out.append(_err("WEB-GFX-001", Msg("WebGL unavailable in the browser%s.",
            ": " + gl["error"] if gl.get("error") else ""),
            fix="Use a browser with WebGL 2 and hardware acceleration.", capability="webgl"))
    for ext in gl.get("missing_extensions", ()):
        out.append(_err("WEB-GFX-001", Msg("Required WebGL extension missing: %s.", ext), capability="webgl"))
    return out


def _check_files(data):
    out = []
    for f in data.get("files", ()):
        name = f.get("name", "?")
        loc = {"source": name}
        status = f.get("status")
        if status is None or status >= 400:
            why = f.get("error") or ("HTTP %s" % status if status else Msg("no response"))
            out.append(_err("WEB-DEPLOY-002", Msg("%s did not load: %s.", name, why),
                            fix="Check the URL and whether the file was published with the package.", location=loc))
            continue
        if name.endswith(".wasm") and f.get("mime") != _WASM_MIME:
            out.append(_err("WEB-DEPLOY-002", Msg("%s served as %r; expected %s.", name, f.get("mime"), _WASM_MIME),
                            fix="Configure the application/wasm MIME type on the server.", location=loc))
        exp, got = f.get("expected_sha256"), f.get("sha256")
        if exp and got and exp != got:
            out.append(_err("WEB-DEPLOY-002", Msg("%s differs from the manifest (mixed cached versions?).", name),
                            fix="Clear the cache and republish all package files together.", location=loc))
    return out


def _check_runtime(data):
    if data.get("runtime_aborted"):
        return [_err("WEB-DEPLOY-002", Msg("Runtime aborted during preflight: %s.", data["runtime_aborted"]),
                     fix="Check the runtime log and fix the error before publishing.")]
    if data.get("runtime_failure"):
        return [_err("WEB-DEPLOY-002", Msg("Runtime failed during preflight: %s.", data["runtime_failure"]),
                     fix="Check the runtime log and the package files.")]
    if data.get("runtime_initialized") is False:
        return [_err("WEB-DEPLOY-002", "Runtime did not finish initializing during preflight.",
                     fix="Increase the preflight time or fix the runtime loading failure.")]
    return []


def _check_context(data):
    if not data.get("context_lost"):
        return []
    return [_err("WEB-DEPLOY-003", "WebGL context lost during execution.",
                 fix="Reload the page; the game should pause or warn instead of running without rendering.")]


def _check_shaders(data):
    out = []
    for s in data.get("shader_errors", ()):
        where = ", material %s" % s["material"] if s.get("material") else ""
        out.append(_err("WEB-GFX-002", Msg("Shader did not compile (stage %s%s).", s.get("stage", "?"), where),
                        fix=s.get("log", ""), location={"source": s.get("material", "")}))
    return out


def _check_python(data):
    out = []
    seen = set()
    for e in data.get("python_errors", ()):
        # O mesmo erro repete a cada frame do controller; um resultado por causa.
        key = (e.get("kind"), e.get("module"), e.get("file"), e.get("text"), e.get("origin"))
        if key in seen:
            continue
        seen.add(key)
        kind = e.get("kind", "")
        if kind in ("ImportError", "ModuleNotFoundError"):
            out.append(_err("WEB-PY-001", Msg("Import failed at runtime: %s.", e.get("module") or e.get("text", "?")),
                            fix="Include the module in the package or remove it.", location={"source": e.get("file", "")}))
        elif kind == "FileNotFoundError":
            out.append(_err("WEB-PKG-003", Msg("File not found at runtime: %s.", e.get("file") or e.get("text", "?")),
                            fix="Include the file in the package.", location={"source": e.get("file", "")}))
        else:
            where = Msg(" (%s%s)", e.get("context", ""), Msg(" in %s", e["origin"]) if e.get("origin") else "")                 if e.get("context") or e.get("origin") else ""
            out.append(_err("WEB-PY-009", Msg("%s at runtime%s: %s", kind or Msg("Error"), where, e.get("text", "")),
                            fix=e.get("traceback", ""), location={"source": e.get("origin") or e.get("file", "")}))
    return out
