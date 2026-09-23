"""
Teste manual para a validade de KX_GameObject.getPhysicsId().

Uso:
1. Crie dois objetos na mesma cena:
   - um objeto controlador, sem necessidade de física, para receber este componente;
   - um alvo com Physics Type diferente de "No Collision".
2. No campo "Target Object", escreva exatamente o nome do alvo.
3. Dê Play e veja o console.

O componente captura o ID de física do alvo, chama endObject() e espera a
remoção efetiva. Em seguida tenta criar um veículo com o ID salvo. O resultado
correto é a mensagem PASS com ValueError; o alvo será removido de propósito.
"""

from collections import OrderedDict

import Range


class PhysicsIdLifetimeTestComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "PHYSICS"),
        ("C_Header /Teste de vida do Physics ID/PHYSICS", True),
        ("Target Object", "PhysicsIdTarget"),
        ("Frames Before Check", 2),
    ])

    def start(self, args):
        self._target_name = args["Target Object"]
        self._frames_before_check = max(1, int(args["Frames Before Check"]))
        self._physics_id = 0
        self._frames_waited = 0
        self._state = "capture"

    def _find_target(self):
        try:
            return self.object.scene.objects[self._target_name]
        except KeyError:
            return None

    def update(self):
        if self._state == "done":
            return

        if self._state == "capture":
            target = self._find_target()
            if target is None:
                print("PhysicsIdLifetimeTest: FAIL - alvo '%s' nao encontrado." % self._target_name)
                self._state = "done"
                return

            self._physics_id = target.getPhysicsId()
            if not self._physics_id:
                print("PhysicsIdLifetimeTest: FAIL - '%s' nao possui controlador de fisica." % target.name)
                self._state = "done"
                return

            print("PhysicsIdLifetimeTest: ID %d capturado de '%s'; removendo o alvo." %
                  (self._physics_id, target.name))
            target.endObject()
            self._state = "wait_for_removal"
            return

        if self._state == "wait_for_removal":
            if self._find_target() is not None:
                self._frames_waited += 1
                if self._frames_waited > 30:
                    print("PhysicsIdLifetimeTest: FAIL - alvo nao foi removido apos 30 frames.")
                    self._state = "done"
                return

            self._frames_waited += 1
            if self._frames_waited < self._frames_before_check:
                return

            self._state = "check"

        if self._state == "check":
            try:
                Range.constraints.createVehicle(self._physics_id)
            except ValueError as error:
                print("PhysicsIdLifetimeTest: PASS - ID expirado rejeitado: %s" % error)
            except Exception as error:
                print("PhysicsIdLifetimeTest: FAIL - excecao inesperada: %s" % error)
            else:
                print("PhysicsIdLifetimeTest: FAIL - ID expirado foi aceito.")

            self._state = "done"


# O campo de nome de classe do Python Component neste fork limita o valor a
# 20 caracteres; use o alias truncado que o editor persiste.
PhysicsIdLifetimeTes = PhysicsIdLifetimeTestComponent
