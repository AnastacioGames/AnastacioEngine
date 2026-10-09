---
name: cena-de-teste
description: Cria e valida cenas .range de teste da Anastacio Engine usando bpy legado, incluindo reprodução de bugs e medição de performance com os instrumentos existentes do repositório. Use ao montar cenas controladas para esta engine.
---

# Cenas de teste da Anastacio Engine

Trabalhe na raiz do repositório (nesta máquina, `D:/AnastacioEngine`). Leia o `AGENTS.md` vigente; ele é a fonte das regras de build e de validação. Consulte `docs/README.md`, o roadmap e o relatório de melhorias para o recurso testado.

## Escolher a cena

Defina o comportamento reproduzido e a evidência esperada antes de gerar: objetos envolvidos, configuração, ação que dispara o caso e resultado observável. Procure um gerador existente antes de criar outro:

- `tools/debug/cenas/criar_cena_grava_igual.py`: transformações repetidas, hierarquia e corpos físicos.
- `tools/debug/cenas/criar_cena_luzes_sombra.py`: Principled, luzes e sombras.
- `tools/create_camera_fx_scene.py`: câmera, lógica e efeitos.
- Para outros domínios, busque `create_*scene*.py` em `tools/`.

Leia o exemplo pertinente, reutilizando apenas o necessário para reproduzir o caso. Guarde scripts reutilizáveis em `tools/debug/cenas/`; cenas geradas, inspeções e logs em um diretório temporário exclusivo. Não sobrescreva o jogo do usuário. Não modifique C++ para instrumentar uma cena quando os contadores existentes bastarem.

## Construir com a API legada

Execute o gerador com `build/bin/AnastacioEngine.exe -b --factory-startup --python ... -- ...`. Use a API bpy desta engine, derivada do Blender 2.79, não receitas de Blender moderno: `scene.objects.link`, `scene.objects.active`, `obj.select` e `bpy.data.lamps`.

- Remova objetos padrão e configure `scene.render.engine = 'BLENDER_GAME'`.
- Dê material a todo mesh renderizado. Para material simples, `diffuse_color` recebe RGB. Para Principled/nós, habilite `scene.game_settings.use_shading_nodes = True` e conecte o shader ao output.
- Use materiais visualmente contrastantes para o objeto medido, o chão e as referências (cores, brilho ou valores bem diferentes). Não reutilize o mesmo material ou duas cores iguais quando a inspeção depende de distinguir as formas na tela; isso pode fazer uma cena correta parecer vazia.
- Crie iluminação apropriada e inclua sempre um Sun inclinado para a cena ser legível, salvo quando o caso exigir deliberadamente outra iluminação. Crie world se necessário e desligue névoa não intencional com `world.mist_settings.use_mist = False`.
- Passe `location=` nos operadores de criação; não dependa do cursor 3D.
- Crie, linke e atribua `scene.camera`. Nunca estime `rotation_euler` para uma cena de teste: mire explicitamente o centro ou alvo com `(Vector(alvo) - camera.location).to_track_quat('-Z', 'Y').to_euler()`. Uma janela que mostra apenas o world normalmente é câmera apontada para fora da cena, não prova de que os meshes falharam.
- Para enquadrar uma malha inteira, prefira perspectiva (`camera.data.type = 'PERSP'`) com distância focal ampla de `16 mm`, salvo quando o teste exigir outro enquadramento.
- Ao preservar a transformação de um filho, configure `parent` e `matrix_parent_inverse = pai.matrix_world.inverted()` com as matrizes atualizadas.
- `obj['x']` no bpy é propriedade do editor. Para uma propriedade acessível no jogo, ative o objeto e use `bpy.ops.object.game_property_new`, depois `obj.game.properties['x'].value`. Identificação por nome também serve quando adequada.
- Adicione sensores/controladores/atuadores com `bpy.ops.logic.*(..., object=obj.name)` e faça os links. Always recorrente precisa de `use_pulse_true_level = True`. Para módulo Python, crie texto `nome.py`, configure `mode = 'MODULE'` e `module = 'nome.funcao'`; o texto precisa definir essa função com a assinatura esperada, por exemplo `def tick(cont):`. Importar e chamar código no topo do texto não satisfaz o controlador e deixa a cena aberta sem executar o encerramento automático.
- Configure explicitamente física, resolução e `scene.game_settings.use_frame_rate` conforme o caso; não imponha a mesma configuração a todos os testes.
- Receba destinos após `--` em `sys.argv` e salve o `.range` no caminho solicitado. Evite sintaxe Python mais nova que a versão embarcada; verifique-a na engine se necessário.

## Validar a evidência

Após salvar, reabra a cena pelo editor em background e execute uma inspeção bpy que grave em arquivo: cena ativa, câmera, objetos esperados, materiais dos meshes, propriedades e links de lógica pertinentes. Para cada controlador MODULE, confira que o nome do texto, `controller.module` e a função definida no texto concordam. Verifique exit code, existência e conteúdo da inspeção; salvar o arquivo sozinho não demonstra que o teste funciona.

Execute a cena no player de `build/bin/AnastacioRuntime.exe`. Scripts de jogo devem escrever evidências num arquivo em caminho explícito ou recebido por variável de ambiente; não dependa de `print` visível no runtime. Inclua encerramento automático em testes automatizados e confirme que o código realmente rodou. Um contador inesperadamente zero exige conferir a cena e a instrumentação antes de concluir algo sobre a engine.

Para bugs visuais, valide automaticamente dados e logs de shaders, mas peça ao usuário a avaliação no jogo real, conforme `AGENTS.md`. Captura headless/PrintWindow não prova correção visual. Relate separadamente o que passou automaticamente e o que precisa de avaliação visual. Se execução falhar, descreva o erro e não declare a cena validada.

## Medição de trabalho repetido

Leia `tools/debug/auditar_trabalho_repetido.py` antes de usar: ele injeta o medidor nas câmeras e gera uma cópia, mantendo o original. Exemplo PowerShell, substituindo os caminhos por arquivos da sessão:

```powershell
& .\build\bin\AnastacioEngine.exe -b 'D:\temp\teste\cena.range' --python .\tools\debug\auditar_trabalho_repetido.py -- 'D:\temp\teste\cena_audit.range' 'D:\temp\teste\audit.txt'
$auditSecondsAnterior = $env:AUDIT_SECONDS
try {
    $env:AUDIT_SECONDS = '10'
    & .\build\bin\AnastacioRuntime.exe 'D:\temp\teste\cena_audit.range'
} finally {
    $env:AUDIT_SECONDS = $auditSecondsAnterior
}
```

Crie o diretório de saída antes de executar e use um log novo em cada rodada: o medidor acrescenta linhas. Confira o cabeçalho, amostras e marcador `# fim`. Ele registra objetos, médias dos contadores por frame e `physicsMs`. Descarte os primeiros 2–3 segundos e compare condições equivalentes. Contadores de trabalho não substituem FPS/tempo de frame para afirmar ganho de desempenho.

Para medir o jogo original sem salvar, o medidor aceita saída `-` no editor com janela e `AUDIT_SECONDS=0`; use esse modo apenas quando o usuário solicitar essa interação. Nunca salve instrumentação sobre o projeto original.

Ao entregar, informe o gerador e a cena, comando para abrir, resultado esperado, evidência de execução e eventuais validações visuais pendentes. Compilar só é necessário quando houver mudanças no código da engine; nesse caso siga integralmente o ambiente e o limite de tentativas do `AGENTS.md`.
