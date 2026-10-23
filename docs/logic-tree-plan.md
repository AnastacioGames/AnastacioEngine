# Logic Tree: lógica de jogo por nós

Estado: **plano v1 (2026-10-23)**. Nada implementado. Branch prevista: `feat/logic-tree`.

## 1. Objetivo e meta de sensação

Criar uma árvore de nós de lógica, a **Logic Tree**, como **complemento** aos Logic Bricks. Os bricks continuam
existindo e sendo mantidos (decisão do usuário, 2026-10-23).

O alvo é ter a **praticidade dos bricks com mais liberdade**. O risco principal não é técnico. É o editor ficar
difícil e ninguém usar, como aconteceu com o VisualScript do Godot, removido na versão 4.

**Teste de aceite da sensação.** Fazer "quando apertar Espaço, pular" precisa levar o mesmo tempo que leva nos
bricks, uns 15 segundos: arrastar um gatilho Tecla, puxar o fio, escolher a ação Movimento, preencher um campo e
apertar P. Se a fatia 1 não passar nesse teste com o usuário, ela falhou, por mais recursos que tenha.

## 2. Por que os bricks são fáceis (e o que não podemos perder)

| Qualidade dos bricks | Como a Logic Tree preserva |
|---|---|
| Vocabulário fechado: escolhe-se de uma lista, sem tela em branco | Menu Add por família, busca, sugestão de nó ao soltar um fio no vazio (já existe) |
| Modelo de uma frase: **quando** isto, **faça** aquilo | Três famílias de nós: Gatilhos, Lógica, Ações. Fio de evento como ligação principal |
| Nenhuma fiação de dados | Valor é **campo dentro do nó** (nó "gordo"). Não existe pino de dado na fatia 1 |
| Imediato: adicionou e funciona | Compila sozinho ao apertar P e ao salvar, como o Bake automático da UI Tree |

Os dois problemas que derrubam editores de nós são a **tela em branco** e o **espaguete de dados**. Toda liberdade
nova precisa vir sem reintroduzir nenhum dos dois.

## 3. O que já existe e será reaproveitado

| Peça | Onde | Uso na Logic Tree |
|---|---|---|
| Árvore de nós própria em Python, sockets de evento, nós de ação | `range_ui_tree.py` (UI Tree) | Mesmo padrão de `NodeTree`, `NodeSocket` e categorias |
| Bake automático no Play e ao salvar | `range_ui_tree.py:696` (`game_pre`/`save_pre`) | Mesmo gancho para compilar a árvore |
| Busca no popover Add, filtro de compatibilidade, sugestão ao soltar fio no vazio, abas de categoria, troca de tipo de árvore com nome | commits `b38447e`, `45e9286`, `75b0d0a`, `07135d6`, `b52451f`, `e96723b` | Genéricos: valem para qualquer árvore em Python, sem trabalho novo |
| Criação de bricks em grupo: `sensor`, `actuator`, `link`, `then`, `property`, `state_name` | `logic_presets.py:29` (classe `_Bricks`) | Base do compilador |
| Sequência "Então" (sensor Actuator no modo Concluído + And), Esperar, motivo de encerramento | Logic Bricks 2.0, [plano](bricks-2.0-plano.md) seções 8 e 11; `logic_presets.py:74`; `logic_window.c:1619` | O socket **Then** do nó compila para isso |
| Estados com nome, grupos de bricks | Logic Bricks 2.0, F1a e F1b | Frames de estado e marcação dos bricks gerados |
| Janela Logic Bricks no Debug Mode (histórico, pausa no disparo) | Logic Bricks 2.0, F4 e F5 | Depuração sem trabalho novo, desde que os bricks tenham os nomes dos nós |
| Conversor Logic Bricks → Python | `logic_to_python.py:2674` (`convert_object`) | Árvore → bricks → Python Component, de graça |
| Expressões nativas com `AND`, `OR`, `NOT`, `IF`, aritmética e comparação | `InputParser.cpp:338` | Uma árvore de portas lógicas vira um único controller Expression |
| Propriedade Python que aponta para um ID | `bpy_props.c:3236` | `Object.logic_tree` sem mexer em DNA |

## 4. Decisão de arquitetura: compilar para Logic Bricks nativos

