"""Export to Desktop: a janela que transforma o arquivo num jogo para Windows e Linux.

Substitui o painel RangeArmor (programa à parte).  Mesma moldura e cores da janela de Tutoriais
(range_tutorials_janela), desenhada por cima do editor.  Passos em sequência:

    (Projeto) -> 1 Jogo -> 2 Plataformas -> 3 Exportando -> 4 Pronto

"Projeto" só aparece quando o arquivo ainda não está em <projeto>/data/.  A exportação usa as
mesmas peças do "Export Now" (wm.py): monta o projeto, grava o .rasec e o config.json aqui, e roda
os scripts de 2.79/scripts/export_desktop/ num processo à parte, lido por uma thread, para o editor
não travar.  As linhas "@step <nome>" da saída dizem em que etapa está.
"""
import os
import queue
import subprocess
import sys
import threading

import bgl
import bpy
from bpy.props import StringProperty
from bpy.types import Operator

import range_tutorials as rt
import range_tutorials_janela as rj

T = {
    "titulo": {"pt": "Export to Desktop", "en": "Export to Desktop", "es": "Export to Desktop"},
    "sub": {"pt": "Transforme seu arquivo num jogo para Windows e Linux, pronto para compartilhar.",
            "en": "Turn your file into a game for Windows and Linux, ready to share.",
            "es": "Convierte tu archivo en un juego para Windows y Linux, listo para compartir."},
    "p_jogo": {"pt": "Jogo", "en": "Game", "es": "Juego"},
    "p_plat": {"pt": "Plataformas", "en": "Platforms", "es": "Plataformas"},
    "p_exp": {"pt": "Exportar", "en": "Export", "es": "Exportar"},
    "p_pronto": {"pt": "Pronto", "en": "Done", "es": "Listo"},
    "voltar": {"pt": "Voltar", "en": "Back", "es": "Volver"},
    "proximo": {"pt": "Próximo", "en": "Next", "es": "Siguiente"},
    "exportar": {"pt": "Exportar jogo", "en": "Export game", "es": "Exportar juego"},
    "fechar": {"pt": "Fechar", "en": "Close", "es": "Cerrar"},
    # Projeto
    "proj_t": {"pt": "Primeiro, uma pasta para o projeto", "en": "First, a folder for the project",
               "es": "Primero, una carpeta para el proyecto"},
    "proj_1": {"pt": "O jogo é montado a partir de uma pasta de projeto, com o seu arquivo dentro de data/.",
               "en": "The game is built from a project folder, with your file inside data/.",
               "es": "El juego se arma desde una carpeta de proyecto, con tu archivo dentro de data/."},
    "proj_2": {"pt": "Escolha onde criar.  O arquivo aberto passa a ser salvo lá, como:",
               "en": "Choose where to create it.  The open file is then saved there, as:",
               "es": "Elige dónde crearla.  El archivo abierto pasa a guardarse allí, como:"},
    "proj_3": {"pt": "Texturas e sons fora dessa pasta: use File > External Data > Pack ou copie para data/.",
               "en": "Textures and sounds outside that folder: use File > External Data > Pack or copy them into data/.",
               "es": "Texturas y sonidos fuera de esa carpeta: usa File > External Data > Pack o cópialos a data/."},
    "proj_b": {"pt": "Escolher onde criar o projeto...", "en": "Choose where to create the project...",
               "es": "Elegir dónde crear el proyecto..."},
    # Jogo
    "jogo_t": {"pt": "Como o jogo se chama?", "en": "What is the game called?", "es": "¿Cómo se llama el juego?"},
    "nome": {"pt": "Nome", "en": "Name", "es": "Nombre"},
    "nome_d": {"pt": "Aparece no executável, na janela e no nome da pasta.",
               "en": "Shows in the executable, the window and the folder name.",
               "es": "Aparece en el ejecutable, la ventana y el nombre de la carpeta."},
    "versao": {"pt": "Versão", "en": "Version", "es": "Versión"},
    "versao_d": {"pt": "Por exemplo 1.0.0.  Entra no nome da pasta exportada.",
                 "en": "For example 1.0.0.  Goes into the exported folder name.",
                 "es": "Por ejemplo 1.0.0.  Va en el nombre de la carpeta exportada."},
    "icone": {"pt": "Ícone", "en": "Icon", "es": "Icono"},
    "icone_d": {"pt": "Imagem PNG quadrada (512x512).  Opcional.",
                "en": "Square PNG image (512x512).  Optional.",
                "es": "Imagen PNG cuadrada (512x512).  Opcional."},
    "escolher": {"pt": "Escolher...", "en": "Choose...", "es": "Elegir..."},
    "tirar": {"pt": "Tirar", "en": "Remove", "es": "Quitar"},
    "sem_icone": {"pt": "Sem ícone: usa o padrão da engine.", "en": "No icon: uses the engine default.",
                  "es": "Sin icono: usa el de la engine."},
    "falta_nome": {"pt": "Escreva o nome do jogo.", "en": "Type the game name.", "es": "Escribe el nombre del juego."},
    # Plataformas
    "plat_t": {"pt": "Para quais computadores?", "en": "For which computers?", "es": "¿Para qué computadoras?"},
    "win_d": {"pt": "Pasta com o .exe do jogo.", "en": "Folder with the game .exe.", "es": "Carpeta con el .exe del juego."},
    "lin_d": {"pt": "Pasta com o executável Linux.", "en": "Folder with the Linux executable.",
              "es": "Carpeta con el ejecutable Linux."},
    "sem_rt": {"pt": "Engine desta plataforma não encontrada.", "en": "Engine for this platform not found.",
               "es": "Engine de esta plataforma no encontrada."},
    "ligado": {"pt": "Incluído", "en": "Included", "es": "Incluido"},
    "desligado": {"pt": "Não incluído", "en": "Not included", "es": "No incluido"},
    "os_dois": {"pt": "Com os dois, sai também uma pasta Universal que abre nos dois sistemas.",
                "en": "With both, you also get a Universal folder that opens on both systems.",
                "es": "Con los dos, también sale una carpeta Universal que abre en los dos sistemas."},
    "opcoes": {"pt": "Opções", "en": "Options", "es": "Opciones"},
    "o_zip": {"pt": "Gerar .zip para compartilhar", "en": "Make a .zip to share", "es": "Generar .zip para compartir"},
    "o_cook": {"pt": "Preparar para abrir mais rápido (cook)", "en": "Prepare to open faster (cook)",
               "es": "Preparar para abrir más rápido (cook)"},
    "o_pyc": {"pt": "Esconder o código dos scripts .py (compilar)", "en": "Hide the .py script source (compile)",
              "es": "Ocultar el código de los scripts .py (compilar)"},
    "o_debug": {"pt": "Manter FPS e propriedades de depuração na tela", "en": "Keep FPS and debug properties on screen",
                "es": "Mantener FPS y propiedades de depuración en pantalla"},
    "protegido": {"pt": "Os arquivos do jogo saem protegidos (.rasec, proteção básica).",
                  "en": "Game files ship protected (.rasec, basic protection).",
                  "es": "Los archivos del juego salen protegidos (.rasec, protección básica)."},
    "nenhuma": {"pt": "Escolha pelo menos uma plataforma.", "en": "Choose at least one platform.",
                "es": "Elige al menos una plataforma."},
    # Exportando
    "exp_t": {"pt": "Exportando...", "en": "Exporting...", "es": "Exportando..."},
    "erro_t": {"pt": "A exportação parou", "en": "The export stopped", "es": "La exportación se detuvo"},
    "e_preparar": {"pt": "Salvar e proteger os arquivos do jogo", "en": "Save and protect the game files",
                   "es": "Guardar y proteger los archivos del juego"},
    "e_runtime": {"pt": "Copiar a engine do jogo", "en": "Copy the game engine", "es": "Copiar la engine del juego"},
    "e_cook": {"pt": "Preparar para abrir mais rápido", "en": "Prepare to open faster",
               "es": "Preparar para abrir más rápido"},
    "e_package": {"pt": "Montar as pastas do jogo", "en": "Build the game folders", "es": "Armar las carpetas del juego"},
    "cancelar": {"pt": "Cancelar", "en": "Cancel", "es": "Cancelar"},
    "copiar_log": {"pt": "Copiar log", "en": "Copy log", "es": "Copiar log"},
    "log_copiado": {"pt": "Log copiado.", "en": "Log copied.", "es": "Log copiado."},
    "cancelado": {"pt": "Cancelado.", "en": "Cancelled.", "es": "Cancelado."},
    "sem_detalhe": {"pt": "Veja o log para os detalhes.", "en": "See the log for details.",
                    "es": "Mira el log para los detalles."},
    # Pronto
    "ok_t": {"pt": "Seu jogo está pronto!", "en": "Your game is ready!", "es": "¡Tu juego está listo!"},
    "ok_1": {"pt": "Abre com dois cliques, sem a engine instalada.  As pastas ficaram em:",
             "en": "It opens with a double click, without the engine installed.  The folders are in:",
             "es": "Abre con doble clic, sin la engine instalada.  Las carpetas quedaron en:"},
    "abrir": {"pt": "Abrir pasta", "en": "Open folder", "es": "Abrir carpeta"},
    "testar": {"pt": "Testar o jogo", "en": "Test the game", "es": "Probar el juego"},
    "de_novo": {"pt": "Exportar de novo", "en": "Export again", "es": "Exportar de nuevo"},
}

