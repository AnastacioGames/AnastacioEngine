# AnastacioEngine
> Game engine para criação de jogos 3D, baseada na Range Engine 1.6 Rev1 e na linhagem UPBGE / Blender 2.79.
> [!IMPORTANT]
> **Para baixar a engine, use os links da seção [Download](#download) ou a página de [Releases](https://github.com/AnastacioGames/AnastacioEngine/releases).**
> O botão verde **Code → Download ZIP** do GitHub baixa somente uma cópia do repositório (README e imagens); ele **não** contém os executáveis da AnastacioEngine.

## Download

A versão atual é **[AnastacioEngine 0.2.0](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.2.0)**, para Windows x64.

| Pacote | Conteúdo |
|---|---|
| [AnastacioEngine Windows x64](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.2.0/AnastacioEngine-0.2.0-windows-x64.zip) | Editor, runtime e dependências necessárias para criar e executar projetos. |
| [AnastacioEngine + RangeArmor](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.2.0/AnastacioEngine-0.2.0-windows-x64-with-RangeArmor.zip) | Pacote completo, com a engine e a ferramenta RangeArmor para criar e empacotar projetos. |
| [SHA-256](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.2.0/SHA256SUMS.txt) | Hashes para verificar a integridade dos downloads. |

Extraia o ZIP em uma pasta própria e abra `RangeEngine.exe`. Para executar um jogo exportado, use `RangeRuntime.exe`.

## Versão 0.2.0

Esta é a distribuição pronta da AnastacioEngine para Windows x64. Escolha o pacote desejado na seção **Download**, extraia-o em uma pasta própria e execute `RangeEngine.exe`.

- O pacote padrão contém a engine, o editor, o runtime e as dependências necessárias.
- O pacote **com RangeArmor** inclui também as ferramentas para criar e empacotar projetos.
- Use `RangeRuntime.exe` para executar um jogo exportado (`.range`).
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

## Links

- [Releases e downloads](https://github.com/AnastacioGames/AnastacioEngine/releases)
- [Relatório de melhorias](relatorio-melhorias-anastacioengine.md)
