# Glossário i18n (pt_BR, es, ru)

Termos fixos para `translations_ui.py`, `translations_labels.py` e `translations_c.py` (revisão de 2026-10-04). Nomes próprios,
códigos, atalhos, identificadores, nomes de ícones e placeholders (`%s`, `%d`) não se traduzem.

| Inglês | pt_BR | es | ru |
|---|---|---|---|
| Object | objeto | objeto | объект |
| Mesh | malha | malla | сетка (não "меш") |
| Scene | cena | escena | сцена |
| Property | propriedade | propiedad | свойство |
| Sensor | sensor | sensor | сенсор |
| Actuator | atuador | actuador | актуатор |
| Controller (lógica) | controlador | controlador | контроллер |
| Driver (animação) | driver | controlador | драйвер |
| Frame | quadro | fotograma | кадр |
| Handle (curva) | alça | manejador (não "manija") | рукоятка |
| Bone | osso | hueso | кость |
| Armature | armature | armature | арматура |
| Layer | camada | capa | слой |
| Shadow | sombra | sombra | тень |
| Constraint | restrição | restricción | ограничение |
| Bake | bake / fazer bake | hornear | запечь |
| Component | componente | componente | компонент |
| Game | jogo | juego | игра |
| Cutscene | Cutscene | Escena cinemática | Катсцена |
| Lens flare | Lens flare | Lens flare | Блик объектива |
| Bloom | Bloom | Bloom | Свечение |
| Guide | Guia | Guía | Направляющая |
| Parallax | Paralaxe | Paralaje | Параллакс |
| Random Walk | Passeio aleatório | Paseo aleatorio | Случайное блуждание |

Mantidos em inglês de propósito (termo técnico de uso corrente): Culling, Hinting, Mipmapping, Billboard, Shader, Draw call,
Skinning, Pool, Buffer, Tick, FXAA, HDR, Vsync, nomes de algoritmos (Burley, PCF, MLCP, Lerp, Arctan2, Filmic).

## Dúvidas registradas (sem resposta nativa)

- ru: "Sensor/Actuator" como сенсор/актуатор (Blender oficial usa "датчик"/"актуатор"); mantido сенсор por já estar em toda a UI.
- ru: "Hinting" saiu como "Хинтинг" (transliteração); avaliar "Хинтинг шрифта".
- ru: "Bloom" virou "Свечение" em `translations_ui.py` para igualar `translations_labels.py`.
- es: "Cutscene" como "Escena cinemática" (ui); labels usa o mesmo conceito, conferir o uso na janela.
- pt_BR: "Cutscene", "Culling" e "Tags" — "Tags" virou "Etiquetas"; "Cutscene"/"Culling" ficaram sem tradução (jargão de jogos).
- es: "Dynamic Mesh" etc. seguem "malla"; "Hornear" (bake) é a escolha do catálogo Blender es; "Armature" ficou sem tradução por coerência com pt.
- Duas revisões automáticas (sem falante nativo): es e ru continuam pedindo revisão nativa.

## Lacunas por idioma

Não há binário do Blender neste ambiente (Linux de nuvem), então `i18n_audit.py`, `i18n_scan_labels.py` e `i18n_scan_c.py` não foram
rodados. A medição abaixo é estática: entradas das três tabelas cuja tradução é igual ao inglês (com letras). Quase todas são
nomes, códigos ou termos iguais; as lacunas reais de texto de interface eram as listadas na tabela acima.

| Idioma | Lacunas antes (iguais ao inglês) | Texto real fechado | Restam |
|---|---|---|---|
| pt_BR | 137 | 5 (Tags, Guide, Parallax, Random Walk, Picture-in-Picture) | 132 (nomes, códigos, termos iguais) |
| es | 119 | 4 (Guide, Parallax, Random Walk, Cutscene) | 115 (idem) |
| ru | 43 | 5 (Guide, Parallax, Random Walk, Bloom, Lens flare) | 39 (nomes, códigos, siglas) |

Também foram corrigidos 74 textos de es/ru (hornear/bake, armature, concordância, "меш" → "сетка", "manijas" → "manejadores",
"Translate:" ru, "Re-Key Shape Points" ru etc.).

Lacunas do catálogo do Blender 2.79 só medidas em runtime (último valor, 2026-09-24 no roadmap): pt_BR ~455, es ~511, ru ~1 124.
**Não foram remedidas**; rodar `RangeEngine -b --python tools/tests/web_profile/i18n_audit.py -- <idioma>` no Windows/Linux com o editor.
