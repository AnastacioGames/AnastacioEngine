"""Som e microfone no jogo: toca um seno e captura com o backend Test (seno de 440 Hz, sem microfone físico)."""
import wave

INICIA = '''
import aud, bge
d = aud.Device() if hasattr(aud, 'Device') else aud.device()
fonte = aud.Sound.sine(440) if hasattr(aud, 'Sound') else aud.Factory.sine(440)
bge.logic.teste_handle = d.play(fonte.limit(0, 5))
m = aud.Microphone(backend='Test', rate=22050, channels=1)
m.start()
m.record_start()
bge.logic.teste_mic = m
resultado = [bool(bge.logic.teste_handle.status), m.state]
'''

POLL = "import bge\nbge.logic.teste_mic.poll()\nresultado = bge.logic.teste_mic.level"


def testar(t):
    j = t.jogo(t.gerar(''))
    tocando, estado = j.py(codigo=INICIA)
    assert tocando, 'o som não começou a tocar'
    niveis = []
    for _ in range(8):
        j.esperar(frames=10)
        niveis.append(j.py(codigo=POLL))
    assert max(niveis) > 0, 'nível do microfone Test ficou zerado: %s (estado %s)' % (niveis, estado)

    wav = t.pasta / 'gravado.wav'
    j.py(codigo="import bge\nm = bge.logic.teste_mic\nm.poll()\nm.record_stop()\nm.save_wav(%r)\nm.stop()\n"
                "bge.logic.teste_handle.stop()" % str(wav))
    assert wav.exists(), 'save_wav não criou o arquivo'
    with wave.open(str(wav), 'rb') as w:
        quadros, taxa = w.getnframes(), w.getframerate()
    assert taxa == 22050 and quadros > 0, 'WAV inválido: %s quadros a %s Hz' % (quadros, taxa)
    t.nota('estado %s, nível máx %.2f, WAV %.2f s' % (estado, max(niveis), quadros / taxa))
