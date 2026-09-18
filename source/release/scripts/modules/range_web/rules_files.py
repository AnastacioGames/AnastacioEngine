# Regras de arquivos e empacotamento (WEB-PKG-004..009). Puras: recebem strings e bytes,
# quem le o disco e o coletor (marco C). So realpath em check_within_roots toca o sistema.

import os
import posixpath
import re

from .results import (
    EVIDENCE_CONFIRMED, EVIDENCE_POTENTIAL, SEVERITY_ERROR, SEVERITY_WARNING, Finding,
)

_WIN_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
_HOST_POSIX = re.compile(r"^/(home|Users|mnt|media|Volumes)/")
_NATIVE_EXT = (".pyd", ".dll", ".so", ".dylib")
_RASEC_EXT = (".rasec",)


def _loc(source, **extra):
    d = {"source": source}
    d.update(extra)
    return d


def looks_like_host_path(text):
    """Caminho de drive Windows, UNC ou raiz tipica de usuario POSIX. `//x` (relativo do Blender) nao conta."""
    if not isinstance(text, str):
        return False
    return bool(_WIN_DRIVE.match(text) or text.startswith("\\\\") or _HOST_POSIX.match(text))


def check_runtime_path(path, source, line=None):
    """WEB-PKG-004: o chamador afirma que `path` e usado pelo runtime sem remapeamento."""
    if not looks_like_host_path(path):
        return []
    return [Finding("WEB-PKG-004", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                    "Caminho do host usado no runtime: %s" % path,
                    fix="Remapear para o FS virtual (caminho relativo ao jogo).",
                    location=_loc(source, line=line))]


def normalize_virtual_path(path):
    """Normaliza para o FS virtual. Retorna (caminho, problema); problema None se valido."""
    if not path or not isinstance(path, str):
        return None, "caminho vazio"
    if looks_like_host_path(path):
        return None, "caminho do host sem remapeamento"
    p = posixpath.normpath(path.replace("\\", "/"))
    if p.startswith("/"):
        return None, "caminho absoluto no FS virtual"
    if p == ".." or p.startswith("../"):
        return None, "escapa da raiz do pacote"
    if p == ".":
        return None, "caminho vazio"
    return p, None


def check_destinations(entries):
    """WEB-PKG-005/006 sobre pares (destino_virtual, origem). Colisao exata e por caixa."""
    findings = []
    seen = {}
    folded = {}
    for dest, source in entries:
        norm, problem = normalize_virtual_path(dest)
        if problem:
            findings.append(Finding("WEB-PKG-005", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                                    "Destino inválido %r: %s." % (dest, problem),
                                    fix="Normalizar o destino dentro da raiz do pacote.",
                                    location=_loc(source)))
            continue
        if norm in seen:
            findings.append(Finding("WEB-PKG-005", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                                    "Destinos colidem em %r (%s e %s)." % (norm, seen[norm], source),
                                    fix="Renomear um dos arquivos ou remapear o destino.",
                                    location=_loc(source, other=seen[norm])))
            continue
        seen[norm] = source
        key = norm.casefold()
        if key in folded and folded[key][0] != norm:
            findings.append(Finding("WEB-PKG-006", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                                    "Nomes ambíguos entre plataformas: %r e %r." % (folded[key][0], norm),
                                    fix="Padronizar a caixa do nome; sistemas de arquivos diferem.",
                                    location=_loc(source, other=folded[key][1])))
        else:
            folded.setdefault(key, (norm, source))
    return findings


def check_reference_case(reference, available, source, line=None):
    """WEB-PKG-006: referencia que so casa com um arquivo se ignorar a caixa."""
    norm, problem = normalize_virtual_path(reference)
    if problem:
        return []
    names = set(available)
    if norm in names:
        return []
    matches = sorted(n for n in names if n.casefold() == norm.casefold())
    if not matches:
        return []
    return [Finding("WEB-PKG-006", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                    "Referência %r não coincide em maiúsculas/minúsculas com %r." % (reference, matches[0]),
                    fix="Corrigir a referência para %r (o FS virtual diferencia a caixa)." % matches[0],
                    location=_loc(source, line=line))]


def check_within_roots(path, roots, source=None):
    """WEB-PKG-005: o caminho real (symlinks resolvidos) precisa ficar dentro de alguma raiz declarada."""
    real = os.path.normcase(os.path.realpath(path))
    for root in roots:
        r = os.path.normcase(os.path.realpath(root))
        if real == r or real.startswith(r.rstrip(os.sep) + os.sep):
            return []
    return [Finding("WEB-PKG-005", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                    "%s resolve para fora das raízes declaradas." % path,
                    fix="Incluir o arquivo dentro da raiz do projeto; não seguir links para fora.",
                    location=_loc(source or str(path)))]


def check_file_kind(name, head, source=None, expected_pyc_magic=None):
    """WEB-PKG-008/009 por conteudo/extensao. `head` = primeiros bytes do arquivo (>= 4).

    .pyc so e julgado pelo magic; sem o magic do runtime (manifesto) vira aviso, nao erro.
    Extensao nativa sozinha nao prova formato binario: confere assinatura ELF/PE/Mach-O.
    """
    source = source or name
    lower = name.lower()
    if lower.endswith(_RASEC_EXT):
        return [Finding("WEB-PKG-009", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                        "%s é conteúdo RangeArmor sem leitor validado no runtime Web." % name,
                        fix="Usar o formato de conteúdo suportado pelo perfil Web.",
                        location=_loc(source))]
    if lower.endswith(_NATIVE_EXT):
        if head[:4] == b"\x7fELF" or head[:2] == b"MZ" or head[:4] in (
                b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
            return [Finding("WEB-PKG-008", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                            "Extensão nativa do host requerida: %s." % name,
                            fix="Usar fonte Python ou módulo Wasm construído para o runtime.",
                            location=_loc(source))]
        return [Finding("WEB-PKG-008", SEVERITY_WARNING, EVIDENCE_POTENTIAL,
                        "%s tem extensão nativa, mas o conteúdo não é binário reconhecido." % name,
                        fix="Confirmar o que o arquivo é antes de empacotar.",
                        location=_loc(source))]
    if lower.endswith(".pyc"):
        magic = bytes(head[:4])
        if len(magic) < 4:
            return [Finding("WEB-PKG-008", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                            "%s truncado: não é um .pyc válido." % name,
                            fix="Usar o fonte .py.", location=_loc(source))]
        if expected_pyc_magic is None:
            return [Finding("WEB-PKG-008", SEVERITY_WARNING, EVIDENCE_POTENTIAL,
                            "%s: o manifesto do runtime não informa o magic do .pyc." % name,
                            fix="Usar o fonte .py ou um runtime cujo manifesto declare python.pyc_magic.",
                            location=_loc(source))]
        if magic != expected_pyc_magic:
            return [Finding("WEB-PKG-008", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                            "%s foi compilado para outra versão do Python." % name,
                            fix="Usar o fonte .py ou recompilar com a versão do runtime.",
                            location=_loc(source))]
    return []
