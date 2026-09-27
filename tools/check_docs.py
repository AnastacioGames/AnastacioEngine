#!/usr/bin/env python3
"""Confere se a documentacao ainda bate com o codigo.

Uso (na raiz do repo):
    python tools/check_docs.py          # so relata
    python tools/check_docs.py --fix    # corrige linhas dos mapas de codigo e tamanhos de arquivo

O que confere:
  1. Links locais em Markdown ([texto](caminho)) apontam para arquivos que existem.
  2. Referencias `arquivo.cpp:123` apontam para um arquivo que existe e tem pelo menos essa linha.
  3. Mapas de codigo (docs/code-map-*.md): cada `Metodo` NNN ainda comeca perto da linha NNN,
     e os tamanhos "(N linhas)" batem com o arquivo.

Saida 1 quando ha erro (link quebrado, arquivo sumido, metodo com mais de LIMITE linhas de desvio);
desvios menores sao so aviso. Rode antes de cada release. Nao olha o historico do changelog, que
descreve o passado de proposito.
"""
import argparse
import datetime
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEENGINE = 'source/source/gameengine/'
LIMITE = 20  # desvio em linhas a partir do qual um metodo do mapa conta como erro

DOCS = ['README.md', 'AGENTS.md', 'CLAUDE.md', 'CONTRIBUTING.md', 'relatorio-melhorias-anastacioengine.md']
DOCS_IGNORADOS = {'docs/changelog.md'}  # historico: links e linhas antigos sao esperados
# Documentos cujas referencias arquivo:linha apontam para o SDK do Emscripten ou para JS gerado no build.
REFS_EXTERNAS = {'docs/web-gl-emulation-analysis.md', 'docs/web-audio-analysis.md'}
CODE_MAPS = {
    'docs/code-map-gameengine.md': None,
    'docs/code-map-kx-gameobject.md': 'Ketsji/KX_GameObject.cpp',
}
EXTS_CODIGO = 'cpp|cc|c|h|hpp|py|glsl|cjs|js|cmake'

RE_LINK = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')
RE_ARQ_LINHA = re.compile(r'(?<![\w/.-])([\w./-]+\.(?:%s)):(\d+)\b' % EXTS_CODIGO)
RE_TAMANHO = re.compile(r'`([\w./-]+\.\w+)`(\]\(([^)]+)\))? \(([\d.]+) linhas')
# Separador sem virgula: em "`SetTransform`, posicao/escala 936-1185" o numero e da faixa, nao do metodo.
RE_ANCORA = re.compile(r'`(\w+)`([^`|0-9,;]*?)(\d{2,5})(–\d{2,5})?')
RE_CONFERIDO = re.compile(r'\*\*Linhas conferidas em [\d-]+ \(`HEAD` `\w+`\)\.\*\*')


def ler(caminho):
    with open(os.path.join(ROOT, caminho), encoding='utf-8', errors='replace') as f:
        return f.read()


def contar_linhas(texto):
    return texto.count('\n') + (0 if texto.endswith('\n') or not texto else 1)


def arquivos_git():
    saida = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', check=True).stdout
    return saida.splitlines()


class Relatorio:
    def __init__(self):
        self.erros = []
        self.avisos = []

    def erro(self, doc, n, msg):
        self.erros.append(f'{doc}:{n}: {msg}')

    def aviso(self, doc, n, msg):
        self.avisos.append(f'{doc}:{n}: {msg}')


def docs_para_conferir(todos):
    lista = [d for d in DOCS if os.path.exists(os.path.join(ROOT, d))]
    for f in todos:
        if f.startswith('docs/') and f.endswith('.md') and f.count('/') <= 2 \
                and not f.startswith('docs/changelog/') and f not in DOCS_IGNORADOS:
            lista.append(f)
    return lista


def conferir_links(doc, linhas, rel):
    base = os.path.dirname(doc)
    for n, linha in enumerate(linhas, 1):
        for alvo in RE_LINK.findall(linha):
            if re.match(r'^[a-z]+:', alvo) or alvo.startswith('#'):
                continue
            caminho = alvo.split('#')[0]
            if not caminho:
                continue
            completo = os.path.normpath(os.path.join(ROOT, base, caminho.replace('%20', ' ')))
            if not os.path.exists(completo):
                rel.erro(doc, n, f'link quebrado: {alvo}')


def resolver(nome, por_nome, existentes):
    """Acha o arquivo de uma referencia `nome` (caminho parcial ou so o nome)."""
    for prefixo in ('', GAMEENGINE, 'source/source/', 'source/'):
        if prefixo + nome in existentes:
            return [prefixo + nome]
    candidatos = por_nome.get(os.path.basename(nome), [])
    return [c for c in candidatos if c.endswith('/' + nome) or '/' not in nome]


def conferir_arq_linha(doc, linhas, rel, por_nome, existentes, cache):
    for n, linha in enumerate(linhas, 1):
        for nome, num in RE_ARQ_LINHA.findall(linha):
            if nome.startswith('/') or 'emsdk' in nome:
                continue  # arquivo de fora do repo (ex.: emsdk)
            achados = resolver(nome, por_nome, existentes)
            if not achados:
                # Pode ser arquivo de terceiros ou gerado no build; so avisa.
                rel.aviso(doc, n, f'arquivo fora do repo ou removido: {nome}:{num}')
                continue
            maior = max(cache.setdefault(a, contar_linhas(ler(a))) for a in achados)
            if int(num) > maior:
                rel.erro(doc, n, f'{nome}:{num} passa do fim do arquivo ({maior} linhas)')


