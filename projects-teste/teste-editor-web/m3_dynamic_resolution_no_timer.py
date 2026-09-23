"""M3 Web: deixa a resolução dinâmica ativa por quadros suficientes para a sonda.

No Web o timer GPU não é suportado. O sinal obrigatório é o aviso único do
runtime; sem ele, a cena falha. A escala interna não tem getter Python, então
o verificador confirma o aviso e a ausência de abort/erro GL; a confirmação
numérica de escala depende do trace de render scale no runtime.
"""
from bge import logic


def rodar(cont):
    own = cont.owner
    frame = own.get("m3_frames", 0) + 1
    own["m3_frames"] = frame
    if frame == 1:
        print("[m3-dynres] iniciado: timer GPU deve estar indisponivel no Web")
    if frame == 180:
        print("[m3-dynres] RESULTADO OK; espere o aviso de timer indisponivel e nenhuma subida de escala")
        logic.endGame()
