"""Range Trace launcher: a window that picks the game, the player and the trace modules,
runs the game and opens the report when it closes (docs/range-trace.md).

Choices are remembered in %APPDATA%\\AnastacioEngine\\range_trace_launcher.json; nothing is
written next to the game. Usage: pythonw tools/debug/range_trace_launcher.py [jogo.range]
"""
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RELATORIO = os.path.join(RAIZ, 'tools', 'debug', 'relatorio_trace.py')
CONFIG = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'AnastacioEngine',
                      'range_trace_launcher.json')

# (nome, descrição). Novos módulos entram aqui quando o CM_Trace os aceitar.
MODULOS = (
    ('load', 'Carga: cenas, objetos, malhas, materiais, imagens, On Demand'),
    ('usage', 'Uso: primeiro frame em que cada objeto é desenhado; envio de imagens'),
)

PADRAO = {
    'jogo': r'D:\ProjetoRolimaRacer\RolimaRacer.range',
    'exe': os.path.join(RAIZ, 'build', 'bin', 'AnastacioRuntime.exe'),
    'modulos': [m for m, _ in MODULOS],
    'saida': os.path.join(RAIZ, 'debug-logs'),
    'abrir_relatorio': True,
}


def ler_config():
    cfg = dict(PADRAO)
    try:
        with open(CONFIG, encoding='utf-8') as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def salvar_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        with open(CONFIG, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


class Launcher(tk.Tk):
    def __init__(self, jogo=None):
        super().__init__()
        self.title('Range Trace')
        self.resizable(True, False)
        cfg = ler_config()
        if jogo:
            cfg['jogo'] = os.path.abspath(jogo)

        self.jogo = tk.StringVar(value=cfg['jogo'])
        self.exe = tk.StringVar(value=cfg['exe'])
        self.saida = tk.StringVar(value=cfg['saida'])
        self.abrir = tk.BooleanVar(value=cfg['abrir_relatorio'])
        self.mods = {m: tk.BooleanVar(value=m in cfg['modulos']) for m, _ in MODULOS}
        self.status = tk.StringVar(value='Escolha o jogo e os módulos.')

        quadro = ttk.Frame(self, padding=12)
        quadro.pack(fill='both', expand=True)
        quadro.columnconfigure(1, weight=1)

        def linha(r, rotulo, var, escolher):
            ttk.Label(quadro, text=rotulo).grid(row=r, column=0, sticky='w', pady=3)
            ttk.Entry(quadro, textvariable=var, width=60).grid(row=r, column=1, sticky='ew', padx=6)
            ttk.Button(quadro, text='...', width=3, command=escolher).grid(row=r, column=2)

        linha(0, 'Jogo', self.jogo, lambda: self.escolher_arquivo(
            self.jogo, (('Jogo', '*.range *.blend'), ('Todos', '*.*'))))
        linha(1, 'Executável', self.exe, lambda: self.escolher_arquivo(
            self.exe, (('Executável', '*.exe'), ('Todos', '*.*'))))
        linha(2, 'Saída', self.saida, self.escolher_pasta)

        grupo = ttk.LabelFrame(quadro, text='Módulos', padding=8)
        grupo.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(10, 4))
        for i, (m, descricao) in enumerate(MODULOS):
            ttk.Checkbutton(grupo, text='%s  -  %s' % (m, descricao),
                            variable=self.mods[m]).grid(row=i, column=0, sticky='w')

        ttk.Checkbutton(quadro, text='Abrir o relatório ao fechar o jogo',
                        variable=self.abrir).grid(row=4, column=0, columnspan=3, sticky='w')

        rodape = ttk.Frame(quadro)
        rodape.grid(row=5, column=0, columnspan=3, sticky='ew', pady=(10, 0))
        rodape.columnconfigure(0, weight=1)
        ttk.Label(rodape, textvariable=self.status, wraplength=420).grid(row=0, column=0, sticky='w')
        self.botao_pasta = ttk.Button(rodape, text='Abrir pasta', command=self.abrir_pasta,
                                      state='disabled')
        self.botao_pasta.grid(row=0, column=1, padx=6)
        self.botao = ttk.Button(rodape, text='Jogar com trace', command=self.iniciar)
        self.botao.grid(row=0, column=2)
        self.pasta_trace = None

    def escolher_arquivo(self, var, tipos):
        inicial = os.path.dirname(var.get()) if var.get() else RAIZ
        caminho = filedialog.askopenfilename(initialdir=inicial, filetypes=tipos)
        if caminho:
            var.set(os.path.normpath(caminho))

    def escolher_pasta(self):
        caminho = filedialog.askdirectory(initialdir=self.saida.get() or RAIZ)
        if caminho:
            self.saida.set(os.path.normpath(caminho))

    def abrir_pasta(self):
        if self.pasta_trace:
            os.startfile(self.pasta_trace)

    def iniciar(self):
        modulos = [m for m, _ in MODULOS if self.mods[m].get()]
        jogo, exe = self.jogo.get(), self.exe.get()
        if not modulos:
            self.status.set('Ligue pelo menos um módulo.')
            return
        if not os.path.isfile(jogo):
            self.status.set('Jogo não encontrado: %s' % jogo)
            return
        if not os.path.isfile(exe):
            self.status.set('Executável não encontrado: %s' % exe)
            return
        salvar_config({'jogo': jogo, 'exe': exe, 'modulos': modulos, 'saida': self.saida.get(),
                       'abrir_relatorio': self.abrir.get()})

        self.pasta_trace = os.path.join(self.saida.get(), 'trace-' + time.strftime('%Y%m%d-%H%M%S'))
        os.makedirs(self.pasta_trace, exist_ok=True)
        env = dict(os.environ, RANGE_TRACE=self.pasta_trace, RANGE_TRACE_MODULES=','.join(modulos))
        self.botao.configure(state='disabled')
        self.botao_pasta.configure(state='normal')
        self.status.set('Jogo aberto (%s). Feche o jogo para gerar o relatório.' % ','.join(modulos))
        threading.Thread(target=self.rodar, args=(exe, jogo, env), daemon=True).start()

    def rodar(self, exe, jogo, env):
        try:
            subprocess.run([exe, jogo], cwd=os.path.dirname(jogo), env=env)
            saida = subprocess.run([sys.executable.replace('pythonw', 'python'), RELATORIO,
                                    self.pasta_trace], capture_output=True, text=True,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            html = os.path.join(self.pasta_trace, 'relatorio.html')
            if saida.returncode == 0 and os.path.isfile(html):
                msg = 'Relatório pronto em %s' % self.pasta_trace
                if self.abrir.get():
                    os.startfile(html)
            else:
                msg = 'Relatório falhou: %s' % (saida.stderr.strip().splitlines() or ['?'])[-1]
        except OSError as erro:
            msg = 'Não consegui abrir: %s' % erro
        self.after(0, self.terminou, msg)

    def terminou(self, msg):
        self.status.set(msg)
        self.botao.configure(state='normal')


if __name__ == '__main__':
    Launcher(sys.argv[1] if len(sys.argv) > 1 else None).mainloop()
