# Web — empacotamento e hospedagem

Estado em 2026-09-20: empacotador, verificador e integração ao editor (Exportar Web) implementados; deploy no GitHub Pages
aceito em Chrome, Edge, Firefox e celular. Fluxo do editor (Validar, Exportar e Abrir no navegador) aceito pelo
usuário em 2026-09-20 (ver [web-profile-validation-plan.md](web-profile-validation-plan.md)). O runtime tem preset de release (`web-runtime-release`).

## Pré-voo no navegador

Abrir o pacote com `?preflight=1` mostra e expõe (`window.rangePreflight()`) o relatório `range-web-preflight` v1:
isolamento de origem, WebGL, status/MIME/SHA-256 de cada arquivo contra o `manifest.json`, perda de contexto e
erros de shader/Python extraídos do log. `PREFLIGHT_OUT=pf.json node tools/web/verify-package.cjs <url>` grava o
relatório; `range_web.preflight.check_preflight` o converte em resultados. A extração de shader/Python é heurística.

## Gerar o pacote

Pré-requisito: `RangeRuntime.{js,wasm,data}` gerados (a partir de `source/`, com o emsdk ativo) por
`cmake --preset web-runtime-release && cmake --build --preset web-runtime-release` (saída em `build-web-release/bin`,
use `--runtime-dir build-web-release/bin`) ou, para depuração, pelo preset `web-runtime` (`build-web/bin`).

```
python tools/web/package-web.py --game caminho/jogo.range --name meu-jogo --version 0.1.0 --zip
```

- Nome do `.range` com espaço, acento ou caractere inválido é ajustado sozinho para o FS virtual (`Meu Jogo Ação.range`
  → `Meu_Jogo_Acao.range`; nome só com caracteres não ASCII vira `game.range`). O arquivo original não é alterado.
- `--extra arquivo.py` (repetível) coloca módulos ao lado do `.range` no FS virtual `/` (mesmo diretório
  do jogo, que entra no `sys.path`). Dependências dinâmicas não são descobertas: declare-as.
- Saída em `build-web/dist/<name>/` (troca o pacote anterior só depois de o novo estar completo) e, com `--zip`,
  `<name>-<version>-web.zip` + `.sha256`.
- O pacote contém `index.html` (página de produção), `RangeRuntime.*`, `game/`, `manifest.json` (hashes,
  requisitos, avisos), `SHA256SUMS.txt`, `serve.py` e `HOSTING.md`.

## Testar localmente

**No editor (recomendado):** em Properties > Scene > Web (Range), **Abrir no navegador** sobe um servidor local numa
porta livre e abre o jogo no navegador padrão (clique em **Jogar**). O botão só fica ativo com o pacote exportado e
atualizado em relação ao `.range` salvo; caso contrário o painel mostra o motivo. **Parar servidor** encerra
(o servidor também morre com o editor). A opção **Abrir após exportar** faz isso ao fim do Exportar Web.
**Testar pacote no navegador** (pré-voo) também só libera com pacote e Chrome/Edge disponíveis.

Na linha de comando:

```
cd build-web/dist/meu-jogo && python serve.py 8080
```

Abra http://localhost:8080/, espere o botão **Jogar** e clique (dá foco ao canvas). `?debug=1` mostra o log do runtime.

Verificação automatizada (só logs/estado, **não** julga o visual): com um Chrome aberto com
`--remote-debugging-port=9333`, rode `node tools/web/verify-package.cjs http://127.0.0.1:8080/ 9333`.
Sai com 0 se o botão liberar, sem erro visível, aborto ou exceção.
Se `node` não estiver no PATH, use o do emsdk (ex.: `D:/emsdk/node/24.19.0_64bit/node.exe`).
`node tools/web/verify-persistence.cjs <url> 9333` testa a persistência: grava um token em `/saves`, faz `syncfs`, recarrega
e confere que o arquivo voltou do IndexedDB (usa `Module.FS`, exposto pelo pre-js). Cobre a camada IDBFS.
`node tools/web/verify-save.cjs <url> 9333` testa `saveGlobalDict`/`loadGlobalDict` de ponta a ponta num pacote gerado de
`tools/create_web_save_scene.py` (`RangeEngine -b --python ...`): grava numa sessão, recarrega e confere a leitura. Não use `--virtual-time-budget` com
`--dump-dom`: trava o `syncfs` do IndexedDB e o runtime fica esperando `idbfs-initial-sync`.

## Requisitos de hospedagem

- Servidor estático com `.wasm` como `application/wasm`; habilitar gzip/brotli em `.wasm`/`.js`/`.data`.
- Compressão medida (gzip nível 6): `.wasm` 20,3 → 8,0 MiB, `.data` 24,8 → 8,4 MiB, `.js` 0,9 → 0,2 MiB; o download
  cai de ~46 para ~17 MiB. Receitas por host (Netlify, GitHub Pages, itch.io, nginx, Apache) e o `curl -sI` de conferência
  estão no `HOSTING.md` gerado em cada pacote.
- **COOP/COEP não são necessários**: o preset atual não usa pthreads (o `TaskScheduler` loga
  "failed to launch thread" e segue serial).
- Piso gráfico: WebGL 2 (o preset fixa `MIN/MAX_WEBGL_VERSION=2`).
- Saves ficam no IndexedDB, por origem; trocar de domínio ou limpar dados do site apaga o save.
- Ao publicar nova versão, mude `--version`: os arquivos são pedidos com `?v=<versao>`.

## Limitações conhecidas do pacote atual

- O `.data` do runtime embute a stdlib do Python e `release/scripts`; o jogo vem de `game/`. O preload `untitled.range` (TEMP) foi removido.
- Release (`-O2`, sem `SAFE_HEAP`/`ASSERTIONS`): `.wasm` 19,9 MB (debug 25,4 MB), `.js` 0,9 MB (debug 2,1 MB); pacote ~44,8 MiB
  (zip 16,3 MB). O `.data` (~25 MB) domina e ainda é candidato a enxugar.
- Áudio: Audaspace + SDL2 (Web Audio), WAV, MP3 e OGG (dr_mp3 e stb_vorbis, domínio público; sem efeitos OpenAL, módulo Python `aud` sem numpy (`Sound.data()`/`buffer()` indisponíveis); erros de `aud` como arquivo inexistente/corrompido viram exceção Python e não derrubam o jogo); o navegador só libera o som após um gesto do usuário (botão Jogar). Toque vira clique de mouse (emulação do SDL); não há API multitouch.
- Aceite manual do usuário (2026-09-18): entrada, filtros 2D, gamepad e save (`SAVED`/`LOADED` após recarregar) OK. Persistência IDBFS verificada.
