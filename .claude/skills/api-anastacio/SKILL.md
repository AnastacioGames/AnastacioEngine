---
name: api-anastacio
description: Consulta a referência da API Python da Anastacio Engine (Range.logic, KX_GameObject, componentes, etc.) por páginas pequenas antes de escrever ou revisar scripts de jogo. Use ao programar scripts/componentes Python para a engine, ao responder "essa função existe?" ou ao adicionar atributo/método Python novo.
---

# API Python da Anastacio Engine

A engine é nova: nenhum modelo foi treinado com ela, então **não escreva nomes de memória**. Funções vêm do `bge` do UPBGE/Range, mas a Anastacio mudou e acrescentou itens. Se um nome não aparece na referência, ele não existe.

A referência completa tem ~450 KB. **Não carregue o arquivo inteiro.** Use a versão fatiada.

## Onde consultar (nesta ordem)

1. **Ferramentas MCP `anastacio-api`**, se estiverem disponíveis (`api_guia`, `api_indice`, `api_buscar`, `api_pagina`, `api_item`). *Ainda não verificado num Claude Code real* (só testado com um cliente de teste): se uma chamada falhar ou os nomes das ferramentas forem outros, passe para o próximo item.
2. **Versão fatiada publicada**: `https://anastaciogames.github.io/anastacio-docs/api-ia/pt/` com `INDEX.md`, `GUIA.md`, `busca.json` e `paginas/<Classe>.md`. Busque com WebFetch (ou curl).
3. **Repositório `anastacio-docs`**, se estiver clonado: `site/public/api-ia/pt/`.
4. **Sem doc acessível**: leia os bindings no C++ (`source/source/gameengine/**/*.cpp`, tabelas `PyMethodDef X::Methods[]` e `PyAttributeDef X::Attributes[]`) e diga ao usuário que não conferiu na referência.

## Roteiro

1. Leia o `GUIA` uma vez por sessão (regras e armadilhas: `Range` com R maiúsculo, `SystemError` em objeto removido, script contra componente, tempo independente do FPS).
2. Procure cada nome que vai usar (`api_buscar` ou `busca.json`). Só use o que aparecer.
3. Abra a página da classe só para o que precisa. Páginas grandes (`KX_GameObject`, `Range.logic`, `Range.texture`) têm partes `--props`, `--funcs`, `--consts`.
4. Itens marcados *(novo na Anastacio)* ou *(alterado na Anastacio)* não existiam no UPBGE: leia a descrição, não suponha o comportamento.
5. Só diga que um nome "não existe" depois de conferir na referência **ou**, se ela estiver inacessível, nos bindings do C++ (item 4 acima). Sem nenhuma das duas conferências, diga que não conseguiu verificar e não rejeite o nome. Se confirmado que não existe, proponha a alternativa que existe e não crie um nome parecido.

## Instalar o MCP (uma vez por máquina)

O servidor fica no repo `anastacio-docs` (`tools/anastacio_api_mcp.py`, só biblioteca padrão):

```
claude mcp add anastacio-api -- python <caminho>/anastacio-docs/tools/anastacio_api_mcp.py --lang pt
```

Para ler a doc publicada em vez da pasta local, acrescente `--fonte https://anastaciogames.github.io/anastacio-docs/api-ia/pt/`.

## Se você está adicionando ou mudando a API Python da engine

A regra "cascata de propriedade nova" do `AGENTS.md` continua valendo: **neste repo, rode `python tools/check_cascata.py` antes do commit** (ele não regenera a doc externa). A regeneração abaixo é um passo separado, no repo `anastacio-docs`, para a IA não ficar com a referência desatualizada:

```
python tools/api_inventario.py --engine <caminho da engine>
python tools/gerar_paginas.py --engine <caminho da engine>
python tools/gerar_md_unico.py
python tools/gerar_api_ia.py
```

Escreva a descrição do item novo na docstring do C++ (4º campo do `PyMethodDef`) ou em `conteudo/descricoes.json` do `anastacio-docs`. Item sem frase de descrição aparece em `inventario/sem_descricao.md` e a IA acerta menos nele.
