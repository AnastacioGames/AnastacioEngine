# Ferramentas incluídas

Esta pasta reúne ferramentas externas e protótipos que não fazem parte do build da AnastacioEngine. Cada
uma possui compatibilidade, licença e ciclo de atualização próprios.

| Ferramenta | Estado e compatibilidade | Observação |
| --- | --- | --- |
| `ADD na engine anastacioEngine/UI/collections` | Add-on local para API Blender 2.79 / RanGE 1.6. | Consulte o README da pasta; não é integrado ao build. |
| `ADD na engine anastacioEngine/UI/Logic Nodes for Range - Beta` | Add-on externo de Logic Nodes. | Verifique compatibilidade antes de instalar; ele pode copiar DLLs para o diretório da engine. |
| `RangeArmor-master` | Projeto externo MIT, descontinuado nas versões modernas do Range Engine. | Não é necessário para o fluxo atual sem validação específica. |

Não altere READMEs de projetos importados sem necessidade. Para adotar uma ferramenta, registre primeiro a
versão, a origem, a licença, os arquivos que ela instala e uma forma de reversão.
