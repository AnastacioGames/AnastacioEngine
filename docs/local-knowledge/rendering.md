# Conhecimento local: rendering

> Gerado por `tools/build_local_knowledge.sh` via modelo local (Ollama).
> Resumo raso para orientacao inicial - para decisoes reais, leia o arquivo completo.

## source/source/gameengine/Rasterizer/Node/RAS_BaseNode.h

Este arquivo implementa a classe `RAS_BaseNode`, que é uma classe de base para envolver uma classe de renderização em um game engine C++ derivado do UPBGE/Blender 2.79. O `RAS_BaseNode` simula a renderização através de funções de ligação (bind) e desligação (unbind), permitindo que os nós de renderização sejam manipulados de forma mais modular e controlada. Ele provavelmente interage com outros sistemas do motor de jogo, como o gerenciamento de cena, renderização gráfica, e sistemas de propriedades ou dados de nós, para coordenar a renderização e a atualização dos objetos e elementos gráficos na cena.

## source/source/gameengine/Rasterizer/Node/RAS_DownwardNode.h

Este arquivo implementa a classe `RAS_DownwardNode`, que é uma estrutura de nó usada em um motor de jogo C++ (fork do UPBGE/Blender 2.79) para renderização em ordem não classificada. A classe `RAS_DownwardNode` armazena nós filhos e é responsável pela execução da função de ligação, renderização dos filhos e desligamento em uma ordem de cima para baixo na árvore de nós. Essa estrutura interage com outros sistemas do motor, como a renderização de objetos 3D e a manipulação de dados de nós, ao fornecer um mecanismo para gerenciar e processar a hierarquia de nós durante o processo de renderização.

## source/source/gameengine/Rasterizer/Node/RAS_DummyNode.h

Este arquivo define uma classe `RAS_DummyNode` usada em um game engine C++ baseado no UPBGE (Unreal Python Blender Game Engine) ou Blender 2.79. A classe implementa um nó dummy, provavelmente usado como uma estrutura básica para outros nós ou para representar um lugar reservado no sistema de nós da engine. Ela contém estruturas internas `RAS_DummyNodeData` e `RAS_DummyNodeTuple` para armazenar dados e tuplas associadas ao nó. A classe também tem um método `Print` para exibir informações sobre o nó, possivelmente para fins de depuração. Esses nós dummy podem interagir com outros sistemas de renderização, física, lógica de jogo e gerenciamento de cena, servindo como uma base para a construção de nós mais complexos e funcionalidades específicas no engine.

## source/source/gameengine/Rasterizer/Node/RAS_RenderNode.h

Este arquivo define uma estrutura de nós de renderização para um motor de jogo C++ baseado no UPBGE/Blender 2.79. Implementa uma árvore de nós para gerenciar e renderizar materiais, arrays de exibição e slots de malha. Os nós interagem com sistemas de renderização, gerenciamento de materiais, armazenamento de arrays de exibição e buffers de instânciação. A estrutura permite o fluxo de dados e operações específicas para cada nível de renderização, desde a configuração global da renderização até detalhes específicos de malhas e materiais.

## source/source/gameengine/Rasterizer/Node/RAS_UpwardNode.h

Este arquivo implementa uma classe RAS_UpwardNode, que é uma extensão da classe base RAS_BaseNode, usada em um motor de jogo C++ (fork do UPBGE/Blender 2.79). O RAS_UpwardNode armazena uma referência ao seu nó pai, permitindo que seja usado em processos de renderização ordenados onde dois nós não consecutivos podem compartilhar o mesmo nó pai. Este design ajuda a controlar a ordem de renderização, onde os nós podem ser renderizados de cima para baixo ou de baixo para cima. A classe provavelmente interage com outros sistemas de renderização, gerenciamento de nós e estruturas de dados que dependem da ordem ou hierarquia dos nós na cena.

## source/source/gameengine/Rasterizer/Node/RAS_UpwardNodeIterator.h

