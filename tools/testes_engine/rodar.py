#!/usr/bin/env python3
"""Roda os testes guardados em tools/testes_engine/casos e diz o que quebrou.

  python tools/testes_engine/rodar.py              (todos)
  python tools/testes_engine/rodar.py jogo_         (só os que têm "jogo_" no nome)

Cada caso é um casos/<nome>.py com `def testar(t)`: usa t.gerar() para criar a cena,
t.jogo() / t.editor() para dirigir e `assert` para conferir. Tudo invisível.
Resultado também em artifacts/testes/rodada.json.
"""
import importlib.util, json, subprocess, sys, tempfile, time, traceback
from pathlib import Path

import controle

AQUI = Path(__file__).resolve().parent
CASOS = AQUI / 'casos'
SAIDA = controle.RAIZ / 'artifacts/testes'


class Teste:
    """Ferramentas que o caso recebe; fecha o que abriu ao terminar."""
    def __init__(self, nome):
        self.nome = nome
        self.pasta = Path(tempfile.mkdtemp(prefix=nome + '_', dir=controle.PASTA))
        self.abertos = []
        self.notas = []

    def gerar(self, codigo, nome='cena', limite=180):
        """Roda `codigo` (bpy) no editor em background sobre a cena padrão e salva <pasta>/<nome>.range.
        O código vê `saida` (caminho do .range) e pode salvar por conta própria; senão é salvo no fim."""
        destino = self.pasta / (nome + '.range')
        script = self.pasta / (nome + '_gerar.py')
        script.write_text('import bpy\nsaida = %r\n%s\nimport os\nif not os.path.exists(saida):\n'
                          '    bpy.ops.wm.save_as_mainfile(filepath=saida)\n' % (str(destino), codigo), encoding='utf-8')
        r = subprocess.run([str(controle.EDITOR), '-b', '--factory-startup', '--python-exit-code', '1',
                            '--python', str(script)], capture_output=True, text=True, errors='replace', timeout=limite)
        if r.returncode or not destino.exists():
            raise RuntimeError('gerar %s falhou:\n%s' % (nome, (r.stdout + r.stderr)[-2000:]))
        return destino

    def jogo(self, arquivo, **opcoes):
        j = controle.abrir_jogo(arquivo, **opcoes)
        self.abertos.append(_garantir(j.fechar, controle.ultimo_pid))
        return j

    def editor(self, cena=None):
        controle.abrir(str(cena) if cena else None)
        e = controle.Editor()
        self.abertos.append(_garantir(lambda: _fechar_editor(e), controle.ultimo_pid))
        return e

    def nota(self, texto):
        self.notas.append(str(texto))

    def fechar_tudo(self):
        for fechar in reversed(self.abertos):
            try:
                fechar()
            except Exception:
                pass
        self.abertos.clear()


def _garantir(fechar, pid):
    """Pede para fechar e, se o processo não sair em 15 s, mata: nada aberto passa para o próximo caso."""
    def executar():
        try:
            fechar()
        finally:
            controle.encerrar(pid, espera=15)
    return executar


def _fechar_editor(e):
    e.canal.write(json.dumps({'cmd': 'fechar', 'token': e.sessao['token']}) + '\n')
    e.canal.flush()


def py(editor, codigo):
    """Atalho: roda código no editor e devolve `resultado`, levantando erro se falhar."""
    r = editor.pedir('py', codigo=codigo)
    if not r['ok']:
        raise RuntimeError(r.get('traceback') or r['erro'])
    return r['resultado']


def carregar(arquivo):
    spec = importlib.util.spec_from_file_location('caso_' + arquivo.stem, arquivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def main():
    filtro = sys.argv[1] if len(sys.argv) > 1 else ''
    # a exportação vai por último: depois dela os jogos seguintes abriram até 20x mais devagar
    arquivos = sorted((a for a in CASOS.glob('*.py') if not a.name.startswith('_') and filtro in a.stem),
                      key=lambda a: (a.stem == 'jogo_exportado', a.stem))
    resultados = []
    for arquivo in arquivos:
        t = Teste(arquivo.stem)
        inicio = time.time()
        try:
            carregar(arquivo).testar(t)
            estado, detalhe = 'OK', ''
        except AssertionError as erro:
            estado, detalhe = 'FALHOU', str(erro) or traceback.format_exc(limit=-1)
        except Exception:
            estado, detalhe = 'ERRO', traceback.format_exc(limit=-3)
        finally:
            t.fechar_tudo()
        tempo = time.time() - inicio
        resultados.append({'caso': arquivo.stem, 'estado': estado, 'segundos': round(tempo, 1),
                           'detalhe': detalhe, 'notas': t.notas, 'pasta': str(t.pasta)})
        print('%-7s %-32s %5.1f s  %s' % (estado, arquivo.stem, tempo, '; '.join(t.notas)), flush=True)
        if detalhe:
            print('        ' + detalhe.strip().replace('\n', '\n        '), flush=True)
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / 'rodada.json').write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding='utf-8')
    ruins = [r for r in resultados if r['estado'] != 'OK']
    print('\n%d de %d OK' % (len(resultados) - len(ruins), len(resultados)))
    sys.exit(1 if ruins else 0)


if __name__ == '__main__':
    main()