PASSOS = ("p_jogo", "p_plat", "p_exp", "p_pronto")
HOST = "Windows64" if sys.platform == "win32" else "Linux64"
RUNTIMES = {"Windows64": ("AnastacioRuntime.exe", "RangeRuntime.exe"),
            "Linux64": ("AnastacioRuntime", "RangeRuntime")}

estado = {}  # vazio = fechada


def _t(chave):
    return rt._txt(T[chave])


# ---------------------------------------------------------------- dados do jogo

def _cena():
    return bpy.context.scene


def _projeto():
    from bl_ui.properties_scene import desktop_project_dir
    return desktop_project_dir()


def _launcher_ok(alvo):
    """Há launcher do jogo para esta plataforma (no projeto ou vindo com a engine)?"""
    from bl_operators import wm as wm_ops
    nome = "Launcher.exe" if alvo == "Windows64" else "Launcher"
    projeto = _projeto()
    if projeto and os.path.isfile(os.path.join(projeto, "launcher", nome)):
        return True
    pastas = wm_ops.export_desktop_dirs()
    return bool(pastas) and os.path.isfile(os.path.join(pastas[0], "launcher", nome))


def _runtime_ok(alvo):
    """Há engine e launcher para esta plataforma (no projeto, instalada ou num build vizinho)?"""
    if not _launcher_ok(alvo):
        return False
    nomes = RUNTIMES[alvo]
    projeto = _projeto()
    if projeto and any(os.path.isfile(os.path.join(projeto, "engine", alvo, n)) for n in nomes):
        return True
    pasta_bin = os.path.dirname(bpy.app.binary_path)
    if alvo == HOST and any(os.path.isfile(os.path.join(pasta_bin, n)) for n in nomes):
        return True
    env = os.environ.get("RANGEARMOR_ENGINE_DIR_" + alvo.upper())
    if env and any(os.path.isfile(os.path.join(env, n)) for n in nomes):
        return True
    build = "build" if alvo == "Windows64" else "build-linux"
    pasta = pasta_bin
    while True:
        if any(os.path.isfile(os.path.join(pasta, build, "bin", n)) for n in nomes):
            return True
        acima = os.path.dirname(pasta)
        if acima == pasta:
            return False
        pasta = acima


def _plataformas():
    """Plataformas escolhidas que têm engine disponível."""
    exp = _cena().rangearmor_export
    escolha = {"Windows64": exp.export_windows64, "Linux64": exp.export_linux64}
    return [alvo for alvo in ("Windows64", "Linux64") if escolha[alvo] and _runtime_ok(alvo)]


# ---------------------------------------------------------------- campos de texto

CAMPOS = {"nome": ("range_game_info", "name"), "versao": ("range_game_info", "version")}


def _valor(campo):
    grupo, prop = CAMPOS[campo]
    return getattr(getattr(_cena(), grupo), prop)


def _gravar(campo, texto):
    grupo, prop = CAMPOS[campo]
    setattr(getattr(_cena(), grupo), prop, texto)


def _focar(campo):
    estado["foco"] = campo
    estado["cursor"] = len(_valor(campo)) if campo else 0


