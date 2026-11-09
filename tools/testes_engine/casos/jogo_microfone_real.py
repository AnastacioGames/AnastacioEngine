"""Microfone com o backend real do sistema (OpenAL; no Linux via PulseAudio/PipeWire).

Confere que o backend aparece, lista dispositivos de captura e, se houver algum, grava 1 s
e salva um WAV válido. Não exige som no ambiente: sem dispositivo, só anota.
"""
import wave

INICIA = '''
import aud, bge
resultado = {'backends': list(aud.Microphone.backends()), 'devices': list(aud.Microphone.devices())}
if resultado['devices']:
    m = aud.Microphone(rate=22050, channels=1)
    m.start()
    m.record_start()
    bge.logic.teste_mic = m
    resultado['estado'] = m.state
'''

POLL = "import bge\nbge.logic.teste_mic.poll()\nresultado = bge.logic.teste_mic.level"


def testar(t):
    j = t.jogo(t.gerar(''))
    info = j.py(codigo=INICIA)
    assert 'Test' in info['backends'], 'backend Test sumiu: %s' % info['backends']
    reais = [b for b in info['backends'] if b != 'Test']
    assert reais, 'nenhum backend de captura real compilado: %s' % info['backends']
    if not info['devices']:
        t.nota('backends %s, nenhum dispositivo de captura' % info['backends'])
        return
    niveis = []
    for _ in range(6):
        j.esperar(frames=10)
        niveis.append(j.py(codigo=POLL))
    wav = t.pasta / 'gravado.wav'
    j.py(codigo="import bge\nm = bge.logic.teste_mic\nm.poll()\nm.record_stop()\nm.save_wav(%r)\nm.stop()" % str(wav))
    assert wav.exists(), 'save_wav não criou o arquivo'
    with wave.open(str(wav), 'rb') as w:
        quadros, taxa = w.getnframes(), w.getframerate()
    assert taxa == 22050 and quadros > 0, 'WAV inválido: %s quadros a %s Hz' % (quadros, taxa)
    t.nota('%s; dispositivo "%s"; nível máx %.3f; WAV %.2f s'
           % ('/'.join(reais), info['devices'][0], max(niveis), quadros / taxa))