def inicios_de_metodo(fonte, nome):
    padrao = re.compile(r'::' + nome + r'\s*\(')
    return [i + 1 for i, l in enumerate(fonte) if not l.startswith((' ', '\t')) and padrao.search(l)]


def conferir_mapa(doc, arquivo_padrao, rel, fix, por_nome, existentes):
    linhas = ler(doc).split('\n')
    fonte = ler(GAMEENGINE + arquivo_padrao).split('\n') if arquivo_padrao else None
    ajustes = 0

    def formatar(num):
        return f'{num:,}'.replace(',', '.')

    for i, linha in enumerate(linhas):
        n = i + 1
        cab = re.match(r'## `([^`]+)` \(', linha)
        if cab:
            fonte = ler(GAMEENGINE + cab.group(1)).split('\n')

        def tamanho(m):
            nonlocal ajustes
            nome, link = m.group(1), m.group(3)
            caminho = os.path.normpath(os.path.join(os.path.dirname(doc), link)).replace('\\', '/') \
                if link else None
            achados = [caminho] if caminho in existentes else resolver(nome, por_nome, existentes)
            if len(achados) != 1:
                return m.group(0)
            real = formatar(contar_linhas(ler(achados[0])))
            if real == m.group(4):
                return m.group(0)
            rel.aviso(doc, n, f'{nome}: doc diz {m.group(4)} linhas, arquivo tem {real}')
            ajustes += 1
            return m.group(0).replace(m.group(4) + ' linhas', real + ' linhas')

        linha = RE_TAMANHO.sub(tamanho, linha)

        if fonte is not None and linha.startswith('|'):
            def ancora(m):
                nonlocal ajustes
                nome, sep, num, faixa = m.group(1), m.group(2), int(m.group(3)), m.group(4)
                inicios = inicios_de_metodo(fonte, nome)
                if not inicios:
                    return m.group(0)
                real = min(inicios, key=lambda x: abs(x - num))
                desvio = real - num
                if desvio == 0:
                    return m.group(0)
                if abs(desvio) > LIMITE:
                    rel.erro(doc, n, f'`{nome}` {num}: metodo agora na linha {real} ({desvio:+d})')
                else:
                    rel.aviso(doc, n, f'`{nome}` {num}: metodo agora na linha {real} ({desvio:+d})')
                ajustes += 1
                nova_faixa = '–' + str(int(faixa[1:]) + desvio) if faixa else ''
                return f'`{nome}`{sep}{real}{nova_faixa}'

            linha = RE_ANCORA.sub(ancora, linha)
        linhas[i] = linha

    if fix and ajustes:
        head = subprocess.run(['git', 'rev-parse', '--short=8', 'HEAD'], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
        hoje = datetime.date.today().isoformat()
        texto = RE_CONFERIDO.sub(f'**Linhas conferidas em {hoje} (`HEAD` `{head}`).**', '\n'.join(linhas))
        with open(os.path.join(ROOT, doc), 'w', encoding='utf-8', newline='\n') as f:
            f.write(texto)
    return ajustes


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--fix', action='store_true',
                        help='corrige linhas e tamanhos nos mapas de codigo (links quebrados continuam manuais)')
    args = parser.parse_args()

    todos = arquivos_git()
    existentes = set(todos)
    por_nome = {}
    for f in todos:
        por_nome.setdefault(os.path.basename(f), []).append(f)

    rel = Relatorio()
    cache = {}
    docs = docs_para_conferir(todos)
    for doc in docs:
        linhas = ler(doc).split('\n')
        conferir_links(doc, linhas, rel)
        if doc not in REFS_EXTERNAS:
            conferir_arq_linha(doc, linhas, rel, por_nome, existentes, cache)

    ajustes = 0
    for doc, padrao in CODE_MAPS.items():
        ajustes += conferir_mapa(doc, padrao, rel, args.fix, por_nome, existentes)

    if args.fix and ajustes:
        # O que foi corrigido deixa de ser pendencia; confere de novo para relatar so o que sobrou.
        rel_mapas = Relatorio()
        for doc, padrao in CODE_MAPS.items():
            conferir_mapa(doc, padrao, rel_mapas, False, por_nome, existentes)
        rel.erros = [e for e in rel.erros if not e.startswith('docs/code-map-')] + rel_mapas.erros
        rel.avisos = [a for a in rel.avisos if not a.startswith('docs/code-map-')] + rel_mapas.avisos

    for a in rel.avisos:
        print('aviso:', a)
    for e in rel.erros:
        print('ERRO: ', e)
    print(f'\n{len(docs)} documentos e {len(CODE_MAPS)} mapas de codigo conferidos: '
          f'{len(rel.erros)} erro(s), {len(rel.avisos)} aviso(s).')
    if args.fix:
        print(f'--fix: {ajustes} ajuste(s) gravado(s) nos mapas de codigo.')
    elif ajustes:
        print('Linhas e tamanhos dos mapas podem ser corrigidos com: python tools/check_docs.py --fix')
    return 1 if rel.erros else 0


if __name__ == '__main__':
    sys.exit(main())