def _tecla(context, event):
    """Edita o campo com foco; True se a tecla foi usada."""
    campo = estado.get("foco")
    if not campo or event.value != 'PRESS':
        return False
    texto, c = _valor(campo), min(estado.get("cursor", 0), len(_valor(campo)))
    tipo = event.type
    if tipo in ('RET', 'NUMPAD_ENTER', 'TAB'):
        ordem = list(CAMPOS)
        seguinte = ordem.index(campo) + (-1 if event.shift else 1)
        _focar(ordem[seguinte] if 0 <= seguinte < len(ordem) and tipo == 'TAB' else None)
        return True
    if tipo == 'ESC':
        _focar(None)
        return True
    if tipo == 'BACK_SPACE':
        if c:
            _gravar(campo, texto[:c - 1] + texto[c:])
            c -= 1
    elif tipo == 'DEL':
        _gravar(campo, texto[:c] + texto[c + 1:])
    elif tipo == 'LEFT_ARROW':
        c = max(0, c - 1)
    elif tipo == 'RIGHT_ARROW':
        c = min(len(texto), c + 1)
    elif tipo == 'HOME':
        c = 0
    elif tipo == 'END':
        c = len(texto)
    elif tipo == 'V' and (event.ctrl or event.oskey):
        colar = context.window_manager.clipboard.replace("\r", " ").replace("\n", " ")
        _gravar(campo, texto[:c] + colar + texto[c:])
        c += len(colar)
    elif tipo == 'A' and (event.ctrl or event.oskey):
        _gravar(campo, "")
        c = 0
    elif event.unicode and event.unicode.isprintable() and not event.ctrl and not event.alt:
        _gravar(campo, texto[:c] + event.unicode + texto[c:])
        c += len(event.unicode)
    else:
        return False
    estado["cursor"] = c
    return True


# ---------------------------------------------------------------- exportação

def _preparar(context):
    """Parte que precisa do editor (no thread principal): salvar, montar o projeto, gravar o .rasec e o
    config.json.  Devolve (comandos, ambiente) para o processo à parte ou levanta RuntimeError."""
    from bl_operators import wm as wm_ops

    projeto = _projeto()
    if projeto is None:
        raise RuntimeError("The file is not inside <project>/data/")
    if bpy.data.is_dirty and bpy.ops.wm.save_mainfile() != {'FINISHED'}:
        raise RuntimeError("Could not save the file")
    erro = wm_ops._rangearmor_scaffold_project(projeto)
    if erro:
        raise RuntimeError(erro)
    if not wm_ops._rangearmor_write_export_preset(context):
        raise RuntimeError("Could not save the protected copy (.rasec) or launcher/config.json")
    wm_ops._rangearmor_ensure_launcher_script(context)

    import json
    config = os.path.join(projeto, "launcher", "config.json")
    with open(config, encoding="utf-8") as f:
        dados = json.load(f)
    python = wm_ops.WM_OT_one_click_export_rangearmor._resolve_python(None, projeto, dados)
    if not python:
        raise RuntimeError("Could not find the engine's Python interpreter")
    pastas = wm_ops.export_desktop_dirs()
    if pastas is None:
        raise RuntimeError("Export to Desktop files not found (2.79/scripts/export_desktop)")
    scripts = pastas[1]

    comandos = []
    copiar = os.path.join(scripts, "get_rangeengine_currentplatform.py")
    for alvo in _plataformas():
        if _runtime_desatualizado(projeto, alvo):
            comandos.append(("runtime", [python, "-u", copiar, "--project", config, "--platform", alvo,
                                         "--drop-previous"]))
    exp = context.scene.rangearmor_export
    comandos.append(("package", [python, "-u", os.path.join(scripts, "build_release.py"), "--project", config]
                     + wm_ops.export_desktop_build_args(exp, _plataformas())))
    ambiente = dict(os.environ)
    try:
        from bl_operators.anastacio_cook import _runtime_path
        ambiente["RANGEARMOR_COOK_RUNTIME"] = _runtime_path()
    except Exception:
        pass
    return comandos, ambiente, projeto


def _runtime_desatualizado(projeto, alvo):
    """Copia a engine quando falta no projeto ou, na plataforma deste PC, quando a instalada mudou
    (senão o jogo sairia com um player velho depois de atualizar a engine)."""
    destino = next((os.path.join(projeto, "engine", alvo, n) for n in RUNTIMES[alvo]
                    if os.path.isfile(os.path.join(projeto, "engine", alvo, n))), None)
    if destino is None:
        return True
    if alvo != HOST:
        return False
    instalado = next((os.path.join(os.path.dirname(bpy.app.binary_path), n) for n in RUNTIMES[alvo]
                      if os.path.isfile(os.path.join(os.path.dirname(bpy.app.binary_path), n))), None)
    if instalado is None:
        return False
    a, b = os.stat(instalado), os.stat(destino)
    return a.st_size != b.st_size or abs(a.st_mtime - b.st_mtime) > 2


class _Trabalho:
    """Roda os comandos em sequência numa thread; as linhas vão para uma fila lida pelo modal."""

    def __init__(self, comandos, ambiente, pasta):
        self.fila = queue.Queue()
        self.processo = None
        self.cancelado = False
        self.codigo = None
        self.thread = threading.Thread(target=self._rodar, args=(comandos, ambiente, pasta), daemon=True)
        self.thread.start()

    def _rodar(self, comandos, ambiente, pasta):
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW: sem console piscando
        # Grupo próprio no Linux: Cancelar encerra também o runtime do cook, filho do script.
        extra = {} if sys.platform == "win32" else {"start_new_session": True}
        try:
            for etapa, cmd in comandos:
                if self.cancelado:
                    break
                self.fila.put("@step " + etapa)
                self.processo = subprocess.Popen(cmd, cwd=pasta, env=ambiente, stdout=subprocess.PIPE,
                                                 stderr=subprocess.STDOUT, universal_newlines=True,
                                                 errors="replace", creationflags=flags, **extra)
                for linha in self.processo.stdout:
                    self.fila.put(linha.rstrip("\r\n"))
                if self.processo.wait() != 0:
                    self.codigo = self.processo.returncode
                    break
            else:
                self.codigo = 0
        except OSError as erro:
            self.fila.put("X " + str(erro))
            self.codigo = 1

    def cancelar(self):
        """Encerra o script e os filhos dele (o runtime do cook continuaria usando os arquivos)."""
        self.cancelado = True
        processo = self.processo
        if not processo or processo.poll() is not None:
            return
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(processo.pid)],
                               capture_output=True, creationflags=0x08000000)
            else:
                import signal
                os.killpg(processo.pid, signal.SIGTERM)
        except (OSError, ValueError):
            processo.terminate()


def _comecar_exportacao(context):
    estado.update(pagina=3, log=[], etapas={}, erro=None, saidas={}, trabalho=None, preparar=2)
    estado["lista"] = ["preparar", "runtime"] + (["cook"] if context.scene.rangearmor_export.cook_before_export
                                                 else []) + ["package"]
    _marcar("preparar")


