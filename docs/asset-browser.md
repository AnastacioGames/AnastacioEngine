# Asset Browser

O Asset Browser não é um editor novo. Como no Blender, ele é um modo de navegação do File Browser
(`SpaceFile.browse_mode`: `FILES` ou `ASSETS`). Os assets são os Objects, Groups e Materials guardados
em arquivos `.blend` de uma pasta de biblioteca.

## Uso

### Abrir

- Menu de tipo de editor de qualquer área > **Asset Browser**.
- **Window > Asset Browser** abre uma janela flutuante. Ela usa a mesma janela temporária das Preferências e do Drivers.
- Em Python: `space.browse_mode = 'ASSETS'` num File Browser sem diálogo aberto.

### Bibliotecas

- Na aba **Assets**, no painel **Asset Libraries**, navegue até uma pasta e clique em **+**. A pasta vira uma biblioteca e é aberta.
- Se você estiver dentro de um `.blend`, a biblioteca registrada é a pasta que contém esse arquivo.
- **−** remove a biblioteca ativa. A pasta em disco não é tocada.
- As bibliotecas ficam salvas na seção `[AssetLibraries]` do `bookmarks.txt` do usuário, junto com os favoritos.

### Adicionar à cena

- **Arrastar para a Vista 3D:**
  - um objeto ou grupo entra no ponto onde foi solto;
  - um material vai para o objeto sob o cursor, ou para o objeto ativo se não houver nenhum sob o cursor.
- **Duplo clique:** adiciona o asset no cursor 3D.
- **Append/Link (botão no header):**
  - vale para Groups e Materials;
  - Objects são sempre append (o 2.79 não instancia objeto linkado);
  - Ctrl ao soltar força link.
- Não é possível arrastar assets do próprio arquivo aberto.

### Miniaturas

O botão **Generate Previews**, no painel Asset Libraries, gera as miniaturas de todos os `.blend` da pasta:

- não abre diálogo e não cria backup `.blend1`;
- pula o arquivo aberto no editor;
- por baixo, roda `wm.previews_batch_generate` em processos em segundo plano.

### Limitações

- Ao dar append num objeto filho, o pai não vem junto: `expand_object` do 2.79 não expande `ob->parent`. Use um Group.
- No modo Assets, os operadores de pasta nova, renomear e apagar ficam bloqueados.

## Implementação

| Parte | Onde |
|---|---|
| Campo `browse_mode` e enum `eFileBrowse_Mode` | `makesdna/DNA_space_types.h` |
| Parâmetros do modo, troca de modo, biblioteca ativa | `editors/space_file/filesel.c` |
| Recriar a lista e sincronizar regiões no refresh | `editors/space_file/space_file.c` (`file_refresh`) |
| Categoria `FS_CATEGORY_ASSET_LIBRARIES` e `[AssetLibraries]` | `editors/space_file/fsmenu.c` |
| `file.asset_library_add/remove`, `file.asset_add` | `editors/space_file/file_ops.c` |
| Drop na Vista 3D (`VIEW3D_OT_asset_drop`) | `editors/space_view3d/view3d_ops.c`, `space_view3d.c` |
| Entrada no menu de tipo de editor (subtipo) | `editors/screen/area.c` |
| Janela flutuante (`SCREEN_OT_asset_browser_show`, `WM_WINDOW_ASSETS`) | `editors/screen/screen_ops.c`, `windowmanager/intern/wm_window.c` |
| RNA: `browse_mode`, `asset_libraries(_active)`, `params.use_link` | `makesrna/intern/rna_space.c` |
| Header, painéis e `file.asset_previews_generate` | `bl_ui/space_filebrowser.py`, `bl_operators/file.py` |

Regras do modo Assets. `ED_fileselect_browse_mode_params_ensure` as reaplica a cada refresh:

- lista `FILE_LOADLIB` com recursão 1 (vista plana);
- filtro de pastas, `.blend` e ID, com `filter_id` restrito a OB, GR e MA;
- miniaturas.

Um diálogo de arquivo (`sfile->op`) sempre tem prioridade: com um operador aberto, a área se comporta como File Browser normal.