A árvore é uma **nova forma de escrever** a lógica nativa, não um runtime novo. Ao apertar P ou salvar, cada
objeto que usa uma Logic Tree recebe os bricks equivalentes num grupo próprio. No jogo não existe nada novo.

| Opção | Desempenho | Web/Android | Depuração | Liberdade | Custo e risco |
|---|---|---|---|---|---|
| **A. Compilar para bricks (proposta)** | Nativo, C++ | Sem trabalho | Janela F4/F5 já pronta | Tudo que os bricks expressam, com a montagem mais livre (seção 5) | Baixo: só Python no editor |
| B. Gerar um Python Component pelo conversor | Python por objeto por quadro | Funciona, mais lento no celular | Perde a janela de bricks | Maior, com dados e contas | Médio. O conversor lê bricks reais, então precisaria de adaptador |
| C. Interpretar a árvore em runtime Python, como a UI Tree | Pior das opções | Funciona | Nenhuma | Maior | Médio, e cria um runtime paralelo para manter |
| D. Runtime de grafo novo em C++ | Nativo | Exige trabalho | Nova | Total | Alto: DNA, conversão e versioning novos |

Motivos da escolha:
- Segue os princípios do Logic Bricks 2.0 (nativo, mantém sensor → controller → actuator, convertível).
- Herda de graça Web/Android, a janela de depuração, o "To Python" e o `.cooked` (que não guarda lógica).
- Risco de runtime zero na fatia 1: se os bricks gerados estiverem certos, o jogo está certo.
- A opção D continua possível no futuro se os bricks virarem o teto. A árvore salva no arquivo seria a mesma.

Referência externa: a UPBGE (ancestral deste fork) teve um editor de Logic Nodes ao lado dos bricks, que gerava
Python. A opção A troca esse custo de Python por bricks nativos.

## 5. Onde está a liberdade maior

O que a Logic Tree permite e os bricks não:

1. **Portas lógicas compostas.** `(W ou Seta) e não Pausado` em qualquer profundidade. Nos bricks não existe
   controller → controller. O compilador dobra a árvore de portas num controller Expression.
2. **Sequências desenhadas como fio.** Saída **Then** em Esperar, Action, Sound, Steering e Vídeo, encadeando
   "faça A, depois B, depois C". O plano dos bricks 2.0 registrou que um fio da 3ª coluna até a 1ª exigiria um
   tipo novo de link. No grafo ele é natural.
3. **Estados visíveis como máquina de estados.** Um Frame marcado como Estado, como a Screen da UI Tree. Os nós
   dentro dele valem naquele estado, e a ação "Ir para Estado" troca o estado.
4. **Uma árvore, vários objetos.** A Logic Tree é um datablock. Dez inimigos usam a mesma árvore, e editar uma vez
   vale para todos. Nos bricks, isso exige copiar e colar entre objetos.
5. **Leitura de projetos grandes.** O RolimaRacer tem 324 controllers em 42 arquivos. Em colunas fica ilegível.
   Em grafo dá para organizar por Frames.
6. **Receitas editáveis.** Os presets dos bricks viram blocos de nós que o usuário vê e modifica.
7. **Saída para Python, sem pinos.** Nó "Rodar Python" (`modulo.funcao`), compilado para um controller Python em
   modo Module.

O que fica de fora na fatia 1, de propósito: pinos de dado, variáveis locais, laços e funções. Expressões nos
campos cobrem a maior parte dos casos: o valor do actuator Property e o controller Expression já aceitam
expressões. Pinos de dado só entram se um caso real mostrar que a expressão não basta (F6).

## 6. Experiência no editor

- **Criar:** no painel Game do objeto (e no cabeçalho do Logic Editor), um campo **Logic Tree** com botão New. O
  Node Editor abre já nessa árvore.
- **Árvore nova não começa vazia:** vem com uma nota curta ("arraste um gatilho ou use Add > Receitas"). O menu
  Add tem as famílias **Gatilhos**, **Lógica**, **Ações** e **Receitas**.
- **Nó gordo:** os campos principais ficam no próprio nó, como no Button da UI Tree. Os avançados ficam no painel
  lateral (N).
