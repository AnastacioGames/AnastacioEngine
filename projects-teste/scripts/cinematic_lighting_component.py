"""Runtime cinematic-lighting profile for AnastacioEngine test scenes.

Attach ``CinematicLighting`` to one persistent Empty in the scene. On game
start it enables and configures the engine's native SSAO, Tonemap, Bloom and
FXAA filters through ``scene.filterManager``; no C++ change or custom GLSL is
needed. Press F8 by default to toggle only the filters managed by this
component.

The component does not configure shadow maps: enable shadows and, optionally,
Cascaded Shadow Mapping on the scene's Sun in the editor before starting the
game. Runtime light shadow settings are intentionally read-only.
"""

from collections import OrderedDict

import Range


class CinematicLighting(Range.types.KX_PythonComponent):
    """Apply a balanced real-time lighting profile to the current scene."""

    args = OrderedDict([
        ("enabled", True),
        ("toggle_key", "F8KEY"),
        ("ssao_samples", 16),
        ("ssao_strength", 2.0),
        ("ssao_distance", 1.0),
        ("ssao_attenuation", 1.0),
        ("tonemap_exposure", 1.0),
        ("tonemap_gamma", 2.2),
        ("bloom_intensity", 1.0),
        ("bloom_threshold", 0.85),
    ])

    def start(self, args):
        self.settings = {
            "ssao_samples": int(args["ssao_samples"]),
            "ssao_strength": float(args["ssao_strength"]),
            "ssao_distance": float(args["ssao_distance"]),
            "ssao_attenuation": float(args["ssao_attenuation"]),
            "tonemap_exposure": float(args["tonemap_exposure"]),
            "tonemap_gamma": float(args["tonemap_gamma"]),
            "bloom_intensity": float(args["bloom_intensity"]),
            "bloom_threshold": float(args["bloom_threshold"]),
        }
        self.enabled = False
        self.toggle_key = getattr(Range.events, args["toggle_key"], None)

        if self.toggle_key is None:
            print("[CinematicLighting] toggle_key '{}' invalida; alternancia por tecla desativada.".format(
                args["toggle_key"]))

        self._warn_if_sun_has_no_shadow()
        self._set_enabled(bool(args["enabled"]))

    def update(self):
        if self.toggle_key is None:
            return

        keyboard = Range.logic.keyboard
        if keyboard.events[self.toggle_key] == Range.logic.KX_INPUT_JUST_ACTIVATED:
            self._set_enabled(not self.enabled)

    def _warn_if_sun_has_no_shadow(self):
        sun = Range.logic.getCurrentScene().worldSun
        if sun is None:
            print("[CinematicLighting] aviso: a cena nao possui World Sun; configure uma Sun com sombras no editor.")
        elif not sun.useShadow:
            print("[CinematicLighting] aviso: World Sun sem sombras; ative Use Shadow/CSM no editor.")

    def _set_enabled(self, enabled):
        filters = Range.logic.getCurrentScene().filterManager
        calls = (
            ("SSAO", filters.changeSSAOValues,
             (enabled, self.settings["ssao_samples"], self.settings["ssao_strength"],
              self.settings["ssao_distance"], self.settings["ssao_attenuation"])),
            ("Tonemap", filters.changeTonemapValues,
             (enabled, self.settings["tonemap_exposure"], self.settings["tonemap_gamma"])),
            ("Bloom", filters.changeBloomValues,
             (enabled, self.settings["bloom_intensity"], self.settings["bloom_threshold"])),
            ("FXAA", filters.changeFxaaValues, (enabled,)),
        )

        failed = []
        for name, method, values in calls:
            try:
                method(*values)
            except (TypeError, ValueError) as exc:
                failed.append("{}: {}".format(name, exc))

        if failed:
            print("[CinematicLighting] erro ao {} perfil: {}".format(
                "ativar" if enabled else "desativar", "; ".join(failed)))
            return

        self.enabled = enabled
        print("[CinematicLighting] perfil {}: SSAO, Tonemap, Bloom e FXAA.".format(
            "ativado" if enabled else "desativado"))
