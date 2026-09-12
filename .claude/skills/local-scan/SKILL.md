---
name: local-scan
description: Delega grunt work (resumir arquivo grande, primeira varredura em C++, boilerplate) ao modelo de código local via Ollama antes de trazer só o essencial para o contexto. Use para arquivos grandes ou buscas repetitivas antes de ler tudo diretamente.
---

# Delegar para o modelo local (Ollama)

Este repo tem um modelo de código local rodando via Ollama (`qwen2.5-coder:14b`), acessível pelo script [tools/ask_local.sh](../../../tools/ask_local.sh). Use-o para tarefas mecânicas antes de gastar seu próprio contexto lendo o arquivo inteiro.

## Quando usar

- Arquivo `.cpp`/`.h` grande e você só precisa saber "o que essa função faz" antes de decidir se vale ler tudo.
- Primeira varredura num arquivo desconhecido do engine (ex: entender um sistema de renderização legado do UPBGE antes de mexer nele).
- Gerar boilerplate repetitivo (getters/setters, structs simples) para depois revisar/ajustar.

## Quando NÃO usar

- Mudanças reais de código, decisões de arquitetura, ou qualquer coisa que vá para o build — isso continua sendo trabalho seu, não do modelo local.
- Arquivos pequenos (já é mais rápido ler direto).

## Uso

```bash
tools/ask_local.sh "resuma o que essa funcao faz" < arquivo.cpp
tools/ask_local.sh "explique este trecho: $(cat arquivo.cpp)"
```

Variáveis de ambiente opcionais: `OLLAMA_MODEL` (padrão `qwen2.5-coder:14b`), `PYTHON_BIN` (padrão aponta para o Python 3.10 real, contornando o stub do Microsoft Store).