def _marcar(etapa):
    """Etapa em andamento; as anteriores da lista ficam feitas."""
    lista = estado["lista"]
    if etapa not in lista:
        return
    i = lista.index(etapa)
    for nome in lista[:i]:
        estado["etapas"][nome] = "feito"
    for nome in lista[i + 1:]:
        estado["etapas"].pop(nome, None)
    estado["etapas"][etapa] = "andando"


def _passo_exportacao(context):
    """Chamado pelo timer durante a página 3."""
    if estado.get("preparar"):
        # Espera dois redesenhos para a página aparecer antes do trabalho que trava (salvar o .rasec).
        estado["preparar"] -= 1
        if estado["preparar"]:
            return
        try:
            comandos, ambiente, projeto = _preparar(context)
        except (RuntimeError, OSError, ValueError) as erro:
            estado["etapas"]["preparar"] = "erro"
            estado["erro"] = str(erro)
            return
        estado["projeto"] = projeto
        _marcar("runtime")
        estado["trabalho"] = _Trabalho(comandos, ambiente, projeto)
        return
    trab = estado.get("trabalho")
    if trab is None:
        return
    while True:
        try:
            linha = trab.fila.get_nowait()
        except queue.Empty:
            break
        _ler_linha(linha)
    if trab.thread.is_alive() or not trab.fila.empty():
        return
    estado["trabalho"] = None
    atual = next((n for n, s in estado["etapas"].items() if s == "andando"), None)
    if trab.cancelado:
        estado["erro"] = _t("cancelado")
    elif trab.codigo != 0 and not estado.get("erro"):
        estado["erro"] = _t("sem_detalhe")
    if estado.get("erro"):
        if atual:
            estado["etapas"][atual] = "erro"
        return
    for nome in estado["lista"]:
        estado["etapas"][nome] = "feito"
    estado["pagina"] = 4


def _ler_linha(linha):
    estado["log"].append(linha)
    del estado["log"][:-2000]
    print("[export desktop] " + linha, flush=True)
    if linha.startswith("@step "):
        _marcar(linha[6:].strip())
    elif linha.startswith("X "):
        estado["erro"] = linha[2:].strip()
    elif linha.startswith("> Build successful:"):
        partes = linha.split(":", 1)[1].strip().split(" ", 1)
        if len(partes) == 2:
            estado["saidas"][partes[0]] = partes[1].strip()


def _executavel(pasta):
    """O launcher na raiz da pasta exportada para este PC."""
    try:
        nomes = sorted(os.listdir(pasta))
    except OSError:
        return None
    for nome in nomes:
        caminho = os.path.join(pasta, nome)
        if not os.path.isfile(caminho):
            continue
        if sys.platform == "win32" and nome.lower().endswith(".exe"):
            return caminho
        if sys.platform != "win32" and "." not in nome and os.access(caminho, os.X_OK):
            return caminho
    return None


def _abrir(caminho):
    if sys.platform == "win32":
        os.startfile(caminho)
    else:
        subprocess.Popen(["xdg-open", caminho])


# ---------------------------------------------------------------- desenho

def _desenhar():
    if not estado or bpy.context.window.as_pointer() != estado["janela"]:
        return
    caixa = bgl.Buffer(bgl.GL_INT, 4)
    bgl.glGetIntegerv(bgl.GL_SCISSOR_BOX, caixa)
    ligado = bgl.glIsEnabled(bgl.GL_SCISSOR_TEST)
    try:
        bgl.glEnable(bgl.GL_BLEND)
        _desenhar_tudo()
    finally:
        bgl.glScissor(*list(caixa))
        (bgl.glEnable if ligado else bgl.glDisable)(bgl.GL_SCISSOR_TEST)
        bgl.glDisable(bgl.GL_BLEND)
        bgl.glLineWidth(1.0)


class _Tela:
    """Ajudantes de desenho de uma passada: guarda os alvos de clique e a posição do mouse."""

    def __init__(self):
        self.e = rt._escala()
        self.alvos = []
        self.mouse = estado.get("mouse", (-1, -1))

    def sobre(self, r):
        return rj._dentro(r, *self.mouse)

    def botao(self, r, rotulo, acao, valor=None, primario=False, ativo=True):
        e = self.e
        if primario:
            cor = rj.DOURADO if ativo else rj.BORDA
            rj._ret(*r, cor=cor, alfa=0.85 if ativo and self.sobre(r) else 1.0, raio=8 * e)
            cor_txt = rj.ESCURO if ativo else rj.TEXTO_3
        else:
            rj._ret(*r, cor=rj.BORDA if self.sobre(r) and ativo else rj.LATERAL, raio=8 * e)
            cor_txt = rj.TEXTO if ativo else rj.TEXTO_3
        tam = 14
        rj._txt((r[0] + r[2] - rj._largura(rotulo, tam)) / 2, (r[1] + r[3]) / 2 - 5 * e, rotulo, cor_txt, tam)
        if ativo:
            self.alvos.append((r, acao, valor))

    def caixa_marcar(self, x, y, rotulo, ligado, acao, valor):
        e = self.e
        r = (x, y, x + 18 * e, y + 18 * e)
        alvo = (x, y - 4 * e, x + 26 * e + rj._largura(rotulo, 13), y + 22 * e)
        rj._ret(*r, cor=rj.DOURADO if ligado else (rj.TEXTO_3 if self.sobre(alvo) else rj.BORDA), raio=4 * e)
        if not ligado:
            rj._ret(r[0] + 2 * e, r[1] + 2 * e, r[2] - 2 * e, r[3] - 2 * e, rj.PAINEL, raio=3 * e)
        else:
            _visto(x + 9 * e, y + 9 * e, 6 * e, rj.ESCURO)
        rj._txt(x + 28 * e, y + 4 * e, rotulo, rj.TEXTO, 13)
        self.alvos.append((alvo, acao, valor))

    def campo(self, x0, y1, largura, chave, rotulo, dica):
        e = self.e
        rj._txt(x0, y1 - 14 * e, rotulo, rj.TEXTO, 14)
        r = (x0, y1 - 58 * e, x0 + largura, y1 - 24 * e)
        foco = estado.get("foco") == chave
        rj._moldura(*r, cor=rj.DOURADO if foco else (rj.TEXTO_3 if self.sobre(r) else rj.BORDA),
                    raio=6 * e, espessura=(2 if foco else 1) * e)
        texto = _valor(chave)
        visivel = texto
        while visivel and rj._largura(visivel, 15) > largura - 24 * e:
            visivel = visivel[1:]
        rj._txt(r[0] + 12 * e, r[1] + 11 * e, visivel, rj.TEXTO, 15)
        if foco:
            corte = len(visivel) - (len(texto) - min(estado.get("cursor", 0), len(texto)))
            cx = r[0] + 12 * e + rj._largura(visivel[:max(0, corte)], 15)
            rj._ret(cx, r[1] + 8 * e, cx + max(1.0, 1.5 * e), r[3] - 8 * e, rj.TEXTO)
        rj._txt(x0, r[1] - 20 * e, dica, rj.TEXTO_3, 12)
        self.alvos.append((r, "foco", chave))
        return r[1] - 32 * e