Este arquivo implementa classes para iterar sobre nós em uma estrutura de árvore hierárquica em um motor de jogo C++ baseado no UPBGE/Blender 2.79. As classes `RAS_DummyUpwardNodeIterator` e `RAS_UpwardNodeIterator` são templates que permitem iterar sobre nós e seus nós pais, gerenciando o encadeamento e desencadeamento (bind e unbind) dos nós conforme necessário durante a iteração. Elas são usadas para renderização ordenada de nós, onde a ordem de renderização é determinada pela relação hierárquica entre os nós. Essas classes provavelmente interagem com outros sistemas de gerenciamento de nós, renderização e hierarquia dentro do motor de jogo.

## source/source/gameengine/Rasterizer/RAS_2DFilter.cpp

Este arquivo implementa um sistema de filtros 2D dentro de um motor de jogos C++ baseado no UPBGE (Unreal Engine Python Binding for Games Engine) / Blender 2.79. O `RAS_2DFilter` permite aplicar efeitos visuais 2D como bloom, tonemapping, efeitos atmosféricos e outros efeitos de pós-processamento na cena renderizada. Ele interage com vários outros sistemas, incluindo:

1. `RAS_2DFilterManager` - Gerenciador de filtros.
2. `RAS_Rasterizer` - Sistema de rasterização.
3. `RAS_ICanvas` - Canvas de renderização.
4. `RAS_OffScreen` - Renderização off-screen.
5. `RAS_Rect` - Recursos de retângulos.
6. `EXP_Value` - Valores de expressão.

O sistema usa shaders GLSL para aplicar os efeitos, e a classe `RAS_ScopeExit` é usada para garantir que os recursos sejam corretamente desligados após o uso, prevenindo vazamento de recursos. O arquivo também define uma série de uniformes pré-definidos que podem ser usados em shaders para controle de efeitos específicos.

## source/source/gameengine/Rasterizer/RAS_2DFilter.h

Este arquivo C++ define a classe `RAS_2DFilter`, que é parte de um motor de jogo baseado em uma versão do UPBGE/Blender 2.79. A classe `RAS_2DFilter` é responsável por gerenciar e aplicar efeitos 2D em tempo real, como bloom, tonemapping, lens flare, entre outros. Ela interage com vários outros sistemas do motor, incluindo `RAS_Rasterizer` (para renderização), `RAS_ICanvas` (para gerenciamento de viewport), e `RAS_OffScreen` (para renderização off-screen). A classe permite a definição e binding de uniforms específicos para os shaders 2D, além de gerenciar texturas de entrada e saída, e realizar cálculos de offsets para amostragem de pixels nas texturas.

## source/source/gameengine/Rasterizer/RAS_2DFilterData.cpp

Este arquivo implementa uma classe chamada `RAS_2DFilterData` que é provavelmente usada em um motor de jogo baseado no UPBGE (Unreal Engine Blender Game Engine) ou em um fork do Blender 2.79, escrito em C++. Essa classe é responsável por armazenar dados relacionados a filtros 2D aplicados a objetos no jogo. Os dados incluem um ponteiro para o objeto de jogo (`gameObject`), um booleano que indica se o filtro deve usar mipmaps (`mipmap`), um índice de modo de filtro (`filterMode`), e um índice de passo de filtro (`filterPassIndex`). Essa classe provavelmente interage com outros sistemas de renderização e efeitos visuais dentro do motor de jogo, aplicando e controlando filtros 2D para objetos renderizados na cena.

## source/source/gameengine/Rasterizer/RAS_2DFilterData.h

Este arquivo define a estrutura e os dados associados a filtros 2D que podem ser aplicados em um motor de jogos C++ baseado no UPBGE/Blender 2.79. A classe `RAS_2DFilterData` encapsula informações sobre filtros personalizados e filtros internos predefinidos, como Fxaa, Bloom, Tonemap, entre outros. Esses filtros são usados para efeitos visuais na renderização 2D, como correção de antialiasing, efeitos de luz, efeitos atmosféricos e distorções de imagem.

O arquivo provavelmente interage com outros sistemas do motor de jogos, como o gerenciador de filtros 2D (`RAS_2DFilterManager`), que é responsável por adicionar, remover e gerenciar os filtros ativos durante a renderização. Além disso, ele pode interagir com sistemas que lidam com propriedades de objetos de jogo (`KX_GameObject`) e atuadores (`SCA_2DFilterActuator`) para controlar a aplicação e as configurações dos filtros.

## source/source/gameengine/Rasterizer/RAS_2DFilterManager.cpp

