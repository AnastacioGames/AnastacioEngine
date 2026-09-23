import os
from re import findall, error as re_error
import bpy
import hashlib
from pathlib import Path

# =========================
# Imports & Regex (Atualizado e Robusto)
# =========================
try:
    from ..var_globals import regex_multiline
    from ..var_globals import log
except ImportError:
    # Backup: Regex melhorada para capturar classes KX_PythonComponent
    # Garante que pega o nome correto mesmo com espacos ou heranca multipla
    regex_multiline = r"class\s+([a-zA-Z_]\w*)\s*\([^)]*\bKX_PythonComponent\b[^)]*\)\s*:"

# =========================
# Configurações & Cache
# =========================
_MAX_BYTES = 2_000_000  # Limite de 2MB para leitura de scripts (seguranca)
# Cache: scripts_path -> {"hash": str, "modules": dict}
_CACHE = {}


# =========================
# Funções Auxiliares
# =========================
def _is_py_file(name: str) -> bool:
    if not isinstance(name, str) or not name.endswith(".py"):
        return False
    # Ignora arquivos de backup comuns gerados pelo usuário ou pelo sistema
    if name.startswith("BKP_") or name.startswith("old_") or name.startswith("~"):
        return False
    return True


def _safe_open_read(path_file: str) -> str:
    """
	Tenta ler o arquivo com segurança, ignorando erros de encoding.
	Crucial para evitar crash com caracteres especiais em comentários.
	"""
    try:
        try:
            if _MAX_BYTES and os.path.getsize(path_file) > _MAX_BYTES:
                if 'log' in globals(): log.warning("Ignorando arquivo grande: {}".format(path_file))
                return ""
        except Exception:
            pass

        # errors='ignore' evita travamento com caracteres não-UTF8
        with open(path_file, mode="r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        if 'log' in globals(): log.error("Erro ao ler {}: {}".format(path_file, e))
        return ""


def _build_path_class(path_file: str, scripts_path: str, name_class: str) -> str:
    """Formata o caminho do arquivo para o padrão de importação do Python (pontos)."""
    norm_path = path_file.replace("/", "\\")
    norm_base = scripts_path.replace("/", "\\")

    path_class = norm_path.replace(norm_base, "").replace("\\", ".").replace(".py", "")

    # Remove ponto inicial se houver (para evitar erros de import relativo incorreto)
    if path_class.startswith("."):
        path_class = path_class[1:]

    return "{}.{}".format(path_class, name_class)


def _hash_tree(root_scripts: Path) -> str:
    """
	Gera um hash leve baseado na modificação dos arquivos.
	Se nada mudou na pasta, o hash é o mesmo e usamos o cache.
	"""
    h = hashlib.sha1()
    for base, dirs, files in os.walk(root_scripts):
        if "__pycache__" in dirs:
            try:
                dirs.remove("__pycache__")
            except ValueError:
                pass

        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = Path(base) / fn
            try:
                st = p.stat()
                # Hash considera nome, data de modificação e tamanho
                h.update(fn.encode("utf-8", "ignore"))
                h.update(str(int(st.st_mtime)).encode())
                h.update(str(st.st_size).encode())
            except Exception:
                pass
    return h.hexdigest()


# =========================
# Função Principal: Get Modules (Com Cache)
# =========================
def get_modules(scripts_path, force_refresh=False):
    dict_modules = {}

    # Proteção: Se o caminho não existe, retorna vazio
    if not scripts_path or not os.path.exists(os.path.join(scripts_path, "scripts")):
        return dict_modules

    root_scripts = "{}\\scripts".format(scripts_path)

    # --- Lógica de Cache ---
    root = Path(root_scripts)
    if root.exists():
        tree_hash = _hash_tree(root)
    else:
        tree_hash = "missing"

    cached = _CACHE.get(scripts_path)
    # Se o hash for igual ao anterior, devolve o cache (Performance pura!)
    if not force_refresh and cached and cached.get("hash") == tree_hash:
        return cached["modules"]

    # --- Varredura de Arquivos ---
    for root, dirs, files in os.walk(top=root_scripts, topdown=True):
        root_split = os.path.basename(root)

        # Ignora pastas de cache e pastas ocultas (.git, etc)
        if root_split != "__pycache__" and not root_split.startswith("."):
            module = root_split

            # Inicializa o dicionário do módulo se necessário
            if module not in dict_modules and module != os.path.basename(scripts_path):
                dict_modules[module] = {}

            for file in files:
                if not _is_py_file(file):
                    continue

                path_file = os.path.join(root, file)

                # Leitura Segura
                content = _safe_open_read(path_file)
                if not content:
                    continue

                # Otimização: Só roda regex se tiver "KX_PythonComponent" no texto
                if "KX_PythonComponent" in content:
                    try:
                        all_classes = findall(pattern=regex_multiline, string=content)

                        for cls in all_classes:
                            # Se o regex retornar tupla (grupos), pega o primeiro item.
                            # Se retornar string, usa ela direto.
                            name_class = cls[0] if isinstance(cls, tuple) else cls

                            path_class = _build_path_class(path_file, scripts_path, name_class)
                            dict_modules[module].update({name_class: path_class})

                    except re_error as e:
                        if 'log' in globals(): log.error("Regex error in {}: {}".format(path_file, e))
                        continue
                    except Exception as e:
                        if 'log' in globals(): log.error("Error parsing {}: {}".format(file, e))
                        continue

    # Salva no cache antes de retornar
    _CACHE[scripts_path] = {"hash": tree_hash, "modules": dict_modules}

    return dict_modules


# =========================
# Arquivos Internos (.blend)
# =========================
def get_modules_in_range(scene):
    dict_modules = {"In .Range File": {}}

    if hasattr(bpy.data, "texts"):
        for obj in bpy.data.texts:
            # Filtra apenas scripts Python
            if not obj.name.endswith(".py"):
                continue

            try:
                strTxt = obj.as_string()
                # Verifica existência antes de processar linhas
                if "types.KX_PythonComponent" in strTxt:
                    for line in strTxt.split("\n"):
                        # Procura a definição da classe
                        if "types.KX_PythonComponent" in line and "class" in line:
                            # Limpeza precisa usando strip()
                            try:
                                nm = line.replace("class", "").split("(")[0].strip()
                                if nm:
                                    dict_modules["In .Range File"].update({
                                        nm: obj.name[:-3] + "." + nm
                                    })
                            except IndexError:
                                continue
            except Exception as e:
                if 'log' in globals(): log.error("Erro ao ler texto interno '{}': {}".format(obj.name, e))
                continue

    return dict_modules


# =========================
# Callbacks de Atualização (UI)
# =========================
def update_classes_list(self, context):
    """Callback para atualizar a lista de classes quando o módulo selecionado mudar."""
    wm = context.window_manager
    scene = context.scene

    collection_modules = wm.collection_modules
    index_active = wm.collection_modules_active
    collection_classes = wm.collection_classes

    last_index = wm.get("last_module_index", -1)

    if last_index == index_active:
        return
        
    wm["last_module_index"] = index_active
    collection_classes.clear()

    if len(collection_modules) > 0 and index_active < len(collection_modules):
        from .set_scripts_dir import set_scripts_dir
        dict_modules_live = get_modules_in_range(scene)
        dict_modules_live.update(get_modules(set_scripts_dir()))

        current_module_name = collection_modules[index_active].value
        if current_module_name in dict_modules_live:
            for cls in dict_modules_live[current_module_name]:
                item = collection_classes.add()
                item.value = cls