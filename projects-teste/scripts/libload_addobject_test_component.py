"""
Teste manual da Fase 3 (LibLoad sem instanciar + addObject via bmain).

Uso:
1. Vincule um objeto de uma biblioteca externa usando o botao "Link to
   LibLoad" no Outliner (External Files), sem instanciar em nenhuma cena.
2. Adicione este componente a qualquer objeto ja existente na cena de jogo.
3. Preencha "Object Name" com o nome exato do objeto vinculado
   (ex.: "Armature.000").
4. De Play e aperte a tecla configurada em "Trigger Key" (padrao: barra de
   espaco) duas vezes:
   - 1a vez: addObject deve achar o objeto direto em bmain (via
     BL_Converter::FindOrConvertMainObject) e instancia-lo na cena.
   - 2a vez: addObject deve achar o objeto ja convertido via busca
     cross-scene e apenas replicar, sem crash nem duplicidade quebrada.
"""

from collections import OrderedDict

import Range


class LibLoadAddObjectTestComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "LINKED"),
        ("C_Header /Teste addObject via bmain (LibLoad)/LINKED", True),
        ("Object Name", "Armature.000"),
        ("Trigger Key", "SPACEKEY"),
    ])

    def start(self, args):
        self._target_name = args["Object Name"]
        self._key_code = getattr(Range.events, args["Trigger Key"], Range.events.SPACEKEY)
        self._call_count = 0

    def update(self):
        key = Range.logic.keyboard.inputs[self._key_code]
        if Range.logic.KX_INPUT_JUST_ACTIVATED not in key.queue:
            return

        self._call_count += 1
        scene = self.object.scene

        print("LibLoadAddObjectTest: chamada #%d - addObject('%s') sem libpath..." %
              (self._call_count, self._target_name))

        try:
            new_obj = scene.addObject(self._target_name, self.object)
        except Exception as error:
            print("LibLoadAddObjectTest: FAIL - excecao ao chamar addObject: %s" % error)
            return

        if new_obj is None:
            print("LibLoadAddObjectTest: FAIL - addObject retornou None.")
            return

        print("LibLoadAddObjectTest: PASS - objeto '%s' criado (posicao %s)." %
              (new_obj.name, new_obj.worldPosition))


# O campo de nome de classe do Python Component neste fork limita o valor a
# 22 caracteres; use o alias truncado que o editor persiste.
LibLoadAddObjectTestCo = LibLoadAddObjectTestComponent
