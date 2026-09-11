# AnastacioEngine

> Game engine para criação de jogos 3D, baseada na Range Engine 1.6 Rev1 e na linhagem UPBGE / Blender 2.79.

> [!IMPORTANT]
> **Para baixar a engine, use os links da seção [Download](#download) ou a página de [Releases](https://github.com/AnastacioGames/AnastacioEngine/releases).**
> O botão verde **Code → Download ZIP** do GitHub baixa somente uma cópia do repositório (README e imagens); ele **não** contém os executáveis da AnastacioEngine.

![Splash Screen da AnastacioEngine](https://raw.githubusercontent.com/AnastacioGames/AnastacioEngine/main/release-images/v0.1.0/Captura%20de%20tela%202026-09-08%20192214.png)

## Download

A versão atual é **[AnastacioEngine 0.2.0](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.2.0)**, para Windows x64.

| Pacote | Conteúdo |
|---|---|
| [AnastacioEngine Windows x64](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.2.0/AnastacioEngine-0.2.0-windows-x64.zip) | Editor, runtime e dependências necessárias para criar e executar projetos. |
| [AnastacioEngine + RangeArmor](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.2.0/AnastacioEngine-0.2.0-windows-x64-with-RangeArmor.zip) | Pacote completo, com a engine e a ferramenta RangeArmor para criar e empacotar projetos. |
| [SHA-256](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.2.0/SHA256SUMS.txt) | Hashes para verificar a integridade dos downloads. |

Extraia o ZIP em uma pasta própria e abra `RangeEngine.exe`. Para executar um jogo exportado, use `RangeRuntime.exe`.

## Destaques da versão 0.2.0

- **Resolução dinâmica:** ajusta a escala interna de renderização pelo tempo de GPU, com alvo de FPS, limites, suavização e histerese.
- **Cutscenes nativas:** sequências persistentes, operadores, API Python, importação/exportação JSON e eventos `WAIT_*`.
- **External Files mais robusto:** bibliotecas, Groups e Texts ficam visíveis no Outliner, com importação explícita de scripts ausentes.
- **Renderização e desempenho:** OpenGL Core Profile no runtime, CSM, GPU skinning, partículas GPU, LOD/impostores, instancing e pós-processamento.
- **Ferramentas de jogo:** veículos nativos, ImGui, console, Logic Bricks ampliados, World/Weather e RangeArmor para Windows x64.
- **Editor refinado:** painéis de Render, World, Scene e splash/About reorganizados para o fluxo atual da AnastacioEngine.

Leia a lista detalhada de recursos, correções e limitações nas [notas completas da Release 0.2.0](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.2.0).

## Ferramentas para criar jogos

### World, clima e iluminação

Configure clima diretamente na cena e ajuste o sistema de sombras CSM pelo editor.

![Weather Effects: chuva, nuvens e lens flare](https://raw.githubusercontent.com/AnastacioGames/AnastacioEngine/main/release-images/v0.1.0/Captura%20de%20tela%202026-09-08%20184701.png)

### Veículos e simulação

Transforme um Rigid Body em veículo, configure as rodas e ajuste a física em tempo real pelo Vehicle Lab.

![Configuração nativa de Vehicle](https://raw.githubusercontent.com/AnastacioGames/AnastacioEngine/main/release-images/v0.1.0/Captura%20de%20tela%202026-09-08%20190545.png)

### RangeArmor

Crie projetos, mantenha os arquivos organizados e prepare distribuições com o RangeArmor Panel.

![RangeArmor Panel](https://raw.githubusercontent.com/AnastacioGames/AnastacioEngine/main/release-images/v0.1.0/Captura%20de%20tela%202026-09-08%20192117.png)

### GPU Skinning

O modo **RanGE GPU Skinning** move a deformação do esqueleto para a GPU. Para
usá-lo, selecione esse modo no painel da Armature e habilite **GPU Skinning**
nas opções do material que será usado pelo objeto.

![Seleção de RanGE GPU Skinning na Armature](https://raw.githubusercontent.com/AnastacioGames/AnastacioEngine/main/release-images/v0.1.0/Captura%20de%20tela%202026-09-08%20194142.png)

![Opção GPU Skinning nas configurações do material](https://raw.githubusercontent.com/AnastacioGames/AnastacioEngine/main/release-images/v0.1.0/Captura%20de%20tela%202026-09-08%20194403.png)

## Status de plataformas

| Plataforma | Estado |
|---|---|
| Windows x64 | Suportada nesta release. |
| Linux x64 | Experimental; ainda não há pacote oficial publicado. |
| 32-bit | Não suportado. |

## Estrutura da distribuição

- `RangeEngine.exe`: editor para criar e configurar projetos.
- `RangeRuntime.exe`: player standalone para arquivos `.range`.
- `RangeArmor/`: painel, launcher e scripts de empacotamento; presente somente no pacote completo.

## Sobre

AnastacioEngine é um projeto da Anastacio Games. A engine parte da Range Engine 1.6 Rev1, derivada da UPBGE 0.2.5b / Blender 2.79, e concentra seu desenvolvimento em performance, renderização, ferramentas de runtime e fluxo de produção para jogos.

![Janela About da AnastacioEngine](https://raw.githubusercontent.com/AnastacioGames/AnastacioEngine/main/release-images/v0.1.0/Captura%20de%20tela%202026-09-08%20192236.png)

## Links

- [Releases e downloads](https://github.com/AnastacioGames/AnastacioEngine/releases)
- [Relatório de melhorias](relatorio-melhorias-anastacioengine.md)
