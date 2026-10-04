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
Configurações, `dev_build` (simulador de rede nas Configurações), `open_on_start`, `settings_file`
(JSON das Configurações, ex. `//net_menu_settings.json`; vazio = não salva).

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

## Frente I (2026-10-04): telas de Pausa, Configurações e Servidores LAN

- **Pausa:** sala, jogadores (`n/máx`, ping, host), Continuar, Configurações, Desconectar com confirmação
  (sim/não; Esc cancela).
- **Configurações:** nome, idioma, escala da interface (0,75–2,0), controles de toque (auto/ligado/desligado),
  restaurar padrões; em `dev_build`, latência (0–500 ms), variação (0–200 ms) e perda (0–50 %), aplicadas
  com `net.set_simulation`. Esc/Voltar valida o nome e salva em `settings_file`.
- **Servidores LAN:** lista atualizada a cada 1 s, salas abertas primeiro e por ping; marca "Cheia" e
  "Senha". Primeiro clique/A seleciona, o segundo (ou clique duplo) entra; sala cheia mostra aviso; sala com
  senha pede a senha antes.
- **Teclado e gamepad:** setas/D-pad para cima/baixo mudam o foco; esquerda/direita mudam valores (idioma,
  escala, simulador); Enter/A ativa; Esc/B volta. Campo de texto também recebe foco: Enter/A abre o teclado na
  tela, para quem só tem gamepad.

### API Python que o menu espera de `Range.network` (lista para a implementação local)

O menu funciona com o mínimo da seção 6.2 do plano; o resto é opcional (`getattr`) e liga recursos.

| Nome | Tipo | Uso no menu |
|---|---|---|
| `host(port, max_players=8, room_name="", password="")` | função | Hospedar. Sem os nomeados, cai para `host(port)`. |
| `join(address, password="")` | função | Entrar e LAN. `address` = `"host:porta"`, `"[v6]:porta"` ou código de sala. Sem `password`, cai para `join(address)`. |
| `disconnect()` | função | Sair do lobby e da pausa. |
| `set_ready(ready: bool)` | função, opcional | Botão Pronto do lobby. |
| `send_chat(text: str)` | função, opcional | Chat do lobby (≤ 200 bytes UTF-8). |
| `start_game() -> bool` | função, opcional | Iniciar (só host). False se nem todos estão prontos. |
| `discover_lan() -> list[dict]` | função, opcional | Não bloqueia: a primeira chamada começa a busca, as seguintes devolvem o que já respondeu (a engine reenvia o pedido a cada ~1 s). |
| `set_simulation(latency_ms, jitter_ms, loss_percent)` | função, opcional | Simulador de rede das Configurações (só `dev_build`). |
| `on_connect(fn(client_id))` | evento | Conectou (cliente) ou abriu a sala (host). |
| `on_disconnect(fn(reason, detail))` | evento | `DisconnectReason` 1–5. |
| `on_reject(fn(reason, detail))` | evento, opcional | `RejectReason` 1–6 (+ 7 provisório, abaixo). |
| `on_chat(fn(client_id, text))` | evento, opcional | Linha no chat do lobby. |
| `on_start(fn())` | evento, opcional | Partida começou: o menu fecha. |
| `isServer`, `isConnected` | atributos | Estado. |
| `playerName` | atributo (escrita) | Nome do jogador, vindo das Configurações. |
| `roomName`, `maxPlayers` | atributos, opcionais | Pausa (sala e `n/máx`). |
| `clients` | lista | Cada cliente com `id`, `name`, `ping` (ms), `ready`, `isHost`. |

Dicionário de `discover_lan()` (formato da frente H): `name`, `address` (IPv4), `port` (ENet), `ws_port`
(0 = sem WebSocket), `players`, `max_players`, `ping` (ms), `password` (bool), `scene`. O menu também
aceita o formato antigo do stub (`"address": "ip:porta"` sem `port`).

### Dúvidas novas

1. **Senha errada:** o contrato não tem motivo de `Reject` para senha. Proposta: `7 WrongPassword`. O stub e
   o menu já usam 7 (`reject_password`), marcado como provisório.
2. A senha vai em que campo do `Hello`? Proposta: `str password` no fim do `Hello` (versão 2 do protocolo),
   ou um hash dela no `token`. Fica para a frente que implementar `host(password=)`.
3. `set_simulation` só faz sentido no build de desenvolvimento; a engine pode ignorar no build final.