Este arquivo implementa um gerenciador de filtros 2D (`RAS_2DFilterManager`) para um motor de jogos C++ baseado no UPBGE/Blender 2.79. Ele gerencia vários tipos de filtros visuais 2D, como desfoque, nitidez, dilatação, erosão, antialiasing (FXAA), mapeamento tonal e sombra de área de saom (SSAO), utilizando shaders GLSL para aplicar esses efeitos. O gerenciador interage com outros sistemas do motor, como o gerenciador de tela (`RAS_ICanvas`), o rasterizador (`RAS_Rasterizer`) e o processamento off-screen (`RAS_OffScreen`), permitindo que esses filtros sejam aplicados às imagens renderizadas antes de exibi-las na tela ou salvá-las.

## source/source/gameengine/Rasterizer/RAS_2DFilterManager.h

Este arquivo define a classe `RAS_2DFilterManager` em um fork do UPBGE/Blender 2.79, responsável por gerenciar e aplicar efeitos de pós-processamento 2D no engine. Ele implementa:

- Um conjunto de filtros pré-definidos como SSR (Screen Space Reflection), SSAO (Ambient Occlusion), Bloom, Tone Mapping, entre outros.
- Métodos para adicionar, remover e recuperar filtros de acordo com índices específicos.
- Funções para garantir a criação de filtros específicos como Tonemap, SSAO e FXAA, caso eles não estejam inicialmente habilitados.

Este sistema provavelmente interage com:

- `RAS_Rasterizer` para executar comandos de renderização.
- `RAS_ICanvas` para lidar com a tela de visualização.
- `RAS_OffScreen` para manipular buffers de renderização off-screen.
- `RAS_2DFilter` para implementar os efeitos de filtro específicos.

## source/source/gameengine/Rasterizer/RAS_2DFilterOffScreen.cpp

Este arquivo implementa a classe RAS_2DFilterOffScreen, responsável por gerenciar um framebuffer off-screen em um game engine C++ derivado do UPBGE/Blender 2.79. Essa classe é crucial para renderização de duas dimensões em um buffer separado da tela principal, permitindo efeitos como renderização de camadas, filtros post-processamento e renderização off-screen para texturas. Ela interage com outros sistemas como RAS_ICanvas para gerenciar o tamanho da viewport e RAS_Rasterizer para definir propriedades de viewport e scissor. Além disso, ela utiliza funções da GPU_framebuffer e GPU_texture para criar, gerenciar e liberar recursos de framebuffer e texturas.

## source/source/gameengine/Rasterizer/RAS_2DFilterOffScreen.h

Este arquivo define a classe `RAS_2DFilterOffScreen` em um fork do UPBGE (Blender 2.79) game engine, que gerencia uma tela fora da tela com múltiplas texturas de cor (que podem ser amostradas) e uma textura de profundidade opcional (também amostrável). Diferentemente de `RAS_OffScreen`, esta classe é única por `RAS_2DFilter` para evitar a invalidação implícita do filtro quando a tela fora da tela é excluída ou usada em múltiplos filtros ou cenas diferentes.

A classe interage com outros sistemas como `RAS_Rasterizer`, `RAS_ICanvas`, `GPUFrameBuffer` e `GPUTexture`, permitindo a renderização de múltiplos canais de cores e profundidade em um único frame buffer off-screen. Isto é particularmente útil para efeitos de renderização avançados e filtros 2D em jogos e simulações 3D.

## source/source/gameengine/Rasterizer/RAS_AttributeArray.cpp

Este arquivo implementa a classe `RAS_AttributeArray` que gerencia atributos de vértice em um game engine C++ baseado no UPBGE/Blender 2.79. Essa classe é responsável por armazenar e gerenciar atributos como posições, cores, normais e texturas de vértices em uma estrutura eficiente para renderização. Ela interage com outros sistemas como `RAS_DisplayArray` para lidar com a representação visual dos dados e `RAS_AttributeArrayStorage` para armazenamento otimizado dos atributos. A classe também suporta operações de transferência de recursos através de move semantics e permite a limpeza de recursos com o método `Clear()`.

## source/source/gameengine/Rasterizer/RAS_AttributeArray.h

