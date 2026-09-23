# -*- coding: utf-8 -*-
"""
Fase 0 do docs/vehicle-system-roadmap.md — baseline reproduzivel e testes de
contrato do PHY_IVehicle / KX_VehicleWrapper atuais, ANTES de qualquer mudanca
em C++.

Nao depende de NativeVehicleComponent.py nem de nenhum script do jogo: cria o
veiculo direto pela API publica (Range.constraints.createVehicle +
vehicle.addWheel) para isolar o contrato da engine da logica do Rolima Racer.

Uso:
1. Crie uma cena com:
   - "Chassis": objeto com Physics Type = Rigid Body/Dynamic, sem "No Collision".
   - "Floor": chao estatico plano, grande o suficiente para as 4 rodas.
   - "Ramp": rampa estatica, posicionada a frente do carro (usada so
     visualmente nesta fase; nenhuma assertion depende dela ainda).
   - "Obstacle": caixa estatica pequena a frente do carro.
   - Um objeto de controle qualquer (pode ser o proprio "Chassis") com este
     componente.
2. Ajuste "Chassis Object" se o nome do chassi for diferente.
3. Play. O resultado fica no console E em
   projects-teste/vehicle_contract_test_log.txt (escrita incremental, uma
   linha por evento, para poder comparar rodadas).
4. PASS/FAIL de cada assertion aparece prefixado por "VehicleContractTest:".
   FAIL nao aborta o teste inteiro; o componente segue para as proximas fases
   e imprime um resumo final "RESUMO:" com contagem PASS/FAIL/SKIP.

Convencao usada (confirmada na revisao tecnica do roadmap):
    right = eixo X (0), up = eixo Z (2), forward = eixo Y (1)
    down_dir  = (0, 0, -1)   -> eixo da suspensao, aponta para baixo
    axle_dir  = (-1, 0, 0)   -> eixo de rotacao da roda (right invertido)
"""

from collections import OrderedDict
import json
import os

import Range
from mathutils import Vector

LOG_PATH = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "vehicle_contract_test_log.txt"
))

DOWN_DIR = Vector((0.0, 0.0, -1.0))
AXLE_DIR = Vector((-1.0, 0.0, 0.0))
REST_LENGTH = 0.3
WHEEL_RADIUS = 0.3


class VehicleContractTestComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "PHYSICS"),
        ("C_Header /Fase 0 - Vehicle Contract Test/PHYSICS", True),
        ("Chassis Object", "Chassis"),
        ("Wheel Half Width", 1.0),
        ("Front Axle Y", 1.5),
        ("Rear Axle Y", -1.5),
        ("Frames Per Step", 3),
    ])

    def start(self, args):
        self._chassis_name = args["Chassis Object"]
        self._wheel_half_width = max(0.01, float(args["Wheel Half Width"]))
        self._front_axle_y = float(args["Front Axle Y"])
        self._rear_axle_y = float(args["Rear Axle Y"])
        self._frames_per_step = max(1, int(args["Frames Per Step"]))
        self._frame_wait = 0
        self._results = []
        self._log_lines = []
        self._vehicle = None
        self._chassis = None
        self._wheel_visuals = []

        self._steps = [
            self._step_setup_wheelless,
            self._step_index_errors_zero_wheels,
            self._step_add_first_wheel,
            self._step_index_errors_out_of_range,
            self._step_add_remaining_wheels,
            self._step_config_and_coordinate_contract,
            self._step_vehicle_preset,
            self._step_wheel_air_vs_contact,
            self._step_forward_reverse_sign,
            self._step_speed_units,
            self._step_remove_chassis_live_proxy,
            self._step_remove_chassis_live_proxy_check,
            self._step_finish,
        ]
        self._step_index = 0
        self._log("VehicleContractTest: iniciado. Chassis=%s" % self._chassis_name)

    # ------------------------------------------------------------------
    def _log(self, line):
        print(line)
        self._log_lines.append(line)

    def _record(self, name, ok, detail=""):
        status = "PASS" if ok else "FAIL"
        self._results.append((name, status))
        self._log("VehicleContractTest: %s - %s%s" % (status, name, (" - " + detail) if detail else ""))

    def _record_skip(self, name, detail=""):
        self._results.append((name, "SKIP"))
        self._log("VehicleContractTest: SKIP - %s%s" % (name, (" - " + detail) if detail else ""))

    def _find(self, name):
        try:
            return self.object.scene.objects[name]
        except KeyError:
            return None

    # ------------------------------------------------------------------
    def update(self):
        if self._step_index >= len(self._steps):
            return

        if self._frame_wait > 0:
            self._frame_wait -= 1
            return

        step = self._steps[self._step_index]
        self._step_index += 1
        try:
            step()
        except Exception as error:  # nao deixa uma excecao nao prevista matar o resumo
            self._record(step.__name__, False, "excecao nao tratada: %r" % (error,))
        self._frame_wait = self._frames_per_step

    # ------------------------------------------------------------------
    # 1. zero rodas: getNumWheels antes de addWheel, e indices em veiculo vazio
    def _step_setup_wheelless(self):
        self._chassis = self._find(self._chassis_name)
        if self._chassis is None:
            self._record("chassis encontrado", False, "objeto '%s' nao existe na cena" % self._chassis_name)
            return
        self._record("chassis encontrado", True)

        physics_id = self._chassis.getPhysicsId()
        if not physics_id:
            self._record("chassis tem physics id", False)
            return
        self._record("chassis tem physics id", True, "id=%d" % physics_id)

        # Um physics id sozinho nao garante que este seja um corpo dinamico.
        # Registra a massa que o Bullet realmente expoe e a cadeia de pais:
        # isso torna visivel o caso comum de um mesh Dynamic filho de um
        # Empty/compound, que acaba com massa efetiva zero em runtime.
        try:
            parents = []
            current = self._chassis
            while current is not None:
                parents.append(current.name)
                current = current.parent
            self._log("VehicleContractTest: INFO - chassis runtime mass=%r; hierarquia=%s" % (
                self._chassis.mass, " <- ".join(parents)))
        except Exception as error:
            self._log("VehicleContractTest: INFO - nao foi possivel ler massa/hierarquia do chassis: %r" % (
                error,))

        try:
            self._vehicle = Range.constraints.createVehicle(physics_id)
        except Exception as error:
            self._record("createVehicle", False, repr(error))
            return
        self._record("createVehicle", True)

        num = self._vehicle.getNumWheels()
        self._record("getNumWheels() == 0 antes de addWheel", num == 0, "retornou %r" % (num,))

    # 2. indices invalidos com zero rodas: -1 e numWheels (== 0)
    def _step_index_errors_zero_wheels(self):
        if self._vehicle is None:
            self._record_skip("indices invalidos (zero rodas)", "sem veiculo")
            return
        for bad_index, label in ((-1, "indice -1"), (0, "indice 0 (== numWheels)")):
            try:
                self._vehicle.applyEngineForce(0.0, bad_index)
            except Exception as error:
                self._record("rejeita %s com zero rodas" % label, True, repr(error))
            else:
                self._record("rejeita %s com zero rodas" % label, False, "nao lancou excecao")

    # 3. primeira roda recem-adicionada: estado inicial coerente
    def _step_add_first_wheel(self):
        if self._vehicle is None or self._chassis is None:
            self._record_skip("primeira roda", "sem veiculo/chassis")
            return

        local_pos = Vector((self._wheel_half_width, self._front_axle_y, 0.0))
        wheel_ob = self._make_wheel_visual("VCT_Wheel_0", local_pos)
        connection_point = local_pos.copy()
        connection_point.z = REST_LENGTH
        try:
            self._vehicle.addWheel(
                wheel_ob, connection_point, DOWN_DIR, AXLE_DIR, REST_LENGTH, WHEEL_RADIUS, True
            )
        except Exception as error:
            self._record("addWheel #0", False, repr(error))
            return
        self._record("addWheel #0", True)

        num = self._vehicle.getNumWheels()
        self._record("getNumWheels() == 1 apos addWheel", num == 1, "retornou %r" % (num,))

        try:
            pos = self._vehicle.getWheelPosition(0)
            rot = self._vehicle.getWheelRotation(0)
            self._log("VehicleContractTest: INFO - wheel0 pos=%r rot=%r (estado logo apos addWheel, "
                       "antes do 1o passo de fisica)" % (pos, rot))
            self._record("getWheelPosition/getWheelRotation nao lancam apos addWheel", True)
        except Exception as error:
            self._record("getWheelPosition/getWheelRotation nao lancam apos addWheel", False, repr(error))

    # 4. indices invalidos com 1 roda: -1 e numWheels (== 1)
    def _step_index_errors_out_of_range(self):
        if self._vehicle is None:
            self._record_skip("indices invalidos (1 roda)", "sem veiculo")
            return
        num = self._vehicle.getNumWheels()
        for bad_index, label in ((-1, "indice -1"), (num, "indice == numWheels")):
            try:
                self._vehicle.getWheelPosition(bad_index)
            except Exception as error:
                self._record("rejeita %s" % label, True, repr(error))
            else:
                self._record("rejeita %s" % label, False, "nao lancou excecao")

    # 5. completa 4 rodas para os testes de contato/avanco/re
    def _step_add_remaining_wheels(self):
        if self._vehicle is None:
            self._record_skip("rodas restantes", "sem veiculo")
            return
        specs = [
            ("VCT_Wheel_1", Vector((-self._wheel_half_width, self._front_axle_y, 0.0))),
            ("VCT_Wheel_2", Vector((self._wheel_half_width, self._rear_axle_y, 0.0))),
            ("VCT_Wheel_3", Vector((-self._wheel_half_width, self._rear_axle_y, 0.0))),
        ]
        ok_all = True
        for name, local_pos in specs:
            wheel_ob = self._make_wheel_visual(name, local_pos)
            connection_point = local_pos.copy()
            connection_point.z = REST_LENGTH
            try:
                self._vehicle.addWheel(
                    wheel_ob, connection_point, DOWN_DIR, AXLE_DIR, REST_LENGTH, WHEEL_RADIUS, False
                )
            except Exception as error:
                ok_all = False
                self._log("VehicleContractTest: FAIL - addWheel(%s): %r" % (name, error))
        self._record("addWheel para as 4 rodas", ok_all and self._vehicle.getNumWheels() == 4,
                      "numWheels=%d" % self._vehicle.getNumWheels())

    def _make_wheel_visual(self, name, local_pos):
        existing = self._find(name)
        if existing is not None:
            if existing not in self._wheel_visuals:
                self._wheel_visuals.append(existing)
            return existing
        wheel = self.object.scene.addObject(self._chassis, self._chassis, 0)
        wheel.name = name
        wheel.worldPosition = self._chassis.worldPosition + local_pos
        wheel.removeParent()
        wheel.suspendPhysics()
        self._wheel_visuals.append(wheel)
        return wheel

    def _step_config_and_coordinate_contract(self):
        """Contrato de leitura: valores estruturais e eixos nao podem mudar de sinal."""
        if self._vehicle is None or self._vehicle.getNumWheels() != 4:
            self._record_skip("configuracao/eixos do veiculo", "sem veiculo de quatro rodas")
            return
        try:
            config = self._vehicle.getWheelConfig(0)
            expected_point = Vector((self._wheel_half_width, self._front_axle_y, REST_LENGTH))
            point_ok = (Vector(config["connectionPoint"]) - expected_point).length < 0.0001
            dirs_ok = ((Vector(config["downDirection"]) - DOWN_DIR).length < 0.0001 and
                       (Vector(config["axleDirection"]) - AXLE_DIR).length < 0.0001)
            shape_ok = (point_ok and dirs_ok and
                        abs(config["suspensionRestLength"] - REST_LENGTH) < 0.0001 and
                        abs(config["wheelRadius"] - WHEEL_RADIUS) < 0.0001 and
                        config["hasSteering"] is True)
            self._record("getWheelConfig preserva geometria e sinal publico do eixo", shape_ok, repr(config))

            axes = self._vehicle.getCoordinateSystem()
            self._record("getCoordinateSystem() == (0, 2, 1)", axes == (0, 2, 1), repr(axes))
            try:
                self._vehicle.setCoordinateSystem(0, 0, 1)
            except (AttributeError, ValueError):
                self._record("setCoordinateSystem rejeita eixos repetidos", self._vehicle.getCoordinateSystem() == axes)
            else:
                self._record("setCoordinateSystem rejeita eixos repetidos", False, "nao lancou excecao")

            original_mask = self._vehicle.rayMask
            # O backend recebe a mascara por ``short`` assinado. A mascara
            # completa 0xffff aparece como -1; 0x7fff e a maior mascara que
            # sobrevive ao round-trip e ainda cobre os grupos padrao, sem
            # reduzir o raycast ao bit 1 (o que pode ignorar o Floor).
            safe_collision_mask = (1 << 15) - 1
            test_mask = original_mask if 0 < original_mask <= safe_collision_mask else safe_collision_mask
            if test_mask != original_mask:
                self._log("VehicleContractTest: INFO - rayMask inicial assinada (%r); "
                          "usando mascara segura %d no teste" %
                          (original_mask, safe_collision_mask))
            self._vehicle.rayMask = test_mask
            self._record("rayMask aceita valor valido e round-trip",
                         self._vehicle.rayMask == test_mask,
                         "inicial=%r, testado=%r" % (original_mask, test_mask))
        except Exception as error:
            self._record("configuracao/eixos do veiculo", False, repr(error))

    def _step_vehicle_preset(self):
        """Fase 5: export, import e rejeicao sem mutar shape incompativel."""
        if self._vehicle is None or self._vehicle.getNumWheels() != 4:
            self._record_skip("vehicle preset v1", "sem veiculo de quatro rodas")
            return
        preset_path = os.path.join(os.path.dirname(LOG_PATH), "vehicle_contract_test_preset.json")
        incompatible_path = preset_path + ".incompatible"
        malformed_path = preset_path + ".malformed"
        try:
            self._vehicle.savePreset(preset_path)
            with open(preset_path, "r", encoding="utf-8") as handle:
                preset = json.load(handle)
            basic_shape_ok = (preset.get("version") == 1 and
                              len(preset.get("wheels", [])) == 4 and
                              preset.get("coordinateSystem") == {"right": 0, "up": 2, "forward": 1})
            self._record("savePreset gera vehicle_preset_v1 valido", basic_shape_ok)

            try:
                self._vehicle.rebuildPreset(preset_path, self._wheel_visuals[:3])
            except ValueError:
                self._record("rebuildPreset rejeita lista visual com tamanho incompativel",
                             self._vehicle.getNumWheels() == 4)
            else:
                self._record("rebuildPreset rejeita lista visual com tamanho incompativel", False,
                             "nao lancou ValueError")

            self._vehicle.rebuildPreset(preset_path, self._wheel_visuals)
            self._record("rebuildPreset aceita lista visual correspondente",
                         self._vehicle.getNumWheels() == 4)

            preset["wheels"] = preset["wheels"][:-1]
            with open(incompatible_path, "w", encoding="utf-8") as handle:
                json.dump(preset, handle)
            try:
                self._vehicle.loadPreset(incompatible_path)
            except ValueError:
                self._record("loadPreset rejeita numero de rodas incompativel", self._vehicle.getNumWheels() == 4)
            else:
                self._record("loadPreset rejeita numero de rodas incompativel", False, "nao lancou ValueError")

            with open(preset_path, "r", encoding="utf-8") as handle:
                structural = json.load(handle)
            structural["wheels"][0]["wheelRadius"] += 0.1
            with open(incompatible_path, "w", encoding="utf-8") as handle:
                json.dump(structural, handle)
            try:
                self._vehicle.loadPreset(incompatible_path)
            except ValueError:
                self._record("loadPreset rejeita geometria de roda incompativel",
                             self._vehicle.getNumWheels() == 4)
            else:
                self._record("loadPreset rejeita geometria de roda incompativel", False,
                             "nao lancou ValueError")

            self._vehicle.loadPreset(preset_path)
            self._record("loadPreset aceita o arquivo recem-exportado", True)

            with open(malformed_path, "w", encoding="utf-8") as handle:
                handle.write('{"version": 1} texto-extra')
            try:
                self._vehicle.loadPreset(malformed_path)
            except ValueError:
                self._record("loadPreset rejeita JSON truncado/com texto extra",
                             self._vehicle.getNumWheels() == 4)
            else:
                self._record("loadPreset rejeita JSON truncado/com texto extra", False,
                             "nao lancou ValueError")
        except Exception as error:
            self._record("vehicle preset v1", False, repr(error))
        finally:
            for path in (preset_path, incompatible_path, malformed_path, preset_path + "@"):
                try:
                    os.remove(path)
                except OSError:
                    pass

    # 6. roda no ar vs contato - depende de Floor existir sob o chassi
    def _step_wheel_air_vs_contact(self):
        floor = self._find("Floor")
        if floor is None or self._vehicle is None:
            self._record_skip("roda no ar vs contato", "sem 'Floor' na cena ou sem veiculo")
            return
        # Nesta fase so registramos o estado observavel hoje (posicao da roda
        # apos alguns passos), sem inventar um campo "isInContact" que ainda
        # nao existe no wrapper (isso e trabalho da Fase 1B).
        for i in range(self._vehicle.getNumWheels()):
            pos = self._vehicle.getWheelPosition(i)
            self._log("VehicleContractTest: INFO - wheel%d pos apos assentar=%r" % (i, pos))
            state = self._vehicle.getWheelState(i)
            readable = all(key in state for key in
                           ("physicsTick", "worldPosition", "rotation", "isInContact",
                            "hardPointWorld", "wheelDirectionWorld"))
            self._record("getWheelState #%d possui snapshot completo" % i, readable)
        self._record("estado de posicao das 4 rodas apos assentar e legivel", True)

    # 7. avanco/re - confirma o sinal usado por applyEngineForce hoje
    def _step_forward_reverse_sign(self):
        if self._vehicle is None or self._vehicle.getNumWheels() < 2:
            self._record_skip("avanco/re", "sem veiculo/rodas suficientes")
            return
        try:
            self._vehicle.applyEngineForce(500.0, 0)
            self._vehicle.applyEngineForce(500.0, 1)
            self._record("applyEngineForce(+) aceito nas rodas dianteiras", True)
        except Exception as error:
            self._record("applyEngineForce(+) aceito nas rodas dianteiras", False, repr(error))
        try:
            self._vehicle.applyEngineForce(-500.0, 0)
            self._vehicle.applyEngineForce(-500.0, 1)
            self._record("applyEngineForce(-) aceito nas rodas dianteiras", True)
        except Exception as error:
            self._record("applyEngineForce(-) aceito nas rodas dianteiras", False, repr(error))
        # Sinal fisico real (avanca/recua de fato) exige leitura de posicao
        # do chassi ao longo de varios frames; registrado como TODO da Fase 1B
        # (telemetria), nao decidido aqui.

    # 8. unidade de velocidade - so registra o valor bruto hoje
    def _step_speed_units(self):
        if self._chassis is None:
            self._record_skip("unidade de velocidade", "sem chassis")
            return
        if hasattr(self._chassis, "getLinearVelocity"):
            vel = self._chassis.getLinearVelocity()
            self._log("VehicleContractTest: INFO - chassis linear velocity (m/s, SI)=%r" % (vel,))
            self._record("getLinearVelocity legivel (referencia SI para comparar com getCurrentSpeedKmHour)", True)
        else:
            self._record_skip("unidade de velocidade", "getLinearVelocity indisponivel")

    # 9. remocao do chassi/constraint com proxy vivo. endObject() no BGE so
    #    marca o objeto para remocao no fim do frame (KX_Scene::
    #    RemoveEuthanasyObjects); o controller fisico so e destruido - e o
    #    KX_VehicleWrapper so e invalidado via SetInvalidationCallback - depois
    #    disso. Por isso o teste precisa checar num frame seguinte, nao na
    #    mesma chamada: checar imediatamente so provaria que o objeto ainda
    #    nao foi de fato destruido, nao que a invalidacao esta quebrada.
    def _step_remove_chassis_live_proxy(self):
        if self._vehicle is None or self._chassis is None:
            self._record_skip("remocao do chassi com proxy vivo", "sem veiculo/chassis")
            return
        self._log("VehicleContractTest: INFO - removendo chassis com KX_VehicleWrapper ainda referenciado.")
        self._chassis.endObject()

    def _step_remove_chassis_live_proxy_check(self):
        if self._vehicle is None:
            self._record_skip("proxy falha de forma controlada apos remover chassis", "sem veiculo")
            return
        try:
            self._vehicle.getNumWheels()
        except Exception as error:
            self._record("proxy falha de forma controlada apos remover chassis", True, repr(error))
        else:
            self._record("proxy falha de forma controlada apos remover chassis", False,
                          "retornou normalmente apos endObject() + espera de frame")

    # ------------------------------------------------------------------
    def _step_finish(self):
        passed = sum(1 for _, s in self._results if s == "PASS")
        failed = sum(1 for _, s in self._results if s == "FAIL")
        skipped = sum(1 for _, s in self._results if s == "SKIP")
        self._log("VehicleContractTest: RESUMO: %d PASS, %d FAIL, %d SKIP (total %d)" %
                   (passed, failed, skipped, len(self._results)))
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as handle:
                handle.write("\n".join(self._log_lines) + "\n")
        except OSError as error:
            print("VehicleContractTest: nao foi possivel gravar log em disco: %r" % (error,))


# Compatibilidade temporária com executáveis que ainda limitam o identificador
# completo ``module.Class`` a 63 caracteres. O binding antigo procura este
# sufixo truncado; o operador corrigido passa a usar o nome completo.
VehicleContractTestComp = VehicleContractTestComponent