def _visto(cx, cy, r, cor):
    bgl.glColor4f(cor[0], cor[1], cor[2], 1.0)
    bgl.glLineWidth(max(1.0, 2.0 * rt._escala()))
    bgl.glBegin(bgl.GL_LINE_STRIP)
    bgl.glVertex2f(cx - r, cy)
    bgl.glVertex2f(cx - r * 0.3, cy - r * 0.7)
    bgl.glVertex2f(cx + r, cy + r * 0.7)
    bgl.glEnd()
    bgl.glLineWidth(1.0)


def _desenhar_tudo():
    win = bpy.context.window
    tela = _Tela()
    e = tela.e
    larg, alt = min(860 * e, win.width - 40 * e), min(600 * e, win.height - 40 * e)
    x0, y0 = int((win.width - larg) / 2), int((win.height - alt) / 2)
    x1, y1 = x0 + larg, y0 + alt
    estado["caixa"] = (x0, y0, x1, y1)
    rj._ret(x0 - 1, y0 - 1, x1 + 1, y1 + 1, rj.BORDA, raio=11 * e)
    rj._ret(x0, y0, x1, y1, rj.FUNDO, raio=10 * e)

    # ---- topo
    topo = 92 * e
    m1 = y1 - topo
    rj._ret(x0, m1, x1, y1, rj.PAINEL, raio=10 * e)
    rj._ret(x0, m1, x1, m1 + 12 * e, rj.PAINEL)
    rj._ret(x0, m1, x1, m1 + 1, rj.BORDA)
    cy = m1 + topo / 2
    if not rj._imagem(x0 + 24 * e, cy - 28 * e, x0 + 80 * e, cy + 28 * e):
        rj._icone_cubo(x0 + 52 * e, cy, 20 * e, rj.DOURADO)
    rj._txt(x0 + 96 * e, cy + 4 * e, _t("titulo"), rj.TEXTO, 24)
    rj._txt(x0 + 96 * e, cy - 20 * e, _t("sub"), rj.TEXTO_2, 13)
    fechar = (x1 - 64 * e, cy - 20 * e, x1 - 24 * e, cy + 20 * e)
    exportando = estado.get("pagina") == 3 and not estado.get("erro")
    if not exportando:
        if tela.sobre(fechar):
            rj._ret(*fechar, cor=rj.BORDA, raio=8 * e)
        rj._icone_x((fechar[0] + fechar[2]) / 2, cy, 7 * e, rj.TEXTO if tela.sobre(fechar) else rj.TEXTO_2)
        tela.alvos.append((fechar, "fechar", None))

    # ---- passos
    pagina = estado.get("pagina", 1)
    faixa = 64 * e
    s1 = m1 - faixa
    n = len(PASSOS)
    passo_x0, passo_x1 = x0 + 48 * e, x1 - 48 * e
    largura_passo = (passo_x1 - passo_x0) / n
    for i, chave in enumerate(PASSOS):
        numero = i + 1
        cx = passo_x0 + largura_passo * i + 16 * e
        ccy = s1 + faixa / 2
        if i:  # linha até o passo anterior
            inicio = cx - largura_passo + 22 * e + rj._largura(_t(PASSOS[i - 1]), 13) + 12 * e
            if cx - 24 * e > inicio:
                rj._ret(inicio, ccy - 1 * e, cx - 24 * e, ccy + 1 * e, rj.BORDA)
        feito = numero < pagina or (pagina == 4 and numero == 4)
        atual = numero == pagina
        cor = rj.VERDE if feito else (rj.DOURADO if atual else rj.BORDA)
        rj._ret(cx - 14 * e, ccy - 14 * e, cx + 14 * e, ccy + 14 * e, cor, raio=14 * e)
        if feito:
            _visto(cx, ccy, 6 * e, rj.ESCURO)
        else:
            rj._txt(cx - rj._largura(str(numero), 13) / 2, ccy - 5 * e, str(numero),
                    rj.ESCURO if atual else rj.TEXTO_2, 13)
        rj._txt(cx + 22 * e, ccy - 5 * e, _t(chave), rj.TEXTO if atual else rj.TEXTO_2, 13)
    rj._ret(x0, s1, x1, s1 + 1, rj.BORDA)

    # ---- rodapé
    rodape = 72 * e
    f1 = y0 + rodape
    rj._ret(x0, y0, x1, f1, rj.LATERAL, raio=10 * e)
    rj._ret(x0, f1 - 12 * e, x1, f1, rj.LATERAL)
    rj._ret(x0, f1 - 1, x1, f1, rj.BORDA)

    # ---- conteúdo
    c0, c1 = x0 + 48 * e, x1 - 48 * e
    topo_c = s1 - 32 * e
    {0: _pagina_projeto, 1: _pagina_jogo, 2: _pagina_plataformas, 3: _pagina_exportando,
     4: _pagina_pronto}[pagina](tela, c0, f1 + 16 * e, c1, topo_c, x0, y0, x1, f1)
    estado["alvos"] = tela.alvos


def _rodape(tela, x0, y0, x1, y1, voltar, principal, acao, ativo=True, aviso=None):
    e = tela.e
    cy = (y0 + y1) / 2
    if voltar:
        tela.botao((x0 + 32 * e, cy - 20 * e, x0 + 152 * e, cy + 20 * e), _t("voltar"), "pagina", voltar)
    if principal:
        largura = max(160 * e, rj._largura(principal, 14) + 48 * e)
        tela.botao((x1 - 32 * e - largura, cy - 22 * e, x1 - 32 * e, cy + 22 * e), principal, acao,
                   primario=True, ativo=ativo)
        if aviso:
            rj._txt(x1 - 48 * e - largura - rj._largura(aviso, 13), cy - 5 * e, aviso, rj.TEXTO_2, 13)