O arquivo `RAS_AttributeArray.h` implementa uma classe que gerencia atributos de vértices em um game engine C++ baseado no UPBGE/Blender 2.79. Essa classe é responsável por lidar com diferentes tipos de atributos, como coordenadas de vértices, coordenadas UV, normais, tangentes, cores de vértices, índices de deformação de pele e pesos de pele. A classe mantém uma lista de atributos e fornece métodos para acessar e gerenciar os dados de armazenamento desses atributos. Ela provavelmente interage com outros sistemas do renderizador, como o `RAS_Rasterizer` para lidar com diferentes modos de desenho e o `RAS_DisplayArray` para gerenciar arrays de exibição de vértices.

## source/source/gameengine/Rasterizer/RAS_AttributeArrayStorage.cpp

Este arquivo implementa uma classe C++ chamada RAS_AttributeArrayStorage, que é responsável por gerenciar armazenamento e manipulação de atributos de vértices em um sistema de renderização de jogos baseado em fork do UPBGE/Blender 2.79. Ele provavelmente interage com outros sistemas de renderização e gerenciamento de recursos, como o RAS_StorageVao, que lida com o armazenamento e binding de VAOs (Vertex Array Objects) para otimizar o desempenho de renderização. A classe permite a ligação e desligação de primitivas, facilitando o processo de renderização eficiente em um engine de jogos.

## source/source/gameengine/Rasterizer/RAS_AttributeArrayStorage.h

Este arquivo define a classe `RAS_AttributeArrayStorage`, que é uma parte crucial de um sistema de renderização em um motor de jogos C++ (fork do UPBGE/Blender 2.79). Essa classe é responsável por gerenciar e armazenar dados de atributos, como vértices e normais, que são necessários para renderizar primitivas geométricas. A classe interage com outros sistemas como `RAS_StorageVao` para lidar com Vertex Array Objects (VAOs), que otimizam o acesso a dados de vértices, e `RAS_DisplayArrayLayout` para definir a estrutura e o layout dos dados de atributos. Essa interação garante que os dados sejam organizados e acessados de forma eficiente durante o processo de renderização, permitindo uma renderização eficaz e otimizada das primitivas gráficas no jogo.

## source/source/gameengine/Rasterizer/RAS_BatchDisplayArray.cpp

Este arquivo implementa a classe `RAS_BatchDisplayArray`, responsável pelo batch rendering (processamento em lote) de geometria em um game engine C++ baseado no UPBGE/Blender 2.79. Essa classe estende `RAS_DisplayArray` e permite a mesclagem (merge) e divisão (split) de múltiplos arrays de display, otimizando o processamento gráfico ao renderizar vários objetos como um único lote. Ele interage principalmente com o sistema de renderização da engine, gerenciando vértices, índices, normais, tangentes, coordenadas de UV e cores de vértices. Além disso, a classe notifica sobre atualizações de tamanho, provavelmente interagindo com outros sistemas relacionados ao gerenciamento de recursos gráficos e ao pipeline de renderização.

## source/source/gameengine/Rasterizer/RAS_BatchDisplayArray.h

Este arquivo define a classe `RAS_BatchDisplayArray` em um game engine C++ (fork do UPBGE/Blender 2.79), que estende a classe `RAS_DisplayArray`. A classe é responsável por gerenciar e otimizar a renderização de múltiplos objetos 3D no jogo, utilizando técnicas de renderização em lote (batching) para melhorar a performance. 

Ela implementa a gestão de partes (parts) de objetos 3D, onde cada parte pode ter seus próprios vértices e índices, e pode ser transformada independentemente. A classe fornece métodos para mesclar (merge) arrays de display com matrizes de transformação e dividir partes existentes.

Interagindo com outros sistemas, provavelmente inclui:

1. **Sistema de Renderização**: Para renderizar os objetos 3D em lotes.
2. **Sistema de Geometria**: Para fornecer os dados de vértices e índices dos objetos.
3. **Sistema de Transforms**: Para aplicar matrizes de transformação aos objetos.
4. **Sistema de Memória**: Para gerenciar a memória de buffers de vértices e índices.

## source/source/gameengine/Rasterizer/RAS_BatchGroup.cpp

