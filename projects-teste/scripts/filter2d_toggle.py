"""
Filter2DToggle - AnastacioEngine.

Liga/desliga um filtro de pos-processamento 2D numa tecla, usando a API ja
exposta scene.filterManager.addFilter()/removeFilter()/getFilter() - nao roda
nenhum codigo C++ novo, so orquestra a API em Python (mesmo espirito do
streaming_manager.py: componente autocontido, sem precisar de outros logic
bricks na cena).

Uso: adicione este componente (aba Python Components) a qualquer objeto da
cena - um por filtro que voce quiser poder ligar/desligar. Aperte a tecla
configurada em toggle_key durante o jogo pra alternar.

Campos editaveis (args):
    filter_type   (string) um de: GRAYSCALE, INVERT, SEPIA, BLUR, SHARPEN,
                  DILATION, EROSION, LAPLACIAN, SOBEL, PREWITT.
                  Todos os 10 ja foram migrados pra sintaxe core-profile-safe
                  (ver docs/changelog.md) - continuam funcionando
                  identicamente sob o profile compatibility atual, nao ha
                  diferenca de uso aqui.
                  Padrao: "GRAYSCALE"
    toggle_key    (string) nome da tecla em Range.events (ex.: "FKEY", "GKEY",
                  "HKEY"). Padrao: "FKEY"
    pass_index    (int) slot do filtro no filterManager (1, 2, 3...). Use um
                  numero diferente por componente se mais de um
                  Filter2DToggle estiver ativo na cena ao mesmo tempo, senao
                  um vai substituir o filtro do outro no mesmo slot. NAO use
                  0: internamente o filterManager soma reservedPassIndex (14)
                  ao indice recebido do Python, entao pass_index=0 cai no
                  slot interno 14 - o mesmo slot reservado do filtro Tonemap
                  (FILTERPASS_TONEMAP=14 em RAS_2DFilterManager.h), que a
                  cena pode ja estar usando via as opcoes de World/Scene.
                  Padrao: 1
    start_enabled (bool) se o filtro ja comeca ligado. Padrao: False

Nota: scene.filterManager.addFilter() so aceita os tipos de filtro "simples"
(um shader, sem parametros extras) listados em FILTER_TYPES abaixo - Bloom,
Tonemap, SSAO, FXAA, Outline e Motion Blur usam mecanismos proprios
(changeBloomValues/changeTonemapValues/etc., ou entram automaticamente pelas
opcoes de cena) e nao passam por addFilter, por isso nao aparecem aqui.
"""

from collections import OrderedDict
import Range


class Filter2DToggle(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("filter_type", "GRAYSCALE"),
        ("toggle_key", "FKEY"),
        ("pass_index", 1),
        ("start_enabled", False),
    ])

    # Unicos tipos aceitos por scene.filterManager.addFilter() (ver checagem
    # "type < FILTER_BLUR || type > FILTER_CUSTOMFILTER" em KX_2DFilterManager.cpp).
    FILTER_TYPES = (
        "BLUR", "SHARPEN", "DILATION", "EROSION", "LAPLACIAN", "SOBEL",
        "PREWITT", "GRAYSCALE", "SEPIA", "INVERT",
    )

    def start(self, args):
        filter_type = args["filter_type"]
        if filter_type not in self.FILTER_TYPES:
            print("[Filter2DToggle] filter_type '{}' desconhecido, usando GRAYSCALE. Opcoes: {}".format(
                filter_type, ", ".join(self.FILTER_TYPES)))
            filter_type = "GRAYSCALE"
        self.filter_type_name = filter_type
        self.filter_type_value = getattr(Range.logic, "RAS_2DFILTER_" + filter_type)

        key_name = args["toggle_key"]
        self.toggle_key = getattr(Range.events, key_name, None)
        if self.toggle_key is None:
            print("[Filter2DToggle] toggle_key '{}' invalida (sem Range.events.{}) - tecla desativada.".format(
                key_name, key_name))

        self.pass_index = int(args["pass_index"])
        self.enabled = False

        if args["start_enabled"]:
            self._set_enabled(True)

    def update(self):
        if self.toggle_key is None:
            return

        keyboard = Range.logic.keyboard
        if keyboard.events[self.toggle_key] == Range.logic.KX_INPUT_JUST_ACTIVATED:
            self._set_enabled(not self.enabled)

    def _set_enabled(self, enabled):
        filter_manager = Range.logic.getCurrentScene().filterManager

        try:
            # Sempre limpa o slot primeiro: cobre tanto religar depois de
            # desligar quanto o caso de outro componente ja ter deixado um
            # filtro diferente nesse mesmo pass_index.
            if filter_manager.getFilter(self.pass_index) is not None:
                filter_manager.removeFilter(self.pass_index)

            if enabled:
                filter_manager.addFilter(self.pass_index, self.filter_type_value)
        except ValueError as exc:
            print("[Filter2DToggle] erro ao {} filtro '{}' (pass_index={}): {}".format(
                "ligar" if enabled else "desligar", self.filter_type_name, self.pass_index, exc))
            return

        self.enabled = enabled
        print("[Filter2DToggle] filtro '{}' {} (pass_index={})".format(
            self.filter_type_name, "ligado" if enabled else "desligado", self.pass_index))
