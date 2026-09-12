---
name: local-knowledge
description: Consulta os resumos por area do engine em docs/local-knowledge/ (gerados pelo modelo local via Ollama) antes de explorar codigo desconhecido do zero. Use no inicio de tarefas que mexem numa area ainda nao mapeada na conversa.
---

# Conhecimento local pre-gerado por area

`docs/local-knowledge/*.md` contém resumos gerados pelo modelo local (Ollama, `qwen2.5-coder:14b`) sobre o papel de cada arquivo em áreas do engine:

- `rendering.md` — Rasterizer + GPU
- `physics.md` — Physics (gameengine) + physics (blender)
- `logic-scripting.md` — GameLogic, Expressions, Python API
- `scenegraph-converter.md` — SceneGraph, Converter, Ketsji
- `dna-blend.md` — makesdna, blenloader

## Como usar

Antes de fazer uma primeira varredura manual num arquivo `.cpp`/`.h` de uma dessas áreas, olhe primeiro o `.md` correspondente — pode já ter um resumo de 3-5 linhas do papel do arquivo, evitando ler o arquivo inteiro sem necessidade.

**Isso é só um ponto de partida raso** (gerado por um modelo pequeno, sem julgamento de arquitetura). Para qualquer mudança real de código, decisão de design, ou dúvida onde o resumo pareça incompleto/genérico, leia o arquivo de verdade — não confie no resumo como fonte final.

## Regenerar

Se o resumo estiver desatualizado ou faltando um arquivo novo:

```bash
tools/build_local_knowledge.sh <area>   # regenera uma area especifica
tools/build_local_knowledge.sh          # regenera todas
```

Isso reprocessa até `MAX_FILES_PER_AREA` arquivos (padrão 25) por área via [tools/ask_local.sh](../../../tools/ask_local.sh) — pode levar minutos, não é instantâneo.
