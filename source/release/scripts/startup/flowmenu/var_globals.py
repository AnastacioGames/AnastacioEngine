# ==============================================================================
# VAR GLOBALS - RANGE ENGINE ADDON
# ==============================================================================
import logging

# --- SISTEMA DE LOGS PROFISSIONAL ---
log = logging.getLogger("RangeLabel")
if not log.handlers:
    handler = logging.StreamHandler()
    # Formato: [RangeLabel] INFO: mensagem
    formatter = logging.Formatter('[%(name)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(logging.INFO) # Mude para logging.DEBUG se quiser ver detalhes minuciosos


# Regex Robusta (A "Da hora" que criamos):
# Garante que captura classes herdando de KX_PythonComponent,
# ignorando espaços extras ou formatação bagunçada.
regex_multiline = r"class\s+([a-zA-Z_]\w*)\s*\([^)]*\bKX_PythonComponent\b[^)]*\)\s*:"

# Template Definitivo (Melhor dos dois mundos):
# - Usa imports nativos do BGE (mais compatível).
# - Inclui todo o ciclo de vida (Awake, Start, Update, Dispose).
# - Já traz as referências úteis de Scene e Input.
template_component = """
from Range import *
from collections import OrderedDict

class %s(Range.types.KX_PythonComponent):
    # Argumentos expostos na interface da Range Engine
    args = OrderedDict({
        "Propriedade": 0.0,
    })

    def awake(self, args):
        # [AWAKE] Início Imediato
        # Executado assim que o objeto é criado/spawnado, antes mesmo do primeiro frame.
        # Útil para configurações internas que não dependem de outros objetos da cena.
        pass

    def start(self, args):
        # [START] Primeiro Frame
        # Executado no primeiro frame lógico do jogo.

        # --- Atalhos Úteis (Recuperados da versão antiga) ---
        self.scene = logic.getCurrentScene()  # Referência da Cena atual
        self.keyboard = logic.keyboard.inputs # Atalho para Teclado
        self.mouse = logic.mouse.inputs       # Atalho para Mouse

        # Use self.object para acessar o dono deste componente.
        pass

    def update(self):
        # [UPDATE] Loop Lógico
        # Executado repetidamente a cada frame (Logic Tick).
        # É aqui que a "mágica" acontece: movimento, input, ataques, etc.
        pass

    def dispose(self):
        # [DISPOSE] Limpeza
        # Executado quando o componente ou o objeto é destruído (endObject) ou a cena muda.
        # Use para salvar dados finais ou limpar listas globais.
        pass
"""