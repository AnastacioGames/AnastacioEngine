# Language Button: component that switches the game language with no script.
#
# Add it to a text (or any object) with Text > Translation > Add Language Button, or in
# Game > Components: range_language.LanguageButton.
#   Action      Next / Previous / Set (goes to "Language")
#   Click       a mouse click on the object triggers it (the mouse must be visible)
#   Key         optional keyboard key, e.g. LKEY
#   Show Name   a text object shows the current language name ("Português (Brasil)")

from collections import OrderedDict

import Range
import range_locale


class LanguageButton(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("Action", {"Next", "Previous", "Set"}),
        ("Language", ""),
        ("Click", True),
        ("Key", ""),
        ("Show Name", True),
        ("Click Radius", 0.08),
    ])

    def start(self, args):
        self.action = str(args.get("Action", "Next"))
        self.code = str(args.get("Language", "")).strip()
        self.click = bool(args.get("Click", True))
        key = str(args.get("Key", "")).strip().upper()
        if key and not key.endswith("KEY"):
            key += "KEY"
        self.key = getattr(Range.events, key, None) if key else None
        self.show_name = bool(args.get("Show Name", True)) and hasattr(self.object, "text")
        self.radius = max(0.0, float(args.get("Click Radius", 0.08)))
        self.shown = None

    def _clicked(self):
        mouse = Range.logic.mouse
        if not mouse.inputs[Range.events.LEFTMOUSE].activated:
            return False
        cam = self.object.scene.active_camera
        if cam is None:
            return False
        x, y = mouse.position
        hit = cam.getScreenRay(x, y, 10000.0)
        ob = self.object
        if hit is not None and (hit is ob or hit.parent is ob or ob.parent is hit):
            return True
        # texts usually have no collision: accept a click close to the object on screen
        if self.radius > 0.0:
            sx, sy = cam.getScreenPosition(ob)
            return abs(sx - x) <= self.radius * 2.0 and abs(sy - y) <= self.radius
        return False

    def update(self):
        fire = self.click and self._clicked()
        if not fire and self.key is not None:
            fire = Range.logic.keyboard.inputs[self.key].activated
        if fire:
            if self.action == "Previous":
                range_locale.step(-1)
            elif self.action == "Set" and self.code:
                range_locale.set_language(self.code)
            else:
                range_locale.step(1)
        if self.show_name:
            lang = range_locale._state["language"]
            if lang != self.shown:
                self.shown = lang
                self.object.text = range_locale.name(lang)
