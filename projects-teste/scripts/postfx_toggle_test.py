"""
PostFXToggleTest - AnastacioEngine.

Componente pra testar a correcao da criacao "sob demanda" dos shaders
built-in (Tonemap, SSAO/Ambient Occlusion, Bloom, Light Scattering, SSR,
FXAA) via Python, mesmo quando a cena carrega com a checkbox correspondente
desmarcada em Render > Post Processing Shaders.

Cada shader tem uma tecla propria pra ligar/desligar. Se o shader realmente
ligar (visualmente, na tela) mesmo comecando desmarcado na UI, a correcao
funcionou - antes disso as chamadas eram silenciosamente ignoradas nesse caso.

Teclas (fixas, uma por shader):
    1 -> Tonemap        (changeTonemapValues)
    2 -> SSAO            (changeSSAOValues)
    3 -> Bloom            (changeBloomValues)
    4 -> Light Scattering (changeLightScatterValues)
    5 -> SSR              (changeSSRValues)
    6 -> FXAA              (changeFxaaValues)

Uso: adicione este componente (aba Python Components) a qualquer objeto da
cena, uma vez so. Rode a cena com todas as checkboxes de Post Processing
Shaders desmarcadas e va apertando 1-6 pra confirmar que cada shader liga
(e desliga de novo, apertando a mesma tecla) sem precisar ter passado pela
UI antes.
"""

from collections import OrderedDict
import Range


class PostFXToggleTest(Range.types.KX_PythonComponent):
    args = OrderedDict([])

    # (tecla, nome, metodo, args extras alem de "enabled")
    ENTRIES = (
        ("ONEKEY", "Tonemap", "changeTonemapValues", (2.2, 1.0)),
        ("TWOKEY", "SSAO", "changeSSAOValues", (16, 4.0, 1.0, 1.0)),
        ("THREEKEY", "Bloom", "changeBloomValues", (2.0, 0.75)),
        ("FOURKEY", "LightScatter", "changeLightScatterValues", (32, 0.15, 0.75, 0.2)),
        ("FIVEKEY", "SSR", "changeSSRValues", (16, 3.0, 100.0)),
        ("SIXKEY", "FXAA", "changeFxaaValues", ()),
    )

    def start(self, args):
        self.states = {}
        self.keys = {}

        for key_name, label, method_name, extra_args in self.ENTRIES:
            key_code = getattr(Range.events, key_name, None)
            if key_code is None:
                print("[PostFXToggleTest] tecla '{}' invalida, pulando '{}'.".format(key_name, label))
                continue
            self.keys[key_code] = (label, method_name, extra_args)
            self.states[label] = False

        print("[PostFXToggleTest] pronto. Teclas: 1=Tonemap 2=SSAO 3=Bloom 4=LightScatter 5=SSR 6=FXAA")

    def update(self):
        keyboard = Range.logic.keyboard
        filter_manager = Range.logic.getCurrentScene().filterManager

        for key_code, (label, method_name, extra_args) in self.keys.items():
            if keyboard.events[key_code] != Range.logic.KX_INPUT_JUST_ACTIVATED:
                continue

            new_state = not self.states[label]

            method = getattr(filter_manager, method_name)
            try:
                method(new_state, *extra_args)
            except (ValueError, TypeError) as exc:
                print("[PostFXToggleTest] erro ao chamar {}({}, {}): {}".format(
                    method_name, new_state, extra_args, exc))
                continue

            self.states[label] = new_state
            print("[PostFXToggleTest] {} {} (via {})".format(
                label, "ligado" if new_state else "desligado", method_name))