def _pagina_projeto(tela, x0, y0, x1, y1, fx0, fy0, fx1, fy1):
    e = tela.e
    rj._txt(x0, y1 - 20 * e, _t("proj_t"), rj.TEXTO, 20)
    y = y1 - 60 * e
    for chave in ("proj_1", "proj_2"):
        for linha in rj._quebrar(_t(chave), x1 - x0, 14):
            rj._txt(x0, y, linha, rj.TEXTO_2, 14)
            y -= 22 * e
    from bl_ui.properties_scene import game_name
    nome = _nome_pasta(game_name(_cena()) or "MyGame")
    exemplo = os.path.join("...", nome, "data", nome + ".range")
    rj._ret(x0, y - 18 * e, x1, y + 14 * e, rj.PAINEL, raio=6 * e)
    rj._txt(x0 + 12 * e, y - 7 * e, exemplo, rj.TEXTO, 14)
    y -= 56 * e
    for linha in rj._quebrar(_t("proj_3"), x1 - x0, 12):
        rj._txt(x0, y, linha, rj.TEXTO_3, 12)
        y -= 18 * e
    _rodape(tela, fx0, fy0, fx1, fy1, None, _t("proj_b"), "projeto")


def _nome_pasta(nome):
    proibidos = '<>:"/\\|?*'
    limpo = "".join("_" if ch in proibidos else ch for ch in nome).strip(" .")
    return limpo or "MyGame"


