# Testes manuais do perfil Web

Só o que precisa de janela ou navegador. O resto roda em `tools/tests/web_profile/`.

## Preparação

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/make_manual_project.py

Gera `build/web-manual/` com `bom.blend` (controller em `meu_mod.main`, que importa `pkg.util`)
e `ruim.blend` (módulo inexistente).

## A. Painel no editor (RangeEngine.exe com janela)

1. Abra `build/web-manual/bom.blend`. Propriedades > Cena > painel **Web (Range)**.
2. Clique **Validar Web**. Esperado: resumo sem erros ("Nenhuma incompatibilidade").
3. Clique **Exportar Web**. Esperado: mensagem "Pacote Web gerado em ...", pasta `build/web-manual/web/`
   com `game/meu_mod.py` e `game/pkg/util.py`.
4. Abra `ruim.blend`, clique **Validar Web**. Esperado: erro WEB-PKG-003 com botão **Localizar**.
5. Clique **Localizar**. Esperado: o objeto Porta fica selecionado.
6. Clique **Exportar Web**. Esperado: bloqueado, e `build/web-manual/web/` do passo 3 continua intacta
   (se o destino do `ruim.blend` for o mesmo `//web/`, confira que os arquivos antigos seguem lá).
7. Edite `bom.blend` sem salvar e clique **Exportar Web**. Esperado: pede para salvar.

## C. Análise de submódulo (`from pkg import util`)

1. Abra `build/web-manual/sub.blend` (controller em `sub_mod.main`, que faz `from sub_pkg import perigo`;
   `sub_pkg/perigo.py` chama `subprocess.run` em nível de módulo; dentro de função seria só aviso).
2. Clique **Validar Web**. Esperado: erro **WEB-PY-002** apontando para `sub_pkg/perigo.py`
   (antes da correção passava sem erro).
3. Clique **Exportar Web**. Esperado: bloqueado.

## B. Pacote no navegador

    cd build/web-manual/web
    python serve.py 8080

Abra http://localhost:8080/ (Chrome ou Edge).

1. O jogo carrega sem erro no console (F12).
2. No console não deve haver 404 para `game/meu_mod.py` nem `game/pkg/util.py`.
3. Confirma a criação de subpastas: no console rode
   `FS.readdir('/pkg')` (ou `Module.FS.readdir('/pkg')`). Esperado: `util.py` na lista.
   Isso valida o `FS_createPath` do `index.html`, que nunca foi executado.
4. Anote o que falhar (mensagem do console) e me passe.

## D. Pré-voo importado no editor

Arquivos de exemplo em `build/web-manual/preflight/` (gerados a mão; o `make_manual_project.py` não os recria):
`pf-limpo.json`, `pf-problemas.json`, `pf-invalido.json`. Use `bom.blend` no painel **Web (Range)**.

1. Clique **Importar pré-voo Web** e escolha `pf-limpo.json`. Esperado: mensagem "Pré-voo sem problemas.".
2. Importe `pf-problemas.json`. Esperado: mensagem "Pré-voo: 3 problema(s).", e no painel **WEB-GFX-002**,
   **WEB-PY-001** (numpy) e **WEB-PY-009** (ValueError). Só o WEB-PY-* mostra origem em `meu_mod.py`.
3. Clique **Validar Web**. Esperado: os 3 resultados do pré-voo continuam na lista, junto do resumo novo.
4. Importe `pf-limpo.json` de novo. Esperado: os 3 resultados de pré-voo somem (substitui, não acumula).
5. Importe `pf-invalido.json`. Esperado: um único **WEB-DEPLOY-002** ("Não foi possível ler...").
6. Importe `pf-problemas.json` duas vezes seguidas. Esperado: continuam 3 resultados, sem duplicar.
7. Com resultados de pré-voo na lista, clique **Exportar Web**. Esperado: o export segue a validação normal
   (o pré-voo não bloqueia) e a lista passa a mostrar só a revalidação, sem os resultados de pré-voo.
8. Real: sirva `build/web-manual/web`, abra `http://localhost:8080/?preflight=1`, chame `rangePreflight()` no console,
   salve o JSON e importe. Esperado: sem problemas num pacote saudável.
