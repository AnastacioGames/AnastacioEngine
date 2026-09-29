# AnastacioEngine
> Game engine para criação de jogos 3D, baseada na Range Engine 1.6 Rev1 e na linhagem UPBGE / Blender 2.79.

> [!IMPORTANT]
> **Para baixar a engine, use a seção [Download](#download) ou a página de [Releases](https://github.com/AnastacioGames/AnastacioEngine/releases).**
> O botão verde **Code → Download ZIP** baixa só o código-fonte, sem os executáveis.

![Splash Screen da AnastacioEngine](https://raw.githubusercontent.com/AnastacioGames/AnastacioEngine/main/release-images/v0.4.2/splash.png)

## Download

Versão atual: **[AnastacioEngine 0.4.5](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.4.5)** (Linux) · **[0.4.4](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.4.4)** (Windows)

| Pacote | Conteúdo |
|---|---|
| [Windows x64 (0.4.4)](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.4.4/AnastacioEngine-0.4.4-windows-x64.zip) | Editor e runtime, portátil (extraia e rode). [SHA-256](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.4.4/AnastacioEngine-0.4.4-windows-x64.zip.sha256) |
| [Linux x86_64 (0.4.5)](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.4.5/AnastacioEngine-0.4.5-linux-x86_64.tar.xz) | Editor e runtime nativos, com as bibliotecas incluídas. Ubuntu 22.04+, Debian 12+, Mint 21+, Fedora e Arch recentes. [SHA-256](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.4.5/AnastacioEngine-0.4.5-linux-x86_64.tar.xz.sha256) |
| [RangeArmor 0.4.0](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.4.0/RangeArmor-0.4.0-windows-x64.zip) | Ferramenta separada para criar e empacotar projetos. O painel roda no Windows e exporta jogos para Windows e Linux. [SHA-256](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.4.0/SHA256SUMS.txt) |

**Como usar:** extraia o pacote numa pasta própria e abra `RangeEngine.exe` (Windows) ou `RangeEngine` (Linux).
Para rodar um jogo exportado, use `RangeRuntime`. No Linux não é preciso instalar bibliotecas: o pacote já traz
as que usa em `lib/` e depende só do que qualquer desktop tem (driver de vídeo, X11/Wayland, som). Para pôr o
ícone no menu e na dock, rode `./install-desktop.sh` dentro da pasta.

## Novidades da 0.4.5 (só Linux)

- **Abre em mais distros:** o pacote agora é compilado no Ubuntu 22.04 (exige glibc 2.35) e leva as bibliotecas
  junto. Corrige `libOpenImageIO.so.2.4: cannot open shared object file` no Ubuntu 26.04 e o erro de glibc em
  distros mais antigas que o Ubuntu 24.04. Testado em Ubuntu 22.04, Debian 12, Ubuntu 26.04 e Fedora limpos.
- **Ícone da Range** na janela e atalho `.desktop` para o menu de aplicativos.
- A engine é a mesma da 0.4.4; o Windows continua na 0.4.4.
- Se ainda der erro, rode `ldd ./RangeEngine | grep "not found"` e mande a saída numa
  [issue](https://github.com/AnastacioGames/AnastacioEngine/issues).

## Novidades da 0.4.4

Correções dos bugs reportados pelo Kitsuy (crash com `setHalfAnimations`, folhagem Hashed sem MSAA, rodas do
carro, runtime sem GPU), navmesh dinâmica, Link de objeto e previews automáticas no Asset Browser, espelho e água
com corte oblíquo e correções de lâmpadas e sombras. **Mudança de API:** `setAntiAliasing(0)` e `(1)` usam 4
amostras. O pacote Windows já traz as correções de previews do Asset Browser (`.range`, grupos vazios).
Detalhes nas [notas do release](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.4.4).

## Novidades da 0.4.3

Addons sem avisos do Python 3.11 e correção do loop de tempo (Fixed Timestep fora da interface, v-sync sem
atraso falso). O resto é igual à 0.4.2.

## Novidades da 0.4.2

### Destaque: render Cycles na placa de vídeo
- **NVIDIA (CUDA):** placas RTX 20, 30, 40 e 50 já vêm suportadas no pacote do Windows, sem instalar o CUDA Toolkit.
- **AMD (OpenCL):** render e bake na GPU AMD, testados numa RX 6800M.
- **Embree:** render na CPU mais rápido, no Windows e no Linux.
- Bake de iluminação na GPU dá o mesmo resultado que na CPU.

### Correções importantes
- **Linux:** o pacote 0.4.1 não abria fora da máquina de build (`No module named 'encodings'`). Corrigido e
  testado num Ubuntu 24.04 limpo. **Quem baixou o 0.4.1 deve atualizar.**
- **Arquivos UPBGE:** abrir um projeto UPBGE com sensores escrevia fora da memória; corrigido. Save/Load do
  `globalDict` agora também lê os arquivos `.bgeconf` do UPBGE.
- **Material com shader GLSL próprio:** apagar o texto do shader deixava o material apontando para memória
  liberada (crash). Corrigido, junto com vazamentos de memória.
- **Subsurface Scattering:** Scale 0 gerava pixels pretos; corrigido.
- **Custom Viewport da câmera:** ficava errado ao redimensionar a janela ou usar resolução dinâmica; agora
  se ajusta a cada frame.
- **Foliage (vento):** grama instanciada não balançava e a base das plantas se mexia; corrigido. O vento
  também não perde precisão em sessões longas.
- **Screens:** Ctrl+Seta deixava de trocar de screen depois de apagar uma; corrigido.
- **Theme:** Copy Global Theme agora atualiza toda a interface de uma vez.
- Diversas correções de segurança e estabilidade no Cycles (leitura de arquivos, luzes IES, buffers grandes).

### Novidades e aprimoramentos
- **Asset Browser:** novo modo do File Browser para navegar por bibliotecas de `.blend` e arrastar objetos,
  grupos e materiais direto para a Vista 3D.
- **Outliner com coleções:** pastas para organizar a cena. Uma pasta pode ficar "fora do jogo" (objetos
  começam inativos, prontos para o Add Object) e virar um Group com um clique.
- **Painéis reorganizados:** abas Camera, Material, Render, Physics, Vehicle, Game Settings e Text Editor em
  painéis nativos, com opções que o jogo não usa escondidas e avisos quando uma combinação não tem efeito.
- **Custom Viewport:** presets prontos (tela cheia, picture-in-picture, tela dividida, quadrantes) e prévia do
  tamanho em pixels.
- **Aba Input** nas Propriedades e **aba Export Game** (RangeArmor, Web e Android) no editor.
- **Veículos:** motor em Nm, pedais, joystick, moto e telemetria de marcha/RPM no HUD e no Vehicle Lab.
- **Idiomas:** interface em English, Português, Español e Русский.
- **Windows:** arquivos `.blend` e `.range` associados à engine.

## Ferramentas para criar jogos
- **World, clima e iluminação:** clima direto na cena e sombras CSM ajustáveis pelo editor.
- **Veículos:** transforme um Rigid Body em veículo e ajuste a física em tempo real pelo Vehicle Lab.
- **GPU Skinning:** escolha **RanGE GPU Skinning** no painel da Armature e ligue **GPU Skinning** no material.
- **RangeArmor:** crie projetos e prepare distribuições pelo RangeArmor Panel.
- **Render Cycles:** CPU, NVIDIA (CUDA) e AMD (OpenCL).

## Plataformas
| Plataforma | Estado |
|---|---|
| Windows x64 | Suportada. |
| Linux x86_64 | Suportada (nativo). |
| Web (navegador) | Em testes; ainda não usar em produção. Detalhes no [roadmap](docs/roadmap.md). |
| Android | Experimental: APK/AAB gerado pelo editor a partir do pacote Web. |
| 32-bit | Não suportado. |

## Sobre

AnastacioEngine é um projeto da Anastacio Games. A engine parte da Range Engine 1.6 Rev1, derivada da
UPBGE 0.2.5b / Blender 2.79, e foca em performance, renderização, ferramentas de runtime e fluxo de produção
para jogos.

## Desenvolvimento (código-fonte)

- [Diagramas da arquitetura](docs/diagramas-arquitetura.md) · [Índice da documentação](docs/README.md) · [Roadmap](docs/roadmap.md) · [Histórico técnico](docs/changelog.md)
- [Build no Windows](docs/build-notes.md) · [Build no Linux](docs/linux-build.md) · [Arquitetura](docs/architecture.md)
- [Como contribuir](CONTRIBUTING.md) · [Licença](docs/licenca.md) · [Relatório de melhorias](relatorio-melhorias-anastacioengine.md)

Para agentes de código, as regras operacionais estão em [AGENTS.md](AGENTS.md).