def _pagina_jogo(tela, x0, y0, x1, y1, fx0, fy0, fx1, fy1):
    e = tela.e
    rj._txt(x0, y1 - 20 * e, _t("jogo_t"), rj.TEXTO, 20)
    largura = (x1 - x0) * 0.58
    y = y1 - 52 * e
    y = tela.campo(x0, y, largura, "nome", _t("nome"), _t("nome_d"))
    y = tela.campo(x0, y - 8 * e, min(largura, 220 * e), "versao", _t("versao"), _t("versao_d"))

    # Ícone à direita: prévia + escolher/tirar.
    from bl_ui.properties_scene import game_icon
    ix0 = x0 + largura + 48 * e
    rj._txt(ix0, y1 - 66 * e, _t("icone"), rj.TEXTO, 14)
    lado = 112 * e
    r = (ix0, y1 - 84 * e - lado, ix0 + lado, y1 - 84 * e)
    icone = game_icon(_cena())
    rj._ret(*r, cor=rj.PAINEL, raio=10 * e)
    if not (icone and icone.lower().endswith(".png") and rj._imagem(*r, caminho=icone)):
        rj._icone_cubo((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, 28 * e, rj.TEXTO_3 if not icone else rj.DOURADO)
    yb = r[1] - 44 * e
    tela.botao((ix0, yb, ix0 + 112 * e, yb + 34 * e), _t("escolher"), "icone")
    if icone:
        tela.botao((ix0 + 120 * e, yb, ix0 + 196 * e, yb + 34 * e), _t("tirar"), "tirar_icone")
    texto = os.path.basename(icone) if icone else _t("sem_icone")
    rj._txt(ix0, yb - 22 * e, rj._cortar(texto, x1 - ix0, 12), rj.TEXTO_3, 12)
    rj._txt(ix0, yb - 40 * e, rj._cortar(_t("icone_d"), x1 - ix0, 12), rj.TEXTO_3, 12)

    tem_nome = bool(_valor("nome").strip())
    _rodape(tela, fx0, fy0, fx1, fy1, None, _t("proximo"), "pagina_2", ativo=tem_nome,
            aviso=None if tem_nome else _t("falta_nome"))


def _pagina_plataformas(tela, x0, y0, x1, y1, fx0, fy0, fx1, fy1):
    e = tela.e
    exp = _cena().rangearmor_export
    rj._txt(x0, y1 - 20 * e, _t("plat_t"), rj.TEXTO, 20)
    vao = 24 * e
    larg = (x1 - x0 - vao) / 2
    ct1 = y1 - 44 * e
    ct0 = ct1 - 120 * e
    for i, (alvo, prop, titulo, dica) in enumerate((("Windows64", "export_windows64", "Windows", "win_d"),
                                                     ("Linux64", "export_linux64", "Linux", "lin_d"))):
        r = (x0 + i * (larg + vao), ct0, x0 + i * (larg + vao) + larg, ct1)
        existe = _runtime_ok(alvo)
        ligado = getattr(exp, prop) and existe
        borda = rj.DOURADO if ligado else (rj.TEXTO_3 if tela.sobre(r) and existe else rj.BORDA)
        rj._moldura(*r, cor=borda, raio=10 * e, espessura=2 * e)
        rj._txt(r[0] + 20 * e, r[3] - 40 * e, titulo, rj.TEXTO if existe else rj.TEXTO_3, 20)
        rj._txt(r[0] + 20 * e, r[3] - 66 * e, _t(dica) if existe else _t("sem_rt"), rj.TEXTO_2, 13)
        # Marca no canto: interruptor.
        sw = (r[2] - 64 * e, r[3] - 44 * e, r[2] - 20 * e, r[3] - 20 * e)
        rj._ret(*sw, cor=rj.DOURADO if ligado else rj.BORDA, raio=12 * e)
        bx = sw[2] - 22 * e if ligado else sw[0] + 2 * e
        rj._ret(bx, sw[1] + 2 * e, bx + 20 * e, sw[3] - 2 * e, rj.PAINEL, raio=10 * e)
        rj._txt(r[0] + 20 * e, r[1] + 18 * e, _t("ligado") if ligado else _t("desligado"),
                rj.VERDE if ligado else rj.TEXTO_3, 12)
        if existe:
            tela.alvos.append((r, "alternar", prop))
    y = ct0 - 26 * e
    rj._txt(x0, y, _t("os_dois"), rj.TEXTO_3, 12)

    y -= 40 * e
    rj._txt(x0, y, _t("opcoes").upper(), rj.TEXTO_3, 11)
    y -= 30 * e
    col2 = x0 + (x1 - x0) / 2
    tela.caixa_marcar(x0, y, _t("o_zip"), exp.make_archive, "opcao", "make_archive")
    tela.caixa_marcar(col2, y, _t("o_cook"), exp.cook_before_export, "opcao", "cook_before_export")
    y -= 32 * e
    tela.caixa_marcar(x0, y, _t("o_pyc"), exp.compile_scripts, "opcao", "compile_scripts")
    tela.caixa_marcar(col2, y, _t("o_debug"), exp.keep_debug_overlays, "opcao", "keep_debug_overlays")
    y -= 36 * e
    rj._txt(x0, y, _t("protegido"), rj.TEXTO_3, 12)

    tem = bool(_plataformas())
    _rodape(tela, fx0, fy0, fx1, fy1, 1, _t("exportar"), "exportar", ativo=tem,
            aviso=None if tem else _t("nenhuma"))


def _pagina_exportando(tela, x0, y0, x1, y1, fx0, fy0, fx1, fy1):
    e = tela.e
    erro = estado.get("erro")
    rj._txt(x0, y1 - 20 * e, _t("erro_t") if erro else _t("exp_t"), rj.TEXTO, 20)
    lista = estado["lista"]
    feitas = sum(1 for n in lista if estado["etapas"].get(n) == "feito")
    # Barra de progresso.
    by = y1 - 48 * e
    rj._ret(x0, by, x1, by + 8 * e, rj.BORDA, raio=4 * e)
    if feitas:
        rj._ret(x0, by, x0 + (x1 - x0) * feitas / len(lista), by + 8 * e, rj.VERDE if not erro else rj.DOURADO,
                raio=4 * e)
    y = by - 40 * e
    for nome in lista:
        situacao = estado["etapas"].get(nome)
        cx, cy = x0 + 12 * e, y + 6 * e
        if situacao == "feito":
            rj._ret(cx - 11 * e, cy - 11 * e, cx + 11 * e, cy + 11 * e, rj.VERDE, raio=11 * e)
            _visto(cx, cy, 5 * e, rj.ESCURO)
        elif situacao == "andando":
            rj._ret(cx - 11 * e, cy - 11 * e, cx + 11 * e, cy + 11 * e, rj.DOURADO, raio=11 * e)
            rj._ret(cx - 4 * e, cy - 4 * e, cx + 4 * e, cy + 4 * e, rj.ESCURO, raio=4 * e)
        elif situacao == "erro":
            rj._ret(cx - 11 * e, cy - 11 * e, cx + 11 * e, cy + 11 * e, (0.85, 0.33, 0.30), raio=11 * e)
            rj._icone_x(cx, cy, 4 * e, (1, 1, 1))
        else:
            rj._ret(cx - 11 * e, cy - 11 * e, cx + 11 * e, cy + 11 * e, rj.BORDA, raio=11 * e)
        cor = rj.TEXTO if situacao in ("andando", "erro") else (rj.TEXTO_2 if situacao == "feito" else rj.TEXTO_3)
        rj._txt(x0 + 36 * e, y, _t("e_" + nome), cor, 15)
        y -= 38 * e

    # Última linha do log ou o erro.
    y -= 8 * e
    if erro:
        for linha in rj._quebrar(erro, x1 - x0, 13)[:4]:
            rj._txt(x0, y, linha, (0.85, 0.33, 0.30), 13)
            y -= 20 * e
        if estado.get("copiado"):
            rj._txt(x0, y - 4 * e, _t("log_copiado"), rj.TEXTO_3, 12)
    else:
        ultima = next((l for l in reversed(estado.get("log", [])) if l.strip() and not l.startswith("@")), "")
        rj._txt(x0, y, rj._cortar(ultima, x1 - x0, 12), rj.TEXTO_3, 12)

    if erro:
        e2 = tela.e
        cy = (fy0 + fy1) / 2
        tela.botao((fx0 + 32 * e2, cy - 20 * e2, fx0 + 152 * e2, cy + 20 * e2), _t("voltar"), "pagina", 2)
        tela.botao((fx0 + 164 * e2, cy - 20 * e2, fx0 + 304 * e2, cy + 20 * e2), _t("copiar_log"), "copiar_log")
        tela.botao((fx1 - 192 * e2, cy - 22 * e2, fx1 - 32 * e2, cy + 22 * e2), _t("exportar"), "exportar",
                   primario=True)
    else:
        cy = (fy0 + fy1) / 2
        tela.botao((fx1 - 172 * e, cy - 20 * e, fx1 - 32 * e, cy + 20 * e), _t("cancelar"), "cancelar")


def _pagina_pronto(tela, x0, y0, x1, y1, fx0, fy0, fx1, fy1):
    e = tela.e
    rj._ret(x0, y1 - 28 * e, x0 + 28 * e, y1, rj.VERDE, raio=14 * e)
    _visto(x0 + 14 * e, y1 - 14 * e, 7 * e, rj.ESCURO)
    rj._txt(x0 + 40 * e, y1 - 20 * e, _t("ok_t"), rj.TEXTO, 20)
    y = y1 - 64 * e
    for linha in rj._quebrar(_t("ok_1"), x1 - x0, 14):
        rj._txt(x0, y, linha, rj.TEXTO_2, 14)
        y -= 22 * e
    y -= 6 * e
    release = os.path.normpath(os.path.join(estado.get("projeto", ""), "release"))
    rj._ret(x0, y - 18 * e, x1, y + 14 * e, rj.PAINEL, raio=6 * e)
    rj._txt(x0 + 12 * e, y - 7 * e, rj._cortar(release, x1 - x0 - 24 * e, 14), rj.TEXTO, 14)
    y -= 48 * e
    for alvo, pasta in sorted(estado.get("saidas", {}).items()):
        rj._txt(x0, y, alvo, rj.TEXTO_2, 13)
        rj._txt(x0 + 110 * e, y, rj._cortar(os.path.basename(pasta), x1 - x0 - 110 * e, 13), rj.TEXTO, 13)
        y -= 22 * e
    y -= 16 * e
    tela.botao((x0, y - 40 * e, x0 + 180 * e, y), _t("abrir"), "abrir", release)
    pasta = estado.get("saidas", {}).get(HOST) or estado.get("saidas", {}).get("Universal")
    exe = _executavel(pasta) if pasta else None
    tela.botao((x0 + 192 * e, y - 40 * e, x0 + 372 * e, y), _t("testar"), "testar", exe, ativo=bool(exe))

    cy = (fy0 + fy1) / 2
    tela.botao((fx0 + 32 * e, cy - 20 * e, fx0 + 212 * e, cy + 20 * e), _t("de_novo"), "pagina", 1)
    tela.botao((fx1 - 172 * e, cy - 22 * e, fx1 - 32 * e, cy + 22 * e), _t("fechar"), "fechar", primario=True)


# ---------------------------------------------------------------- operadores

def _fechar(context=None):
    if not estado:
        return
    trab = estado.get("trabalho")
    if trab is not None:
        trab.cancelar()
    if estado.get("timer") is not None:
        bpy.context.window_manager.event_timer_remove(estado["timer"])
    bpy.types.WindowManager.draw_handler_remove(estado["handle"])
    estado.clear()
    rt._redesenhar()


class WM_OT_export_to_desktop(Operator):
    """Turn this file into a game for Windows and Linux, ready to share (step by step)"""
    bl_idname = "wm.export_to_desktop"
    bl_label = "Export to Desktop"

    page: bpy.props.IntProperty(default=1, options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return not bpy.app.background

    def invoke(self, context, event):
        _fechar(context)
        rj._aplicar_tema()
        self.chave = object()
        pagina = self.page if _projeto() else 0
        estado.update(chave=self.chave, janela=context.window.as_pointer(), pagina=pagina, alvos=[], foco=None,
                      mouse=(event.mouse_x, event.mouse_y),
                      timer=context.window_manager.event_timer_add(0.1, context.window),
                      handle=bpy.types.WindowManager.draw_handler_add(_desenhar, ()))
        from bl_ui.properties_scene import game_name, migrate_game_info
        migrate_game_info(context.scene)  # arquivo de antes do bloco Game: traz nome, versão e ícone antigos
        if pagina == 1 and not _valor("nome").strip():
            _gravar("nome", game_name(context.scene))  # sem nada antigo: o nome do arquivo, para editar
        context.window_manager.modal_handler_add(self)
        rt._redesenhar()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if estado.get("chave") is not self.chave:
            return {'CANCELLED'}
        if event.type == 'TIMER':
            if estado.get("pagina") == 3:
                _passo_exportacao(context)
                rt._redesenhar()
            return {'PASS_THROUGH'}
        estado["mouse"] = (event.mouse_x, event.mouse_y)
        if _tecla(context, event):
            rt._redesenhar()
            return {'RUNNING_MODAL'}
        exportando = estado.get("pagina") == 3 and not estado.get("erro")
        if event.type == 'ESC' and event.value == 'PRESS' and not exportando:
            _fechar(context)
            return {'CANCELLED'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            for r, acao, valor in estado.get("alvos", []):
                if rj._dentro(r, event.mouse_x, event.mouse_y):
                    resultado = self.clicar(context, acao, valor)
                    rt._redesenhar()
                    return resultado
            _focar(None)
        rt._redesenhar()
        return {'RUNNING_MODAL'}  # janela modal: o editor por baixo não recebe nada

    def clicar(self, context, acao, valor):
        exp = context.scene.rangearmor_export
        if acao != "foco":
            _focar(None)
        if acao == "fechar":
            _fechar(context)
            return {'CANCELLED'}
        if acao == "foco":
            _focar(valor)
        elif acao == "pagina":
            estado.update(pagina=valor, erro=None, copiado=False)
        elif acao == "pagina_2":
            estado["pagina"] = 2
        elif acao == "alternar":
            setattr(exp, valor, not getattr(exp, valor))
        elif acao == "opcao":
            setattr(exp, valor, not getattr(exp, valor))
        elif acao == "tirar_icone":
            context.scene.range_game_info.icon = ""
            exp.icon_path = ""
        elif acao == "exportar":
            _comecar_exportacao(context)
        elif acao == "cancelar":
            if estado.get("trabalho") is not None:
                estado["trabalho"].cancelar()
            elif estado.get("preparar"):
                # Ainda não começou (esperando o redesenho): não começa.
                estado["preparar"] = 0
                estado["etapas"]["preparar"] = "erro"
                estado["erro"] = _t("cancelado")
        elif acao == "copiar_log":
            context.window_manager.clipboard = "\n".join(estado.get("log", []) + [estado.get("erro") or ""])
            estado["copiado"] = True
        elif acao == "abrir":
            _abrir(valor)
        elif acao == "testar":
            subprocess.Popen([valor], cwd=os.path.dirname(valor))
        elif acao in ("icone", "projeto"):
            # O seletor de arquivos do editor não abre por cima da janela: fecha, escolhe e reabre.
            _fechar(context)
            if acao == "icone":
                bpy.ops.wm.export_desktop_icon('INVOKE_DEFAULT')
            else:
                bpy.ops.wm.export_desktop_project('INVOKE_DEFAULT')
            return {'FINISHED'}
        return {'RUNNING_MODAL'}


def _reabrir(pagina):
    def abrir():
        bpy.ops.wm.export_to_desktop('INVOKE_DEFAULT', page=pagina)
        return None
    abrir()


class WM_OT_export_desktop_icon(Operator):
    """Choose the PNG image used as the game icon"""
    bl_idname = "wm.export_desktop_icon"
    bl_label = "Choose Icon"
    bl_options = {'INTERNAL'}

    filepath: StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    filter_image: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        caminho = self.filepath
        if not caminho.lower().endswith((".png", ".ico")):
            self.report({'WARNING'}, "Choose a PNG image (or an .ico file)")
        else:
            try:
                caminho = bpy.path.relpath(caminho) if bpy.data.filepath else caminho
            except ValueError:
                pass  # outro disco no Windows: fica absoluto
            context.scene.range_game_info.icon = caminho
        _reabrir(1)
        return {'FINISHED'}

    def cancel(self, context):
        _reabrir(1)


class WM_OT_export_desktop_project(Operator):
    """Create the project folder (<Name>/data/) and save the open file inside it"""
    bl_idname = "wm.export_desktop_project"
    bl_label = "Create Project Here"
    bl_options = {'INTERNAL'}

    directory: StringProperty(subtype='DIR_PATH', options={'SKIP_SAVE'})
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})

    def invoke(self, context, event):
        atual = bpy.data.filepath
        self.directory = os.path.dirname(atual) + os.sep if atual else os.path.expanduser("~") + os.sep
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from bl_ui.properties_scene import game_name
        pai = bpy.path.abspath(self.directory)
        if not os.path.isdir(pai):
            self.report({'ERROR'}, "The selected folder does not exist")
            _reabrir(0)
            return {'CANCELLED'}
        nome = _nome_pasta(game_name(context.scene) or "MyGame")
        projeto, n = os.path.join(pai, nome), 2
        while os.path.exists(os.path.join(projeto, "data")):
            projeto, n = os.path.join(pai, "%s (%d)" % (nome, n)), n + 1
        arquivo = os.path.join(projeto, "data", nome + ".range")
        try:
            os.makedirs(os.path.dirname(arquivo))
        except OSError as erro:
            self.report({'ERROR'}, "Could not create the project folder: %s" % erro)
            _reabrir(0)
            return {'CANCELLED'}
        if bpy.ops.wm.save_as_mainfile('EXEC_DEFAULT', filepath=arquivo, check_existing=False) != {'FINISHED'}:
            self.report({'ERROR'}, "Could not save the file in the project")
            _reabrir(0)
            return {'CANCELLED'}
        self.report({'INFO'}, "Project created: %s" % projeto)
        _reabrir(1)
        return {'FINISHED'}

    def cancel(self, context):
        _reabrir(0)


classes = (WM_OT_export_to_desktop, WM_OT_export_desktop_icon, WM_OT_export_desktop_project)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    _fechar()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
