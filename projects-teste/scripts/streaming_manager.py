"""
Streaming Manager - AnastacioEngine.

Carrega/descarrega um pedaco de cena (um arquivo .blend/.range separado,
"chunk") por distancia da camera ativa, usando o mecanismo assincrono ja
existente no motor (LibLoad/LibFree/KX_LibLoadStatus) - nao roda nenhum
codigo C++ novo, so orquestra a API ja exposta em Python.

Uso: adicione este componente (aba Python Components) a um Empty que
representa a "ancora" de um chunk do mundo. Um componente cuida de um
unico chunk; para varios chunks, um componente por ancora.

Campos editaveis (args):
    chunk_path      (string) caminho do .blend/.range do chunk (ex.: "//chunks/casa_A.range")
    chunk_group     (string) nome do grupo/cena dentro do arquivo a carregar
    load_distance   (float) distancia (unidades da cena) abaixo da qual o chunk carrega. Padrao: 40.0
    unload_distance (float) distancia acima da qual o chunk descarrega. Deve ser > load_distance. Padrao: 60.0
    cooldown        (float) segundos minimos entre o chunk terminar de carregar e poder ser descarregado. Padrao: 5.0

Notas importantes (confirmadas no codigo do motor):
    - onFinish do KX_LibLoadStatus funciona; onProgress NAO funciona (stub vazio no C++),
      por isso este componente faz polling de status.finished/status.progress a cada update().
    - LibFree recusa (retorna False, sem crash) se o load assincrono ainda nao terminou -
      por isso sempre conferimos status.finished antes de chamar LibFree.
"""

from collections import OrderedDict
import Range
import time


class StreamingManager(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("chunk_path", "//chunks/chunk.range"),
        ("chunk_group", "Scene"),
        ("load_distance", 40.0),
        ("unload_distance", 60.0),
        ("cooldown", 5.0),
    ])

    STATE_UNLOADED = "unloaded"
    STATE_PENDING = "pending"
    STATE_LOADED = "loaded"

    def start(self, args):
        self.chunk_path = args["chunk_path"]
        self.chunk_group = args["chunk_group"]
        self.load_distance = args["load_distance"]
        self.unload_distance = args["unload_distance"]
        self.cooldown = args["cooldown"]

        if self.unload_distance <= self.load_distance:
            print("[StreamingManager] aviso: unload_distance deveria ser maior que load_distance "
                  "(evita oscilar carregando/descarregando na fronteira)")

        self.state = self.STATE_UNLOADED
        self.status = None
        self.loaded_time = None
        self.retry_cooldown = 3.0
        self.next_retry_time = 0.0

    def update(self):
        scene = Range.logic.getCurrentScene()
        camera = scene.active_camera
        if camera is None:
            return

        distance_sq = (self.object.worldPosition - camera.worldPosition).length_squared

        if self.state == self.STATE_UNLOADED:
            if distance_sq < self.load_distance * self.load_distance:
                if time.perf_counter() >= self.next_retry_time:
                    self._start_load()

        elif self.state == self.STATE_PENDING:
            if self.status is not None and self.status.finished:
                self.state = self.STATE_LOADED
                self.loaded_time = time.perf_counter()
                print("[StreamingManager] chunk carregado: {}".format(self.chunk_path))

        elif self.state == self.STATE_LOADED:
            far_enough = distance_sq > self.unload_distance * self.unload_distance
            cooled_down = (time.perf_counter() - self.loaded_time) > self.cooldown
            if far_enough and cooled_down:
                self._start_unload()

    def _start_load(self):
        try:
            status = Range.logic.LibLoad(
                self.chunk_path, self.chunk_group, asynchronous=1)
        except ValueError as exc:
            print("[StreamingManager] erro ao carregar '{}': {} - tentando de novo em {:.0f}s".format(
                self.chunk_path, exc, self.retry_cooldown))
            self.next_retry_time = time.perf_counter() + self.retry_cooldown
            return

        if not status:
            print("[StreamingManager] LibLoad recusou {} - tentando de novo em {:.0f}s".format(
                self.chunk_path, self.retry_cooldown))
            self.next_retry_time = time.perf_counter() + self.retry_cooldown
            return

        self.status = status
        self.state = self.STATE_PENDING
        print("[StreamingManager] carregando chunk: {}".format(self.chunk_path))

    def _start_unload(self):
        if self.status is not None and not self.status.finished:
            # Nao deveria acontecer (so chegamos aqui a partir de STATE_LOADED,
            # que exige status.finished == True), mas confere de novo por seguranca.
            return

        freed = Range.logic.LibFree(self.chunk_path)
        if not freed:
            print("[StreamingManager] LibFree recusou descarregar {} (ainda em uso?)".format(self.chunk_path))
            return

        self.state = self.STATE_UNLOADED
        self.status = None
        self.loaded_time = None
        print("[StreamingManager] chunk descarregado: {}".format(self.chunk_path))
