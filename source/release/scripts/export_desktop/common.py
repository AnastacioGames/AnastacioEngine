from pathlib import Path as _Path
from json import loads as _loads

# Export to Desktop: estes scripts ficam em <engine>/2.79/scripts/export_desktop/, com launcher/,
# icons/ e tools/ ao lado. Na instalação antiga (painel RangeArmor) ficavam em
# <engine>/rangearmor/release/scripts/, com os modelos uma pasta acima.
HERE = _Path(__file__).resolve().parent
TEMPLATES = HERE if (HERE / 'launcher').is_dir() else HERE.parent
# Pasta do executável da engine: 3 níveis acima nos dois formatos.
ENGINE_DIR = HERE.parents[2]


# Arquivos de uma pasta de build que o jogo não usa: editor, ferramentas do build, símbolos de depuração
# (o .pdb do player sozinho tem ~750 MB) e testes. Só a pasta raiz da engine é filtrada por nome de pasta.
DEV_NAMES = {"makesdna", "makesrna", "datatoc", "datatoc_icon", "msgfmt", "rangearmor", "rangearmor_panel",
             "rangeengine", "rangeengine.exe", "anastacioengine", "anastacioengine.exe", "imgui.ini",
             "makesdna.exe", "makesrna.exe", "datatoc.exe", "datatoc_icon.exe", "msgfmt.exe", "demos"}
DEV_SUFFIXES = (".pdb", ".lib", ".exp", ".ilk")


def ignore_dev_files(_directory, names):
    """shutil.copytree(ignore=...): tira da engine copiada o que só serve para desenvolver."""
    return {name for name in names
            if name.lower() in DEV_NAMES or name.lower().endswith(DEV_SUFFIXES)
            or name.lower().endswith(("_tests.exe", "_test.exe"))}


def step(name):
    """Marca de etapa lida pela janela Export to Desktop (o resto da saída é log)."""
    print('@step ' + name, flush=True)


def resolve_runtime(path):
    """Accept either standard desktop runtime name without changing custom paths."""
    path = _Path(path)
    if path.is_file():
        return path
    alternate = {
        'RangeRuntime.exe': 'AnastacioRuntime.exe',
        'AnastacioRuntime.exe': 'RangeRuntime.exe',
        'RangeRuntime': 'AnastacioRuntime',
        'AnastacioRuntime': 'RangeRuntime',
    }.get(path.name)
    if alternate and path.with_name(alternate).is_file():
        return path.with_name(alternate)
    return path


def getArgs():
    # type: () -> dict[str, str]
    
    from sys import argv
    
    args = {}  # type: dict[str, str]
    
    for i in range(len(argv)):
        if i > 0:
            arg = argv[i]
            argNext = argv[i + 1] if len(argv) > i + 1 else True
            
            if arg.startswith("-"):
                args[arg] = argNext
                
    return args


def getProjectData(projectFile=None):
    # type: (str | _Path) -> dict[str]
    
    import platform
    from ast import literal_eval
    
    args = getArgs()
    
    if not projectFile and args.get("--project"):
        projectFile = str(args.get("--project"))
        
    data = {}  # type: dict[str, object]
    projectFile = _Path(projectFile).resolve() if type(projectFile) == str else _Path(str(projectFile))  # type: _Path
    
    if projectFile.exists():
        curPath = projectFile.parent.parent
        
        with open(projectFile.as_posix(), "r") as sourceFile:
            fileParsed = False
            
            try:
                data = _loads(sourceFile.read())
                fileParsed = True
            except:
                try:
                    data.update(literal_eval(sourceFile.read()))
                    fileParsed = True
                except:
                    print("X Could not parse project file")
                    return data
                    
            if fileParsed:
                print("> Read project from", projectFile.as_posix())
            
        engineExecutables = {}  # type: dict[str, _Path]
        
        for key in data.keys():
            if "Engine" in key:
                engineExecutable = resolve_runtime(curPath / data[key])  # type: _Path
                
                if engineExecutable.exists():
                    engineExecutables[engineExecutable.parent.name] = engineExecutable.resolve()
                        
        data["ProjectFile"] = projectFile
        data["CurPath"] = curPath
        data["Quote"] = '"' if platform.system() == "Windows" else "'"
        data["EngineExecutables"] = engineExecutables
        pointer = curPath / '.anastacio-export/current.json'
        if pointer.is_file():
            prepared = _loads(pointer.read_text(encoding='utf-8'))
            source = (curPath / prepared['source']).resolve()
            if curPath.resolve() not in source.parents or not source.is_dir():
                raise RuntimeError('Prepared export assets must exist inside the project')
            if prepared['main'] != data.get('MainFile'):
                raise RuntimeError('Prepared export assets do not match MainFile; export again from the editor')
            data['PreparedDataSource'] = prepared['source']
        
    else:
        print("X Could not get project data")
    
    return data


def formatFileName(name, spaces=True, lowercase=False):
    # type: (str, bool, bool) -> str
    
    import string
    
    allowedChars = string.ascii_lowercase + string.digits + ".-"
    result = ""
    
    if spaces:
        allowedChars += " "
    elif not spaces:
        name = name.replace(" ", "-")
        
    if lowercase:
        name = name.lower()
    elif not lowercase:
        allowedChars += string.ascii_uppercase
        
    for c in name:
        if c in allowedChars:
            result += c
    
    return result

