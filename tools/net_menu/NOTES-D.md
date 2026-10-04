# Frente D: NetworkMenu (notas)

## Onde ficou e por quê

`source/release/scripts/` não tem pasta de módulos Python do runtime do jogo (`Range/`): `bge/` só
tem `interpreter.py`, `templates_components/` são modelos do editor de texto e `modules/` é do
editor (bpy). Os menus ImGui de exemplo ficam em `source/release/demos/Example_ImgGui/scripts/`,
copiados ao lado do `.range`. Por isso o menu fica em `tools/net_menu/` até o template
Multiplayer Starter (etapa 5) definir o destino final (o plano cita `Range/net_menu.py`).

- `net_menu.py`: componente `NetworkMenu` (desenho com `Range.imgui`).
- `net_menu_logic.py`: máquina de estados, validação, idiomas, tema, escala, teclado na tela, foco.
- `net_api_stub.py`: simula `Range.network`; `load_network()` usa o real quando existir.
- `tests/`: pytest com mock de `Range`/`Range.imgui` (`python -m pytest tools/net_menu/tests`).

## Uso num jogo

Copie os três `.py` para a pasta de scripts do jogo (no `sys.path`, ao lado do `.range`) e adicione
o componente `net_menu.NetworkMenu` a um objeto. Tudo pelos `args`: título, idioma, porta padrão,
máximo de jogadores, touch (auto/on/off), escala, fonte, cores (`#RRGGBB[AA]`), mostrar LAN/
Configurações, `dev_build` (simulador de rede nas Configurações), `open_on_start`.

## Interpretações do plano (6.2) que precisam ser confirmadas pela API real

- Eventos: tratei `net.on_connect(fn)` / `net.on_disconnect(fn)` como registro de callback;
  `on_connect(client_id)`, `on_disconnect(reason, detail)` com `DisconnectReason` do protocolo.
- Extras opcionais, usados só se existirem (`getattr`): `on_reject(reason, detail)` com
  `RejectReason`, `on_chat(client_id, text)`, `on_start()`, `discover_lan()`, `set_ready(bool)`,
  `send_chat(text)`, `start_game()`, `isConnected`, `playerName`, e `host(port, max_players=,
  room_name=, password=)` (cai para `host(port)` se der `TypeError`).
- Cliente em `net.clients`: atributos `id`, `name`, `ping`, `ready`, `isHost`.
- Código de sala: base 36, 4 a 8 caracteres; é passado como está para `net.join()` (resolução do
  código fica com a API/lobby, fora da v1).
- Navegação: foco próprio (setas/Enter/Esc e D-pad/A/B do joystick 0). O C++ já marca janelas Python
  para a navegação por gamepad do ImGui (`KX_ImGui_Impl_Inputs_MarkGameplayWindow`); verificar na
  engine se as duas não ativam o mesmo botão duas vezes.
