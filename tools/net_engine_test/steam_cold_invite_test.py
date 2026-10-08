"""Cold-start argv invite through the attached component, without joining a fake room."""
import os
import traceback
from Range import logic
try:
    for i in range(4): logic.NextFrame()
    component = next(c for c in logic.getCurrentScene().objects['Camera'].components if hasattr(c, 'controller'))
    controller = component.controller
    controller.config.update(app_id=480, steam_dll=os.environ['ANASTACIO_STEAM_DLL'])
    assert controller.ensure_steam(), controller.error
    for i in range(4): logic.NextFrame()
    assert controller.invite == int(os.environ['ANASTACIO_EXPECT_INVITE'])
    assert not component.net.isConnected, 'invite must await user action'
    print('STEAMCOLD PASS (process argv delivered to component; no external invite claimed)', flush=True)
except Exception:
    traceback.print_exc()
    print('STEAMCOLD FAIL', flush=True)
finally:
    logic.endGame()
    logic.NextFrame()
