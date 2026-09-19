# AnastacioEngine
> Game engine para criação de jogos 3D, baseada na Range Engine 1.6 Rev1 e na linhagem UPBGE / Blender 2.79.
> [!IMPORTANT]
> **Para baixar a engine, use os links da seção [Download](#download) ou a página de [Releases](https://github.com/AnastacioGames/AnastacioEngine/releases).**
> O botão verde **Code → Download ZIP** do GitHub baixa somente uma cópia do repositório (README e imagens); ele **não** contém os executáveis da AnastacioEngine.

![Splash Screen da AnastacioEngine 0.3.0](https://raw.githubusercontent.com/AnastacioGames/AnastacioEngine/main/release-images/v0.2.0/splash.png)

## Download

A versão atual é **[AnastacioEngine 0.4.0](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.4.0)** para Windows x64. O pacote Linux x86_64 da 0.4.0 será anexado em breve; até lá, o Linux mais recente é o da 0.3.0.

| Pacote | Conteúdo |
|---|---|
| [AnastacioEngine Windows x64](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.4.0/AnastacioEngine-0.4.0-windows-x64.zip) | Editor, runtime e dependências necessárias para criar e executar projetos no Windows. |
| [AnastacioEngine Linux x86_64](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.3.0/AnastacioEngine-0.3.0-linux-x64.tar.gz) | Editor e runtime nativos para Linux x86_64 (validado fora do WSL). **Versão 0.3.0**; a 0.4.0 chega em breve. |
| [RangeArmor (painel Windows, exporta para Windows e Linux)](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.4.0/RangeArmor-0.4.0-windows-x64.zip) | Ferramenta separada para criar e empacotar projetos (painel, launcher e scripts de exportação). O painel roda apenas no Windows, mas exporta e empacota jogos para Windows **e** Linux x86_64. |
| [SHA-256](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.4.0/SHA256SUMS.txt) | Hashes para verificar a integridade dos downloads. |

Extraia o pacote da sua plataforma em uma pasta própria e abra `RangeEngine.exe` (Windows) ou `RangeEngine`
(Linux). Para executar um jogo exportado, use `RangeRuntime`/`RangeRuntime.exe`. A partir da 0.3.0, a
RangeArmor é distribuída como arquivo separado — baixe-a à parte se quiser criar/empacotar projetos.

## Versão 0.4.0

Esta é a distribuição pronta da AnastacioEngine para Windows x64 e, agora, Linux x86_64 nativo. Escolha o
pacote desejado na seção **Download**, extraia-o em uma pasta própria e execute `RangeEngine`.

- O pacote da engine contém o editor, o runtime e as dependências necessárias para cada plataforma.
- A **RangeArmor** agora é um pacote à parte, com as ferramentas para criar e empacotar projetos.
- Use `RangeRuntime`/`RangeRuntime.exe` para executar um jogo exportado (`.range`).
- Consulte `SHA256SUMS.txt` caso queira verificar a integridade do download.

## Ferramentas para criar jogos
### World, clima e iluminação
Configure clima diretamente na cena e ajuste o sistema de sombras CSM pelo editor.
### Veículos e simulação
Transforme um Rigid Body em veículo, configure as rodas e ajuste a física em tempo real pelo Vehicle Lab.
### RangeArmor
Crie projetos, mantenha os arquivos organizados e prepare distribuições com o RangeArmor Panel.
### GPU Skinning
O modo **RanGE GPU Skinning** move a deformação do esqueleto para a GPU. Para
usá-lo, selecione esse modo no painel da Armature e habilite **GPU Skinning**
nas opções do material que será usado pelo objeto.
### Exportação para Web (em desenvolvimento)
O perfil Web (Range) e o botão **Exportar Web** já existem no editor, mas a exportação para o navegador **ainda não está finalizada** e não deve ser usada em projetos de produção.
## Status de plataformas
| Plataforma | Estado |
|---|---|
| Windows x64 | Suportada nesta release. |
| Linux x86_64 | Suportada nativamente (fora do WSL) a partir da 0.3.0. |
| 32-bit | Não suportado. |
## Estrutura da distribuição
- `RangeEngine`/`RangeEngine.exe`: editor para criar e configurar projetos.
- `RangeRuntime`/`RangeRuntime.exe`: player standalone para arquivos `.range`.
- `RangeArmor`: painel, launcher e scripts de empacotamento; distribuído como pacote separado a partir da 0.3.0.

## Sobre

AnastacioEngine é um projeto da Anastacio Games. A engine parte da Range Engine 1.6 Rev1, derivada da UPBGE 0.2.5b / Blender 2.79, e concentra seu desenvolvimento em performance, renderização, ferramentas de runtime e fluxo de produção para jogos.

## Links

- [Releases e downloads](https://github.com/AnastacioGames/AnastacioEngine/releases)
- [Relatório de melhorias](relatorio-melhorias-anastacioengine.md)
