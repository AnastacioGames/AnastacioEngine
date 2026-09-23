# Teste manual: Exportar Web no editor (marco E/F)

Arquivo: `editor-web-teste.range` (cena com chão xadrez, luz e cubo; gerado por `tools/create_web_render_scene.py`).
Requisito: `build-web-release/bin/RangeRuntime.{js,wasm,data}` existe (já gerado) e `python` no PATH.

Abra `build/bin/RangeEngine.exe`, depois `File > Open` este `.range`. Painel: **Properties > Scene > Web (Range)**.

## 1. Validar
- [OK] Clique **Validar Web**. Esperado: resumo sem erros (ícone de check).

## 2. Exportar Web
- [OK] Sem salvar (se o arquivo estiver modificado): **Exportar Web** avisa "Salve o arquivo antes de exportar".
- [OK] Salve (Ctrl+S) e clique **Exportar Web**. Esperado: "Pacote Web gerado em .../web/" e a pasta
      `web/` ao lado do `.range` com `index.html`, `RangeRuntime.*`, `game/`, `manifest.json`.
- [OK] Com **auto_preflight** ligado, a mensagem termina com o resultado do pré-voo (sem problemas).

## 3. Testar pacote no navegador
- [OK] Clique **Testar pacote no navegador** (~15 s, Chrome/Edge sem janela). Esperado: "sem problemas".
- [OK] Servir na mão para ver com os próprios olhos: `cd web && python serve.py 8080`, abrir
      http://localhost:8080/, esperar **Jogar**; deve mostrar o chão xadrez iluminado com o cubo.

## 4. Importar pré-voo Web
- [OK] Gere o JSON: `PREFLIGHT_OUT=pf.json D:/emsdk/node/24.19.0_64bit/node.exe tools/web/verify-package.cjs http://127.0.0.1:8080/ 9333`
      (Chrome aberto com `--remote-debugging-port=9333`), ou use `?preflight=1` na página.
- [OK] Clique **Importar pré-voo Web**, escolha o `pf.json`. Esperado: "Pré-voo sem problemas."

## 5. Bloqueio por erro (export preserva o anterior)
- [OK] Adicione ao cubo um controller Python com um módulo inexistente (ou um Sensor/script não suportado),
      salve e clique **Exportar Web**. Esperado: bloqueio com mensagem "Corrija e valide novamente."
      e a pasta `web/` anterior intacta (confira o `manifest.json`).
- [OK] **Localizar** num resultado seleciona o objeto/cena de origem.

Anote o que falhar (texto exato da mensagem) e me passe.

## 6. Abrir no navegador (novo)
- [OK] Sem `web/` exportado, **Abrir no navegador** aparece apagado e o painel explica por quê.
- [OK] Após Exportar Web, o botão libera; clicar abre o navegador padrão com o jogo (clique em **Jogar**).
- [OK] Salve o `.range` de novo sem exportar: o botão apaga com "desatualizado".
- [OK] **Parar servidor** faz a página parar de carregar ao recarregar. Feche o editor: a porta é liberada.