- **Padrões que já funcionam:** os pulsos (True Level, Tap) seguem o padrão de cada sensor nos bricks. A opção
  existe, mas não precisa ser mexida para o caso comum.
- **Erros no próprio nó:** campo obrigatório vazio ou alvo inexistente pintam o nó e mostram a mensagem. A saída
  Then só existe nos nós que concluem, então o erro "esse actuator nunca conclui" não acontece.
- **Bricks gerados no Logic Editor:** aparecem num grupo recolhido `Tree: <nome da árvore>`, com aviso de que são
  gerados. Editar lá é perdido na próxima compilação. Quem quiser "ejetar" para bricks pode desligar a árvore do
  objeto e os bricks ficam.

## 7. Contrato da compilação

| Nó | Vira |
|---|---|
| Gatilho (Tecla, Mouse, Colisão, Propriedade, Mensagem, Sempre...) | Um sensor do mesmo tipo, com os campos do nó |
| Porta And/Or/Not entre gatilhos | Um controller Expression com a expressão equivalente. Um único gatilho ligado direto numa ação gera um And |
| Ação (Movimento, Propriedade, Som, Action, Esperar...) | Um actuator do mesmo tipo, ligado ao controller da cadeia |
| Saída Then de uma ação | Sensor Actuator no modo Concluído apontando para o actuator, como o botão "Então" faz hoje |
| Frame de Estado | Os controllers dos nós dentro do Frame recebem o bit daquele estado. O nome do Frame vai para `state_names` |
| Rodar Python | Controller Python em modo Module |

Regras:
- **Quando compila:** em `game_pre` e `save_pre` (o export salva), em todos os objetos com `logic_tree`, e pelo
  botão Compile no painel. A mesma árvore em dez objetos compila dez vezes. É barato: são operações de RNA.
- **Regeneração exata:** o objeto guarda a lista dos bricks que a árvore gerou (propriedade ID). Recompilar apaga
  só esses e cria de novo. Bricks do usuário no mesmo objeto nunca são tocados.
- **Nomes:** o brick recebe o rótulo do nó, com prefixo curto quando preciso para não colidir. Assim a janela de
  depuração mostra nomes que o usuário reconhece.
- **Ordem:** controllers em ordem topológica da árvore. A ordem real de execução continua sendo a das listas,
  como nos bricks.
- **Objeto ligado de biblioteca (linked):** não compila, com aviso. Os bricks dele não podem ser alterados.
- **Alvo:** na fatia 1, tudo age sobre o próprio objeto (Self). Campos de objeto-alvo seguem o que cada actuator
  já aceita.

## 8. Fatias

| Fase | Conteúdo | Risco | C++? |
|---|---|---|---|
| **F0** | Contrato fechado e provas pequenas, sem código de produção (lista abaixo) | — | Não |
| **F1** | Tipo de árvore, `Object.logic_tree`, compilador, ~12 nós, compilação no P e ao salvar, regeneração exata. Teste dos 15 segundos | Baixo | Não |
| **F2** | Then em Esperar/Action/Sound/Steering/Vídeo, Frames de Estado, Ir para Estado | Médio (estados) | Não |
| **F3** | Receitas: Andar WASD, Pular, Coletar Item, Vida e Dano, Porta com Tecla, Plataforma vai-e-volta. Árvore nova com nota | Baixo | Não |
| **F4** | Demais sensores e actuators por tabela, priorizando os mais usados no RolimaRacer. Nó Rodar Python | Baixo, mas é volume | Não |
| **F5** | Depuração: nomes ligando nó e brick na janela F4/F5, pausar no disparo pelo nó. Investigar destaque do nó ativo no Node Editor durante o jogo | Médio | Talvez (só leitura) |
| **F6** | Avaliar, só com caso real: ver bricks existentes como árvore (importação), pinos de dado, runtime próprio | — | — |

**F0, o que precisa ser provado antes da F1:**
1. **Estados:** se o usuário também tem bricks com estados no mesmo objeto, os estados da árvore usam os mesmos
   números por nome? Proposta: Frame de Estado com o mesmo nome de um estado existente usa aquele número. Sem
   Frames, os controllers gerados ficam nos estados iniciais do objeto. Confirmar o que acontece quando um
   actuator State do usuário troca o estado.
