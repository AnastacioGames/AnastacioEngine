---
name: cena-de-teste
description: Monta uma cena .range de teste por script (bpy, -b) e mede com o medidor de trabalho repetido, sem cair nas pegadinhas desta engine (mesh invisível, propriedade que não é de jogo, print sumindo). Use antes de criar qualquer cena de teste ou medir uma correção de desempenho.
---

# Cena de teste no AnastacioEngine

Exemplos prontos: `tools/debug/cenas/criar_cena_luzes_sombra.py` (luzes/sombra) e `tools/debug/cenas/criar_cena_grava_igual.py` (setters, física). Copie o mais parecido em vez de começar do zero.

## Regras ao montar (bpy 2.7x, rodado com `-b --factory-startup`)

- Comece apagando os objetos da cena padrão e definindo `scene.render.engine = 'BLENDER_GAME'`.
- **Todo mesh precisa de material**, senão não aparece no jogo. Um `bpy.data.materials.new()` com `diffuse_color` basta.
- Material com nós Principled exige `scene.game_settings.use_shading_nodes = True`; sem isso o material fica sem shader e nada aparece.
- `obj['x'] = ...` cria propriedade do **editor**, invisível para o jogo (`'x' in obj` dá falso no bge). Para propriedade de jogo use `bpy.ops.object.game_property_new` / `obj.game.properties`, ou identifique os objetos pelo nome (`o.name.startswith(...)`).
- Passe `location=` explícito em todo `primitive_*_add`: sem ele o objeto nasce no cursor 3D.
- Filho: `filho.parent = pai` e `filho.matrix_parent_inverse = pai.matrix_world.inverted()`.
- Câmera: crie, linke e defina `scene.camera`; aponte para o centro com `(-Vector(loc)).to_track_quat('-Z', 'Y').to_euler()`.
- Lógica: `bpy.ops.logic.sensor_add/controller_add/actuator_add(..., object=nome)`, depois `link`. Sensor Always que deve rodar todo frame precisa de `use_pulse_true_level = True`. Controlador Python em modo módulo: texto `nome.py` + `c.mode = 'MODULE'`, `c.module = 'nome.funcao'`.
- "Use Frame Rate" é `scene.game_settings.use_frame_rate` (ligado no RolimaRacer e no template).

## Conferir antes de chamar o usuário

- **O runtime não mostra `print`.** Para saber se um script do jogo rodou, faça ele gravar num arquivo (caminho via variável de ambiente) e leia o arquivo.
- Depois de gerar o `.range`, abra com `-b --python` um script que grave em arquivo: cenas, `scene.camera`, contagem de objetos, materiais por mesh, lógica do objeto controlador.
- Rode e meça você mesmo antes de pedir ao usuário para olhar. Se um contador der 0 onde deveria haver trabalho, a cena está errada, não a engine.

## Medir

```
AnastacioEngine.exe -b cena.range --python tools/debug/auditar_trabalho_repetido.py -- cena_audit.range log.txt
AUDIT_SECONDS=12 AnastacioRuntime.exe cena_audit.range        # fecha sozinho
```

Colunas do log: segundo, objetos, contadores de `KEYS`, `physicsMs`. Descarte os 2-3 primeiros segundos (carregamento, física assentando). Para comparar antes/depois no mesmo executável, use uma chave temporária por variável de ambiente no C++ e remova antes do commit. Rodadas de ~10 s (preferência do usuário).

Jogo do usuário (sem copiar o arquivo): `tools/debug/abrir_engine_log_animacao.bat <jogo.range> --python tools/debug/auditar_trabalho_repetido.py -- - log.txt` com `AUDIT_SECONDS=0`; o usuário joga e fecha sem salvar.

Arquivos temporários (`.range` gerados, logs) vão no scratchpad; só o script gerador vai para `tools/debug/cenas/`.
