# Guia do menu de multiplayer, telas da frente I

Criado em 2026-10-04. Para quem vai ligar o `NetworkMenu` (`tools/net_menu/`) no template Multiplayer
Starter e implementar `Range.network` na engine. Lista completa da API Python esperada:
`tools/net_menu/NOTES-D.md`.

## O que a frente I acrescenta

| Tela | Conteúdo | Chama |
|---|---|---|
| Pausa | sala, jogadores com ping e host, Continuar, Configurações, Desconectar (com confirmação) | `net.disconnect()` |
| Configurações | nome, idioma, escala da interface, toque auto/ligado/desligado, restaurar padrões; simulador de rede em `dev_build` | `net.playerName`, `net.set_simulation()` |
| Servidores LAN | lista com nome, jogadores/máx, ping, "Cheia", "Senha"; atualiza a cada 1 s; senha antes de entrar | `net.discover_lan()`, `net.join(addr, password=)` |

Tudo navega por teclado e gamepad: cima/baixo trocam o foco, esquerda/direita mudam valores, Enter/A ativa
(num campo de texto, abre o teclado na tela), Esc/B volta. As configurações podem ser salvas num JSON
(`settings_file`).

## Exemplo

No objeto que recebe o componente `net_menu.NetworkMenu` (args do componente na UI):

```
language        pt
show_lan        True
dev_build       True                       # mostra o simulador de rede
settings_file   //net_menu_settings.json   # vazio = não salva
```

Implementação mínima de `discover_lan()` em cima da frente H (lado C++ do `Range.network`):

```cpp
// Chamado pelo Python a cada ~1 s enquanto a tela LAN está aberta.
PyObject *discover_lan()
{
	const uint64_t now = net::steadyClockMs();
	if (!m_lan.running()) {
		m_lan.start();
	}
	if (now - m_lastLanRequest >= 1000) {
		m_lan.request(m_gameId, now);
		m_lastLanRequest = now;
	}
	m_lan.update(now, 5000);
	PyObject *list = PyList_New(0);
	for (const net::LanServerEntry &s : m_lan.servers()) {
		PyObject *d = Py_BuildValue("{s:s,s:s,s:i,s:i,s:i,s:i,s:i,s:O,s:s}",
			"name", s.info.name.c_str(), "address", s.address.c_str(), "port", s.info.enetPort,
			"ws_port", s.info.webSocketPort, "players", s.info.players, "max_players", s.info.maxPlayers,
			"ping", s.pingMs, "password", s.info.password ? Py_True : Py_False,
			"scene", s.info.sceneName.c_str());
		PyList_Append(list, d);
		Py_DECREF(d);
	}
	return list;
}
```

## Testes

`python -m pytest tools/net_menu/tests` (Range e Range.imgui são simulados). Cobrem as telas novas com
teclado e gamepad, os três idiomas completos, as configurações em arquivo e um fuzz de 100 000 entradas
(semente fixa) sobre as respostas LAN e o JSON de configurações.

## Limites

| Item | Valor |
|---|---|
| Idiomas | en, pt, es (tabela no `net_menu_logic.py`) |
| Escala | 0,75 a 2,0 (passo 0,25), sobre a escala automática pela altura da tela |
| Simulador | latência 0–500 ms, variação 0–200 ms, perda 0–50 % (só `dev_build`) |
| Lista LAN | uma linha por endereço:porta; ordem: abertas, ping, nome |
| Senha errada | motivo 7 provisório (fora do contrato; proposta em NOTES-D) |
| Web | a tela LAN fica vazia (sem UDP no navegador); escondê-la com `show_lan = False` |
