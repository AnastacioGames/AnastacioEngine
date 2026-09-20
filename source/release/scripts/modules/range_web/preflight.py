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

from .results import EVIDENCE_CONFIRMED, SEVERITY_ERROR, Finding

PREFLIGHT_SCHEMA = "range-web-preflight"
PREFLIGHT_SCHEMA_VERSION = 1

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
        return [_err("WEB-DEPLOY-002", "Não foi possível ler o relatório de pré-voo: %s" % exc,
                     fix="Gerar o relatório com PREFLIGHT_OUT=arquivo.json no verify-package.cjs.",
                     location={"source": str(path)})]
    return check_preflight(data, runtime_manifest)


def check_preflight(data, runtime_manifest=None):
    """Findings de um relatorio de pre-voo. `runtime_manifest` (opcional) diz se o build exige threads."""
    if not isinstance(data, dict) or data.get("schema") != PREFLIGHT_SCHEMA:
        return [_err("WEB-DEPLOY-002", "Relatório de pré-voo ausente ou com schema desconhecido.",
                     fix="Rodar o Testar Web com a página de pré-voo do pacote.")]
    if data.get("schema_version") != PREFLIGHT_SCHEMA_VERSION:
        return [_err("WEB-DEPLOY-002", "Versão do relatório de pré-voo incompatível: %r." % data.get("schema_version"))]

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
                 "Build com threads exige isolamento de origem, mas a página não está isolada.",
                 fix="Servir com Cross-Origin-Opener-Policy: same-origin e "
                     "Cross-Origin-Embedder-Policy: require-corp. O binário serial é outro build.",
                 capability="threads")]


def _check_webgl(data):
    gl = data.get("webgl")
    if gl is None:
        return []
    out = []
    if gl.get("version", 0) < 2:
        out.append(_err("WEB-GFX-001", "WebGL indisponível no navegador%s." % (
            ": " + gl["error"] if gl.get("error") else ""),
            fix="Usar um navegador com WebGL 2 e aceleração de hardware.", capability="webgl"))
    for ext in gl.get("missing_extensions", ()):
        out.append(_err("WEB-GFX-001", "Extensão WebGL obrigatória ausente: %s." % ext, capability="webgl"))
    return out


def _check_files(data):
    out = []
    for f in data.get("files", ()):
        name = f.get("name", "?")
        loc = {"source": name}
        status = f.get("status")
        if status is None or status >= 400:
            why = f.get("error") or ("HTTP %s" % status if status else "sem resposta")
            out.append(_err("WEB-DEPLOY-002", "%s não carregou: %s." % (name, why),
                            fix="Conferir a URL e se o arquivo foi publicado junto do pacote.", location=loc))
            continue
        if name.endswith(".wasm") and f.get("mime") != _WASM_MIME:
            out.append(_err("WEB-DEPLOY-002", "%s servido como %r; esperado %s." % (name, f.get("mime"), _WASM_MIME),
                            fix="Configurar o MIME application/wasm no servidor.", location=loc))
        exp, got = f.get("expected_sha256"), f.get("sha256")
        if exp and got and exp != got:
            out.append(_err("WEB-DEPLOY-002", "%s diverge do manifesto (cache de versões misturadas?)." % name,
                            fix="Limpar o cache e republicar todos os arquivos do pacote juntos.", location=loc))
    return out


def _check_runtime(data):
    if data.get("runtime_aborted"):
        return [_err("WEB-DEPLOY-002", "Runtime abortou durante o pré-voo: %s." % data["runtime_aborted"],
                     fix="Consultar o log do runtime e corrigir o erro antes de publicar.")]
    if data.get("runtime_failure"):
        return [_err("WEB-DEPLOY-002", "Runtime falhou durante o pré-voo: %s." % data["runtime_failure"],
                     fix="Consultar o log do runtime e conferir os arquivos do pacote.")]
    if data.get("runtime_initialized") is False:
        return [_err("WEB-DEPLOY-002", "Runtime não concluiu a inicialização durante o pré-voo.",
                     fix="Aumentar o tempo de pré-voo ou corrigir a falha de carregamento do runtime.")]
    return []


def _check_context(data):
    if not data.get("context_lost"):
        return []
    return [_err("WEB-DEPLOY-003", "Contexto WebGL perdido durante a execução.",
                 fix="Recarregar a página; o jogo deve pausar ou avisar em vez de continuar sem render.")]


def _check_shaders(data):
    out = []
    for s in data.get("shader_errors", ()):
        where = ", material %s" % s["material"] if s.get("material") else ""
        out.append(_err("WEB-GFX-002", "Shader não compilou (estágio %s%s)." % (s.get("stage", "?"), where),
                        fix=s.get("log", ""), location={"source": s.get("material", "")}))
    return out


def _check_python(data):
    out = []
    seen = set()
    for e in data.get("python_errors", ()):
        # O mesmo erro repete a cada frame do controller; um resultado por causa.
        key = (e.get("kind"), e.get("module"), e.get("file"), e.get("text"))
        if key in seen:
            continue
        seen.add(key)
        kind = e.get("kind", "")
        if kind in ("ImportError", "ModuleNotFoundError"):
            out.append(_err("WEB-PY-001", "Import falhou no runtime: %s." % (e.get("module") or e.get("text", "?")),
                            fix="Incluir o módulo no pacote ou removê-lo.", location={"source": e.get("file", "")}))
        elif kind == "FileNotFoundError":
            out.append(_err("WEB-PKG-003", "Arquivo não encontrado no runtime: %s." % (e.get("file") or e.get("text", "?")),
                            fix="Incluir o arquivo no pacote.", location={"source": e.get("file", "")}))
        else:
            out.append(_err("WEB-PY-009", "%s no runtime: %s" % (kind or "Erro", e.get("text", "")),
                            location={"source": e.get("file", "")}))
    return out
