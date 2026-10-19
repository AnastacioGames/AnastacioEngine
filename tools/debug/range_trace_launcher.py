"""Anastacio Trace Launcher: a window that picks the game, the player and the trace modules,
runs the game and opens the report when it closes (docs/range-trace.md).

Choices are remembered in %APPDATA%\\AnastacioEngine\\range_trace_launcher.json; nothing is
written next to the game. Usage: pythonw tools/debug/range_trace_launcher.py [jogo.range]
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RELATORIO = os.path.join(RAIZ, 'tools', 'debug', 'relatorio_trace.py')
CONFIG = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'AnastacioEngine',
                      'range_trace_launcher.json')
LOGO = os.path.join(RAIZ, 'source', 'release', 'datafiles', 'anastacio_engine_logo_v2.png')
ICONE = os.path.join(RAIZ, 'source', 'release', 'windows', 'icons', 'anastacio-engine-icon-transparent-v1.ico')
# Gravado em cada pasta de trace pelo launcher, para a lista de relatórios saber de que jogo é.
META = 'launcher.json'
RECENTES = 6

# (nome, descrição). Novos módulos entram aqui quando o CM_Trace os aceitar.
MODULOS = (
    ('load', 'Carga: cenas, objetos, malhas, materiais, imagens, On Demand'),
    ('usage', 'Uso: primeiro frame em que cada objeto é desenhado; envio de imagens'),
    ('frames', 'Frames lentos: custo de cada frame por categoria e o que carregou junto'),
    ('sector', 'Trilho: câmera percorre a curva da pista e mede o custo por trecho'),
)
# Campos do trilho (módulo sector), lembrados por jogo.
CAMPOS_TRILHO = (('cena', 'Cena', 14), ('curva', 'Curva', 16), ('camera', 'Câmera', 20), ('segundos', 'Segundos', 6))
TRILHO_PADRAO = {
    os.path.normcase(r'D:\ProjetoRolimaRacer\RolimaRacer.range'):
        {'cena': 'Pista_1', 'curva': 'Pista1.009', 'camera': 'Camera_debug_track', 'segundos': '120'},
}

PADRAO = {
    'jogo': r'D:\ProjetoRolimaRacer\RolimaRacer.range',
    'exe': os.path.join(RAIZ, 'build', 'bin', 'AnastacioRuntime.exe'),
    'modulos': ['load', 'usage', 'frames'],
    'saida': os.path.join(RAIZ, 'debug-logs'),
    'abrir_relatorio': True,
    'tema': 'escuro',
}
# O cabeçalho fica sempre escuro: o brilho do logo foi feito para fundo escuro.
CABECALHO = '#15161a'

# Temas: dourado do logo da engine sobre fundo escuro ou claro.
TEMAS = {
    'escuro': dict(FUNDO='#15161a', CARTAO='#1f2127', BORDA='#2c2f37', CAMPO='#2a2d35', TEXTO='#e8e6e1',
                   APAGADO='#8d8f97', OURO='#f0b43c', OURO_ESCURO='#c98d1f', TEXTO_OURO='#1a1206',
                   PERIGO='#e07a6a'),
    'claro': dict(FUNDO='#f3f1ec', CARTAO='#ffffff', BORDA='#dedad2', CAMPO='#f0ede6', TEXTO='#22201c',
                  APAGADO='#6f6b63', OURO='#b07812', OURO_ESCURO='#8f600c', TEXTO_OURO='#ffffff',
                  PERIGO='#b8412f'),
}
FONTE = 'Segoe UI'


def aplicar_tema(nome):
    globals().update(TEMAS.get(nome, TEMAS['escuro']))


aplicar_tema('escuro')


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


def carregar_imagem(caminho, largura):
    """PhotoImage com a largura pedida; usa Pillow se houver, senão reduz por um fator inteiro."""
    if not caminho or not os.path.isfile(caminho):
        return None
    try:
        from PIL import Image, ImageTk
        img = Image.open(caminho)
        altura = max(1, round(img.height * largura / img.width))
        return ImageTk.PhotoImage(img.resize((largura, altura), Image.LANCZOS))
    except ImportError:
        img = tk.PhotoImage(file=caminho)
        if img.width() > largura:
            return img.subsample(max(1, img.width() // largura))
        return img.zoom(max(1, largura // img.width()))
    except Exception:
        return None


def relatorios_recentes(pasta, quantos=RECENTES):
    """[(pasta do trace, jogo ou '', data)] dos relatórios prontos, do mais novo para o mais velho."""
    try:
        nomes = [n for n in os.listdir(pasta) if n.startswith('trace-')]
    except OSError:
        return []
    achados = []
    for nome in nomes:
        caminho = os.path.join(pasta, nome)
        html = os.path.join(caminho, 'relatorio.html')
        if not os.path.isfile(html):
            continue
        jogo = ''
        try:
            with open(os.path.join(caminho, META), encoding='utf-8') as f:
                jogo = json.load(f).get('jogo', '')
        except (OSError, ValueError):
            pass
        achados.append((os.path.getmtime(html), caminho, jogo))
    achados.sort(reverse=True)
    return [(c, j, time.strftime('%d/%m %H:%M', time.localtime(t))) for t, c, j in achados[:quantos]]


def campo(pai, var):
    """Campo de texto com margem interna. tk.Entry dentro de um Frame em vez de ttk.Entry:
    a borda do tema clam deixa pontos claros nos cantos no tema escuro."""
    caixa = tk.Frame(pai, bg=CAMPO, highlightthickness=1, highlightbackground=BORDA, highlightcolor=BORDA)
    entrada = tk.Entry(caixa, textvariable=var, relief='flat', bd=0, font=(FONTE, 10), bg=CAMPO, fg=TEXTO,
                       insertbackground=TEXTO, selectbackground=OURO, selectforeground=TEXTO_OURO,
                       highlightthickness=0)
    entrada.pack(fill='x', padx=10, pady=7)
    entrada.bind('<FocusIn>', lambda _: caixa.configure(highlightbackground=OURO))
    entrada.bind('<FocusOut>', lambda _: caixa.configure(highlightbackground=BORDA))
    return caixa


def botao(pai, texto, comando, destaque=False, perigo=False, **kw):
    cor = TEXTO_OURO if destaque else (PERIGO if perigo else TEXTO)
    return tk.Button(pai, text=texto, command=comando, relief='flat', bd=0, cursor='hand2',
                     font=(FONTE, 12 if destaque else 10, 'bold' if destaque else 'normal'),
                     bg=OURO if destaque else CAMPO, fg=cor,
                     activebackground=OURO_ESCURO if destaque else BORDA,
                     activeforeground=cor, disabledforeground=APAGADO,
                     padx=24 if destaque else 12, pady=10 if destaque else 5, **kw)


class Launcher(tk.Tk):
    def __init__(self, jogo=None):
        # Sem isto o Windows amplia a janela como bitmap em telas com escala > 100% e a fonte fica borrada.
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass
        super().__init__()
        self.escala = self.winfo_fpixels('1i') / 96.0
        self.title('Anastacio Trace Launcher')
        self.minsize(int(860 * self.escala), 0)
        try:
            self.iconbitmap(ICONE)
        except tk.TclError:
            pass
        cfg = ler_config()
        if jogo:
            cfg['jogo'] = os.path.abspath(jogo)

        self.jogo = tk.StringVar(value=cfg['jogo'])
        self.exe = tk.StringVar(value=cfg['exe'])
        self.saida = tk.StringVar(value=cfg['saida'])
        self.abrir = tk.BooleanVar(value=cfg['abrir_relatorio'])
        self.mods = {m: tk.BooleanVar(value=m in cfg['modulos']) for m, _ in MODULOS}
        self.status = tk.StringVar(value='Escolha o jogo e os módulos, depois clique em Jogar com trace.')
        self.pasta_trace = None
        self.imagens = {}
        self.trilhos = cfg.get('trilhos', {})
        self.trilho_vars = {chave: tk.StringVar() for chave, _, _ in CAMPOS_TRILHO}
        self.trilho_inverter = tk.BooleanVar()
        self.carregar_trilho()
        self.jogo.trace_add('write', lambda *_: self.carregar_trilho())
        self.tema = cfg['tema'] if cfg['tema'] in TEMAS else 'escuro'
        self.rodando = False
        self.montar()

    def trocar_tema(self):
        self.tema = 'claro' if self.tema == 'escuro' else 'escuro'
        cfg = ler_config()
        cfg['tema'] = self.tema
        salvar_config(cfg)
        for filho in self.winfo_children():
            filho.destroy()
        self.montar()

    def montar(self):
        aplicar_tema(self.tema)
        self.configure(bg=FUNDO)
        estilo = ttk.Style(self)
        estilo.theme_use('clam')
        estilo.configure('TEntry', fieldbackground=CAMPO, foreground=TEXTO, insertcolor=TEXTO,
                         bordercolor=BORDA, lightcolor=BORDA, darkcolor=BORDA, padding=6)
        for nome, fundo in (('TCheckbutton', CARTAO), ('Fundo.TCheckbutton', FUNDO)):
            estilo.configure(nome, background=fundo, foreground=TEXTO, font=(FONTE, 10),
                             indicatorbackground=CAMPO, indicatorforeground=OURO, focuscolor=fundo)
            estilo.map(nome, background=[('active', fundo)], indicatorbackground=[('active', BORDA)])

        # Cabeçalho com o logo da engine (sempre escuro) e a troca de tema.
        faixa = tk.Frame(self, bg=CABECALHO)
        faixa.pack(fill='x', pady=(0, 14))
        topo = tk.Frame(faixa, bg=CABECALHO)
        topo.pack(fill='x', padx=24, pady=(8, 6))
        if 'logo' not in self.imagens:
            self.imagens['logo'] = carregar_imagem(LOGO, int(290 * self.escala))
        if self.imagens['logo']:
            tk.Label(topo, image=self.imagens['logo'], bg=CABECALHO).pack(side='left')
        else:
            tk.Label(topo, text='ANASTACIO ENGINE', bg=CABECALHO, fg='#f0b43c',
                     font=(FONTE, 22, 'bold')).pack(side='left')
        lado = tk.Frame(topo, bg=CABECALHO)
        lado.pack(side='right')
        tk.Button(lado, text='\u2600  Tema claro' if self.tema == 'escuro' else '\u263e  Tema escuro',
                  command=self.trocar_tema, relief='flat', bd=0, cursor='hand2', font=(FONTE, 9),
                  bg='#2a2d35', fg='#e8e6e1', activebackground='#3a3d45', activeforeground='#ffffff',
                  padx=10, pady=2).pack(anchor='e', pady=(0, 4))
        tk.Label(lado, text='Trace Launcher', bg=CABECALHO, fg='#e8e6e1', font=(FONTE, 16, 'bold')).pack(anchor='e')
        tk.Label(lado, text='o que o jogo carrega e o que ele de fato desenha', bg=CABECALHO, fg='#8d8f97',
                 font=(FONTE, 10)).pack(anchor='e')

        # Jogo: ícone (icon.png da pasta do jogo), nome e caminho.
        corpo = self.cartao('Jogo')
        corpo.columnconfigure(1, weight=1)
        self.icone_jogo = tk.Label(corpo, bg=CAMPO, fg=APAGADO, font=(FONTE, 26, 'bold'))
        self.icone_jogo.grid(row=0, column=0, rowspan=2, padx=(0, 16))
        self.nome_jogo = tk.Label(corpo, bg=CARTAO, fg=TEXTO, font=(FONTE, 17, 'bold'), anchor='w')
        self.nome_jogo.grid(row=0, column=1, columnspan=2, sticky='ew')
        campo(corpo, self.jogo).grid(row=1, column=1, sticky='ew', padx=(0, 8))
        botao(corpo, 'Procurar...', lambda: self.escolher_arquivo(
            self.jogo, (('Jogo', '*.range *.blend'), ('Todos', '*.*')))).grid(row=1, column=2)
        self.jogo.trace_add('write', lambda *_: self.atualizar_jogo())
        self.atualizar_jogo()

        # Módulos.
        corpo = self.cartao('Módulos')
        for m, descricao in MODULOS:
            linha = tk.Frame(corpo, bg=CARTAO)
            linha.pack(fill='x', pady=3)
            ttk.Checkbutton(linha, variable=self.mods[m]).pack(side='left')
            tk.Label(linha, text=m, bg=CARTAO, fg=OURO, font=(FONTE, 11, 'bold'), width=7,
                     anchor='w').pack(side='left')
            tk.Label(linha, text=descricao, bg=CARTAO, fg=TEXTO, font=(FONTE, 10), anchor='w').pack(side='left')

        # Trilho de câmera (módulo sector).
        corpo = self.cartao('Trilho de câmera (sector)')
        for i, (chave, rotulo, largura) in enumerate(CAMPOS_TRILHO):
            corpo.columnconfigure(i, weight=largura)
            tk.Label(corpo, text=rotulo, bg=CARTAO, fg=APAGADO, font=(FONTE, 9), anchor='w').grid(
                row=0, column=i, sticky='w', padx=(0, 8))
            campo(corpo, self.trilho_vars[chave]).grid(row=1, column=i, sticky='ew', padx=(0, 8))
        tk.Label(corpo, text='Com o módulo sector ligado, a câmera entra na curva quando a cena carrega, anda em '
                 'velocidade constante olhando para a frente e o jogo fecha no fim. VSync fica desligado no trilho.',
                 bg=CARTAO, fg=APAGADO, font=(FONTE, 9), justify='left', anchor='w',
                 wraplength=int(760 * self.escala)).grid(row=2, column=0, columnspan=len(CAMPOS_TRILHO),
                                                         sticky='w', pady=(8, 0))
        ttk.Checkbutton(corpo, text='Inverter sentido (do último ponto da curva para o primeiro)',
                        variable=self.trilho_inverter).grid(row=3, column=0, columnspan=len(CAMPOS_TRILHO),
                                                            sticky='w', pady=(6, 0))

        # Execução: executável e pasta de saída.
        corpo = self.cartao('Execução')
        corpo.columnconfigure(1, weight=1)
        for r, (rotulo, var, escolher) in enumerate((
                ('Executável', self.exe, lambda: self.escolher_arquivo(
                    self.exe, (('Executável', '*.exe'), ('Todos', '*.*')))),
                ('Saída', self.saida, self.escolher_pasta))):
            tk.Label(corpo, text=rotulo, bg=CARTAO, fg=APAGADO, font=(FONTE, 10), width=10,
                     anchor='w').grid(row=r, column=0, sticky='w', pady=4)
            campo(corpo, var).grid(row=r, column=1, sticky='ew', padx=(0, 8), pady=4)
            botao(corpo, 'Procurar...', escolher).grid(row=r, column=2, pady=4)

        # Últimos relatórios da pasta de saída.
        self.lista = self.cartao('Últimos relatórios', botao_extra=('Abrir o último', self.abrir_ultimo))
        self.saida.trace_add('write', lambda *_: self.atualizar_recentes())
        self.atualizar_recentes()

        # Rodapé.
        rodape = tk.Frame(self, bg=FUNDO)
        rodape.pack(fill='x', padx=24, pady=(2, 22))
        ttk.Checkbutton(rodape, text='Abrir o relatório ao fechar o jogo', variable=self.abrir,
                        style='Fundo.TCheckbutton').pack(anchor='w')
        acoes = tk.Frame(rodape, bg=FUNDO)
        acoes.pack(fill='x', pady=(12, 0))
        tk.Label(acoes, textvariable=self.status, bg=FUNDO, fg=APAGADO, font=(FONTE, 10), anchor='w',
                 justify='left', wraplength=int(480 * self.escala)).pack(side='left', fill='x', expand=True)
        self.botao = botao(acoes, '\u25b6  Jogar com trace', self.iniciar, destaque=True)
        self.botao.pack(side='right')
        if self.rodando:
            self.botao.configure(state='disabled')
        self.botao_pasta = botao(acoes, 'Abrir pasta', self.abrir_pasta,
                                 state='normal' if self.pasta_trace else 'disabled')
        self.botao_pasta.pack(side='right', padx=10)

    def cartao(self, titulo, botao_extra=None):
        caixa = tk.Frame(self, bg=CARTAO, highlightthickness=1, highlightbackground=BORDA)
        caixa.pack(fill='x', padx=24, pady=(0, 14))
        cabeca = tk.Frame(caixa, bg=CARTAO)
        cabeca.pack(fill='x', padx=16, pady=(12, 6))
        tk.Label(cabeca, text=titulo.upper(), bg=CARTAO, fg=OURO, font=(FONTE, 9, 'bold')).pack(side='left')
        if botao_extra:
            self.botao_ultimo = botao(cabeca, botao_extra[0], botao_extra[1])
            self.botao_ultimo.pack(side='right')
        corpo = tk.Frame(caixa, bg=CARTAO)
        corpo.pack(fill='x', padx=16, pady=(0, 14))
        return corpo

    def carregar_trilho(self):
        chave = os.path.normcase(self.jogo.get())
        valores = self.trilhos.get(chave) or TRILHO_PADRAO.get(chave) or {}
        for k, var in self.trilho_vars.items():
            var.set(valores.get(k, '60' if k == 'segundos' else ''))
        self.trilho_inverter.set(bool(valores.get('inverter')))

    def atualizar_jogo(self):
        caminho = self.jogo.get()
        nome = os.path.splitext(os.path.basename(caminho))[0] or 'Nenhum jogo escolhido'
        self.nome_jogo.configure(text=nome)
        icone = carregar_imagem(os.path.join(os.path.dirname(caminho), 'icon.png'), int(72 * self.escala)) if caminho else None
        self.imagens['jogo'] = icone
        if icone:
            self.icone_jogo.configure(image=icone, text='', width=int(72 * self.escala), height=int(72 * self.escala))
        else:
            self.icone_jogo.configure(image='', text='?', width=3, height=1)

    def atualizar_recentes(self):
        for filho in self.lista.winfo_children():
            filho.destroy()
        self.recentes = relatorios_recentes(self.saida.get())
        self.botao_ultimo.configure(state='normal' if self.recentes else 'disabled')
        if not self.recentes:
            tk.Label(self.lista, text='Nenhum relatório nesta pasta ainda.', bg=CARTAO, fg=APAGADO,
                     font=(FONTE, 10)).pack(anchor='w')
            return
        for pasta, jogo, data in self.recentes:
            linha = tk.Frame(self.lista, bg=CARTAO)
            linha.pack(fill='x', pady=2)
            tk.Label(linha, text=data, bg=CARTAO, fg=OURO, font=(FONTE, 10, 'bold'), width=12,
                     anchor='w').pack(side='left')
            nome = os.path.splitext(os.path.basename(jogo))[0] if jogo else os.path.basename(pasta)
            tk.Label(linha, text=nome, bg=CARTAO, fg=TEXTO, font=(FONTE, 10), anchor='w').pack(side='left')
            botao(linha, 'Apagar', lambda p=pasta, n=nome, d=data: self.apagar(p, n, d),
                  perigo=True).pack(side='right')
            botao(linha, 'Pasta', lambda p=pasta: os.startfile(p)).pack(side='right', padx=6)
            botao(linha, 'Abrir', lambda p=pasta: self.abrir_relatorio(p)).pack(side='right', padx=6)

    def abrir_relatorio(self, pasta):
        html = os.path.join(pasta, 'relatorio.html')
        if os.path.isfile(html):
            os.startfile(html)

    def apagar(self, pasta, nome, data):
        if not messagebox.askyesno('Apagar relatório', 'Apagar o relatório de %s (%s)?\n\n%s\n\n'
                                   'A pasta é apagada de vez, sem passar pela lixeira.' % (nome, data, pasta),
                                   icon='warning', default='no', parent=self):
            return
        try:
            shutil.rmtree(pasta)
            self.status.set('Relatório apagado: %s' % os.path.basename(pasta))
        except OSError as erro:
            self.status.set('Não consegui apagar: %s' % erro)
        self.atualizar_recentes()

    def abrir_ultimo(self):
        if self.recentes:
            self.abrir_relatorio(self.recentes[0][0])

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
        trilho = {k: var.get().strip() for k, var in self.trilho_vars.items()}
        trilho['inverter'] = self.trilho_inverter.get()
        if 'sector' in modulos:
            if not (trilho['cena'] and trilho['curva'] and trilho['camera']):
                self.status.set('O módulo sector precisa de cena, curva e câmera.')
                return
            if 'frames' not in modulos:
                modulos.append('frames')  # o custo por trecho vem do custo de cada frame
        self.trilhos[os.path.normcase(jogo)] = trilho
        cfg = ler_config()
        cfg.update({'jogo': jogo, 'exe': exe, 'modulos': modulos, 'saida': self.saida.get(),
                    'abrir_relatorio': self.abrir.get(), 'tema': self.tema, 'trilhos': self.trilhos})
        salvar_config(cfg)

        self.pasta_trace = os.path.join(self.saida.get(), 'trace-' + time.strftime('%Y%m%d-%H%M%S'))
        os.makedirs(self.pasta_trace, exist_ok=True)
        with open(os.path.join(self.pasta_trace, META), 'w', encoding='utf-8') as f:
            json.dump({'jogo': jogo, 'exe': exe, 'modulos': modulos,
                       'trilho': trilho if 'sector' in modulos else None}, f, ensure_ascii=False)
        env = dict(os.environ, RANGE_TRACE=self.pasta_trace, RANGE_TRACE_MODULES=','.join(modulos))
        env.pop('RANGE_TRACE_RAIL', None)
        if 'sector' in modulos:
            env['RANGE_TRACE_RAIL'] = ';'.join((trilho['cena'], trilho['curva'], trilho['camera'],
                                                trilho['segundos'] or '60') + (('reverse',) if trilho['inverter'] else ()))
        self.rodando = True
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
        self.rodando = False
        self.status.set(msg)
        self.botao.configure(state='normal')
        self.atualizar_recentes()


if __name__ == '__main__':
    Launcher(sys.argv[1] if len(sys.argv) > 1 else None).mainloop()