Este arquivo implementa a classe `RAS_BatchGroup` em um motor de jogos C++ (fork do UPBGE/Blender 2.79), responsável por gerenciar o agrupamento e renderização eficiente de vários objetos de malha que compartilham o mesmo material e formato de vértice. A classe permite que múltiplas instâncias de malha (`RAS_MeshUser`) sejam combinadas em um único lote (`Batch`) para reduzir chamadas de renderização e melhorar o desempenho.

A classe `RAS_BatchGroup` interage com vários outros sistemas do motor, incluindo:

1. **Sistemas de Malha (`RAS_MeshUser`, `RAS_MeshSlot`)**: Gerencia como as malhas são associadas e manipuladas dentro do grupo de lote.

2. **Sistemas de Material (`RAS_IMaterial`, `RAS_MaterialBucket`)**: Determina como diferentes materiais são agrupados e renderizados.

3. **Sistemas de Exibição (`RAS_DisplayArrayBucket`, `RAS_DisplayArray`)**: Lida com a criação e manipulação de buffers de vértices e primitivas.

4. **Sistemas de Mensagem (`CM_Message`)**: Utilizado para registrar erros e avisos durante a operação de agrupamento e divisão de malhas.

Essa implementação é crucial para otimizar o desempenho de renderização em cenários com muitos objetos visíveis simultaneamente, permitindo que o motor processe menos dados de vértice e use menos chamadas de desenho.

## source/source/gameengine/Rasterizer/RAS_BatchGroup.h

Este arquivo implementa a classe RAS_BatchGroup, responsável por gerenciar e otimizar a renderização de grupos de meshes que compartilham o mesmo material em um engine de jogos C++ baseado no UPBGE/Blender 2.79. A classe combina múltiplos display arrays em um único batch para melhorar a eficiência do rendering. Ele provavelmente interage com outros sistemas relacionados à renderização, como RAS_DisplayArrayBucket, RAS_BatchDisplayArray e RAS_MeshUser, além de sistemas de gerenciamento de materiais e transformações de objetos.

## source/source/gameengine/Rasterizer/RAS_BoundingBox.cpp

Este arquivo implementa a classe `RAS_BoundingBox`, responsável por gerenciar e calcular os limites (bounding box) de objetos 3D em um motor de jogo baseado em C++, fork do UPBGE/Blender 2.79. Essa classe é crucial para otimizações de renderização, detecção de colisões e culling de visibilidade. Ela se interage principalmente com o `RAS_BoundingBoxManager`, que gerencia uma lista de bounding boxes ativas e inativas, e com objetos `RAS_DisplayArray`, que representam dados de vértices de malhas. O arquivo também inclui uma subclasse `RAS_MeshBoundingBox`, especifica para malhas 3D, que recalcula seus limites com base nos dados de vértice fornecidos.

## source/source/gameengine/Rasterizer/RAS_BoundingBox.h

Este arquivo implementa classes para gerenciamento e cálculo de bounding boxes em um motor de jogo C++ baseado no UPBGE/Blender 2.79. A classe `RAS_BoundingBox` representa um bounding box genérico, com funcionalidades como adicionar e remover usuários, verificar se foi modificado, e obter as coordenadas do AABB (Axis-Aligned Bounding Box). A classe `RAS_MeshBoundingBox` herda de `RAS_BoundingBox` e é especializada para bounding boxes que acompanham malhas, utilizando vários display arrays para calcular seu AABB. Este sistema provavelmente interage com outros sistemas relacionados à física, colisão e renderização, como o gerenciador de bounding boxes (`RAS_BoundingBoxManager`) e classes de malhas e display arrays.

## source/source/gameengine/Rasterizer/RAS_BoundingBoxManager.cpp

Este arquivo implementa um gerenciador de bounding boxes (`RAS_BoundingBoxManager`) para um motor de jogo baseado em C++, provavelmente um fork do UPBGE/Blender 2.79. O gerenciador é responsável por criar, atualizar e gerenciar o ciclo de vida de bounding boxes associados a objetos e malhas no jogo. Ele interage com outros sistemas do motor, como renderização e física, para fornecer informações de colisão e detecção de limites. O código inclui métodos para criar bounding boxes gerais e específicos para malhas, atualizar suas posições e estados, e mesclar bounding boxes de diferentes managers.

