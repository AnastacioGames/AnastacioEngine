# ragdoll_system/ragdoll.py
import Range
from collections import OrderedDict

"""Esse arquivo cuida do efeito de ragdoll"""


class Ragdoll(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("Active", False),
        ("Debug Lines", False)
    ])

    def get_root(self):
        root = self.object
        while root.parent:
            root = root.parent
        return root

    def start(self, args):
        if not hasattr(self.object, "constraints"):
            print(f"[Ragdoll System Debug] ERRO: O componente Ragdoll foi anexado ao objeto '{self.object.name}', que nao possui constraints. Certifique-se de anexar o componente Ragdoll diretamente a Armature (esqueleto) do personagem.")
            self.is_valid = False
            return
        
        self.is_valid = True
        try:
            # --- OTIMIZAÇÃO NO MENU ---
            # Impede que o personagem calcule matrizes e force as constraints dos ossos na vitrine.
            scene = Range.logic.getCurrentScene()
            if "menu" in scene.name.lower():
                self.__status = False
                for obj in self.object.constraints:
                    obj.enforce = 0.0
                    if obj.target and obj.target.parent:
                        obj.target.parent.suspendPhysics()
                return

            self.__timer = 0.0
            self.active = args.get("Active", False)
            self.debug_lines = args.get("Debug Lines", False)
            self.__status = self.active

            # Force initial behavior
            for obj in self.object.constraints:
                obj.enforce = float(self.active)

            self.__startList = []

            # Cache de matriz invertida
            tmpTransform = self.object.worldTransform.inverted()

            for obj in self.object.constraints:
                out = [None, None]
                if obj.target:
                    # Encontra o verdadeiro objeto físico (pode ser o target ou o parent dele se for uma parte do ragdoll)
                    target = obj.target
                    if obj.target.parent and obj.target.parent.name.startswith("RagdollPart-"):
                        target = obj.target.parent
                    transf = tmpTransform * target.worldTransform
                    out = [target, transf]
                self.__startList.append(out)
             # --- OTIMIZAÇÃO: Cache inicia vazio ---
            self.bone_cache = None

            # Calculate root offset and cache physical collider
            root = self.get_root()
            self.__collider = next((c for c in root.childrenRecursive if "Collider" in c), None)

            # Suspend physics in start
            for (obj, _) in self.__startList:
                if obj is not None:
                    obj.suspendPhysics()

            # debug drawRestLine
            self.path_points = []
            self.ref_camera_ragdoll = None
        except Exception as e:
            print(f"\n[Ragdoll System Debug] ERRO CRITICO no start(): {e}\n")

    def _ensure_bone_cache(self):
        """
        Tenta construir o cache. Retorna a lista de cache se conseguir,
        ou None se os canais ainda não estiverem prontos.
        """
        # pyrefly: ignore [missing-attribute]
        if not self.object.channels:
            return None

        new_cache = []
        
        for channel in self.object.channels:
            bone = channel.bone
            
            # Procure o objeto físico correspondente a este osso a partir das constraints da armature
            matched_obj = None
            for constr in self.object.constraints:
                if constr.target:
                    target_candidate = constr.target
                    if constr.target.parent and constr.target.parent.name.startswith("RagdollPart-"):
                        target_candidate = constr.target.parent
                    
                    if ("-" + bone.name + "-") in target_candidate.name:
                        matched_obj = target_candidate
                        break

            if matched_obj:
                # Pre-calcula pivot se existir
                pivot = None
                if matched_obj.children:
                    pivot = matched_obj.children[0]

                new_cache.append({
                    "obj": matched_obj,
                    "channel": channel,
                    "pivot": pivot
                })

        # Só salva se encontrou algo
        if new_cache:
            self.bone_cache = new_cache
            return self.bone_cache
        return None

    def resetRagdollTransform(self):
        """
        Reseta as transformações.
        Usa cache inteligente: se não existir, cria na hora.
        """
        # Se o cache ainda não existe, tenta criar
        if self.bone_cache is None:
            self._ensure_bone_cache()

        # Se mesmo tentando criar, ele continuar None (erro na armature), sai
        if self.bone_cache is None:
            return

        # Daqui pra baixo é o Loop Rápido (sem strings)
        transform = self.object.worldTransform

        for item in self.bone_cache:
            obj = item["obj"]
            channel = item["channel"]
            pivot = item["pivot"]

            obj.linearVelocity = [0, 0, 0]
            obj.angularVelocity = [0, 0, 0]

            if pivot:
                pivotSpace = pivot.worldTransform.inverted() * obj.worldTransform
                obj.worldTransform = transform * (channel.pose_matrix * pivotSpace)

        # Só redefine a orientação se não houver um parentesco ativo (evita teletransportar o piloto no carro)
        if not self.object.parent:
            self.object.worldTransform = self.get_root().worldTransform

    def applyLinearVelocity(self):
        if not self.object.parent:
            return

        # Usa o colisor salvo no cache ou tenta achar na hora caso a referencia tenha se perdido (Fallback)
        if self.__collider is None or getattr(self.__collider, "invalid", True):
            self.__collider = next((c for c in self.get_root().childrenRecursive if "Collider" in c), None)
            
        if self.__collider:
            linearVelocity = self.__collider.getLinearVelocity()
        else:
            linearVelocity = self.get_root().getLinearVelocity()
            
        # (40%) para suavizar o arremesso
        boosted_velocity = linearVelocity * 0.4

        for (obj, _) in self.__startList:
            if obj:
                obj.setLinearVelocity(boosted_velocity)

    def drawRestLine(self):
        if not self.debug_lines or self.ref_camera_ragdoll is None:
            return

        self.path_points.append(self.ref_camera_ragdoll.worldPosition.copy())

        if len(self.path_points) > 200:
            self.path_points.pop(0)

        for i in range(len(self.path_points) - 1):
            Range.render.drawLine(self.path_points[i], self.path_points[i + 1], (0, 0, 0))

    def ragdoll_on_off(self):
        current_state = self.object.get("active_ragdoll", False)

        if self.__status != current_state:
            self.__status = current_state

            if current_state:
                # LIGANDO RAGDOLL
                self.resetRagdollTransform()
                
                for obj in self.object.constraints:
                    obj.enforce = 1
                
                restored_count = 0
                for (obj, _) in self.__startList:
                    if obj:
                        obj.restorePhysics()
                        restored_count += 1
                self.applyLinearVelocity()
                
                # Debug extra: Verifica se ha animacoes rodando que podem estar segurando a malha
                for layer in range(8):
                    if self.object.isPlayingAction(layer):
                        self.object.stopAction(layer)
            else:
                # DESLIGANDO RAGDOLL
                for obj in self.object.constraints:
                    obj.enforce = 0
                for (obj, _) in self.__startList:
                    if obj:
                        obj.suspendPhysics()
                self.resetRagdollTransform()

        # Se estiver desligado, continua alinhando a física com a animação
        # (Isso garante que o colisor não fique para trás)
        elif not current_state:
            # --- OTIMIZAÇÃO: MODO ESPERA ---
            # Evita recalcular matrizes 60 vezes por segundo enquanto dirige.
            # Atualizar a cada 10 frames já mantém a Bounding Box segura, e poupa muita CPU!
            self._idle_timer = getattr(self, "_idle_timer", 0) + 1
            if self._idle_timer >= 10:
                self._idle_timer = 0
                self.resetRagdollTransform()

    def update(self):
        if not getattr(self, "is_valid", False):
            return
        try:
            scene = Range.logic.getCurrentScene()
            if "menu" in scene.name.lower():
                return

            # --- OTIMIZAÇÃO: RAGDOLL ATIVO E DAMPING DINÂMICO ---
            # Só forçamos a atualização manual da malha 3D se o ragdoll estiver acontecendo.
            if self.__status:
                self.object.update()
                
                # Damping: Mata os micro-tremores dos ossos no chão.
                # Faz o Bullet Physics colocar os ossos para "dormir", aliviando totalmente o peso na CPU.
                if self.bone_cache:
                    for item in self.bone_cache:
                        obj = item["obj"]
                        if obj.worldLinearVelocity.length_squared < 2.0:
                            obj.worldLinearVelocity *= 0.85
                            obj.worldAngularVelocity *= 0.85

            self.ragdoll_on_off()

            if self.debug_lines:
                self.drawRestLine()
        except Exception as e:
            print(f"[Ragdoll System Debug] ERRO no update(): {e}")