2. **Expression no lugar de portas:** cena headless comparando, por evento, `(A ou B) e não C` em Expression
   contra a mesma lógica em bricks And/Or/Nand com estados auxiliares. Conferir os pulsos positivo e negativo
   enviados aos actuators.
3. **Campos dos nós a partir do RNA dos bricks:** gerar as propriedades do nó copiando as definições do RNA
   (enum, padrão, limites) em vez de escrever à mão. Medir em Keyboard (enum de teclas), Motion (vetores) e
   Action (ponteiro para Action). Se não der, escrever à mão os ~12 da F1.
4. **Lista de regeneração:** propriedade ID com nomes de bricks sobrevive a salvar/reabrir, append, cópia do
   objeto e Undo.
5. **Desempenho do compilador** numa árvore de 100 nós em 20 objetos, dentro do `game_pre`.

**Nós da F1 (proposta):**
- Gatilhos: Sempre, Tecla, Botão do Mouse, Colisão (por propriedade), Propriedade (comparação), Mensagem.
- Lógica: E, Ou, Não.
- Ações: Movimento, Definir Propriedade, Somar à Propriedade, Som, Remover Objeto, Esperar (o Then entra na F2).

## 9. Validação

- **Background (`bpy`):** criar a árvore por script, compilar e conferir sensores, controllers, actuators,
  ligações, grupo e lista de regeneração. Salvar, reabrir e recompilar sem duplicar. Bricks do usuário no mesmo
  objeto ficam intactos.
- **Player headless:** a mesma lógica feita em bricks à mão e pela árvore, com registro por tick gravado em
  arquivo (o runtime não imprime no stdout redirecionado, conforme a F2a dos bricks). Os eventos precisam ser
  iguais.
- **To Python:** a árvore compilada converte pelo conversor existente com o mesmo resultado, como já é exigido dos
  bricks.
- **Web:** um pacote de teste com a cena da F1. Não deveria mudar nada, porque o jogo só vê bricks.
- **Teste à mão do usuário:** o teste dos 15 segundos na F1. Na F2, uma plataforma vai-e-volta e um inimigo com
  estados feitos só por nós.

## 10. Riscos

- **Usuário edita os bricks gerados:** perde a edição na próxima compilação. Mitigação: grupo recolhido com nome
  claro e aviso no Logic Editor.
- **Conflito de estados com bricks do usuário:** é o ponto mais delicado. Fica resolvido na F0 antes de qualquer
  código.
- **Volume de nós:** são ~30 sensores e actuators. A geração por tabela (F0, item 3) é o que mantém isso barato.
- **Expectativa de "Blueprint completo":** o plano diz explicitamente o que fica fora (dados, laços, funções). O
  escape é Python.
- **Undo:** compilar dentro do `save_pre` mexe no objeto. Conferir que isso não suja o Undo nem marca o arquivo
  como modificado depois de salvar.

## 11. Decisões em aberto (para o usuário)

1. Compilar para bricks nativos (opção A) em vez de gerar Python? (proposta: sim)
2. Uma árvore compartilhável entre vários objetos? (proposta: sim)
3. Bricks gerados visíveis no Logic Editor, num grupo recolhido? (proposta: sim; escondê-los esconde a depuração)
4. Nomes: "Logic Tree" e as famílias "Gatilhos / Lógica / Ações / Receitas" em pt-BR ("Triggers / Logic /
   Actions / Recipes" em inglês)?
5. A lista de nós da F1 está boa para passar no teste dos 15 segundos?
6. Começar pela F0?

## 12. Referências externas

| Referência | O que aproveitar |
|---|---|
| UPBGE Logic Nodes | Mesma linhagem de engine e o mesmo modelo de complemento aos bricks. Serve de referência de semântica e de lista de nós |
| Unreal Blueprints | Separar fio de execução de dado. Eventos como pontos de entrada. Norte de experiência |
| Animation Nodes (Blender 2.7x) | Sistema de nós em Python sobre `bNodeTree`: ordem por dependência e geração de código |
| Godot VisualScript (removido no 4.0) | O alerta: generalizar demais deixa o editor mais trabalhoso que escrever código |
