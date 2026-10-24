---
name: local-knowledge
description: Consulta os índices de código por área em docs/local-knowledge/index-*.md e os mapas docs/code-map-*.md antes de explorar código desconhecido do zero. Use no início de tarefas que mexem numa área ainda não mapeada na conversa.
---

# Índices de código por área

`docs/local-knowledge/index-<área>.md` lista cada arquivo da área com número de linhas e classes.
É gerado por regex (`tools/build_code_index.py`), sem LLM. Áreas: `rendering`, `physics`,
`logic-scripting`, `scenegraph-converter`, `dna-blend`.

## Como usar

1. Abra o índice da área para achar o arquivo certo e ver o tamanho.
2. Arquivo marcado **grande**: não leia inteiro. Veja o `docs/code-map-*.md` dele, se existir.
3. Visão geral das pastas: `docs/architecture.md`.

O índice só diz onde está e quanto mede. Para entender o código, leia o arquivo.

## Regenerar

Depois de dividir, criar ou apagar arquivos:

```bash
python tools/build_code_index.py
```

Os antigos resumos em prosa (`<área>.md`, gerados por Ollama) foram apagados em 2026-10-24:
cobriam só 25 arquivos pequenos por área e tinham erros.
