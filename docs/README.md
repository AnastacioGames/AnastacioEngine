# Documentação

Este índice separa estado atual, procedimentos e histórico. Documentação herdada de dependências em
`source/extern/` e documentação de ferramentas importadas em `tools/` não fazem parte deste conjunto.

## Estado atual

- [Perfil Web e validação de exportação](web-profile-validation-plan.md): autoria na Range Engine com compatibilidade Web,
  catálogo de avisos/bloqueios, manifesto de capacidades e marcos de implementação; marcos A (painel) e B (núcleo puro) implementados.
- [Empacotamento e hospedagem Web](web-deploy.md): `tools/web/package-web.py` gera pasta/ZIP hospedável a partir
  do build Emscripten; `tools/web/verify-package.cjs` verifica o carregamento por CDP.
- [Plano Android (APK WebView sobre o Web)](android-export-plan.md): plano revisado; prova em APK/aparelho
  real antes do exportador, com critérios de input, persistência, desempenho e ciclo de vida.
- [Roadmap Web/Android](android-web-export-roadmap.md): consolida o estado do runtime Web e usa a validação
  Linux nativa como evidência de portabilidade para planejar o export Android.

- [Roadmap](roadmap.md): somente trabalho aberto ou validação pendente.
- [Relatório de melhorias](../relatorio-melhorias-anastacioengine.md): inventário conciso do que a engine já
  possui e das decisões técnicas vigentes.
- [Modernização dos Logic Bricks](logic-bricks-modernization.md): contrato, marcos implementados e testes
  ainda pendentes dessa frente.
- [Plano do Vehicle System](vehicle-system-plan-2.md): evolução faseada da ponte Bullet, debug de veículo
  e ferramenta Vehicle Lab em ImGui.
- [Preset físico de veículo v1](vehicle-preset-v1.md): contrato do arquivo, save/load e rebuild explícito.
- [Roteiro de teste de veículo](vehicle-test-guide.md): cena padrão, automação por componente e validação manual.
- [Relatório de bugs silenciosos](relatorio-varredura-bugs-silenciosos.md): candidatos da auditoria estática
  de `source/source/blender`.
- [Auditoria estruturada de performance](performance-audit.md): taxonomia, evidências atuais e roteiro de
  validação para CPU, memória, GPU e ciclo de vida.

## Referência e manutenção

- [Pesquisa de áudio Web](web-audio-analysis.md): Audaspace/SDL2 e OpenAL do Emscripten,
  streaming, codecs e roteiro de validação para integração.
- [Auditoria da emulação OpenGL Web](web-gl-emulation-analysis.md): flags verificadas,
  incompatibilidade FULL_ES3/legacy e reprodução isolada de perda do VBO no VAO emulado.
- [Arquitetura](architecture.md): fluxo do runtime e mapa dos módulos.
- [Plano mestre de modernização do Ketsji](ketsji-engine-modernization-plan.md): sequência de correções,
  instrumentação, testes, extrações arquiteturais e otimizações do loop principal.
- [Notas de build](build-notes.md): ambiente Windows, alvos e validação.
- [Build no Linux](linux-build.md): presets do runtime/editor, dependências, empacotamento e validações em
  Linux nativo.
- [Guia de manutenção](maintenance-guide.md): arquivos normalmente afetados por cada tipo de mudança.
- [Checklist de bugs silenciosos](checklist-varredura-bugs-silenciosos.md): roteiro reutilizável de auditoria.
- [Atlas de ícones](icon-atlas-notes.md): formato e carregamento do atlas externo.
- [Distribuição 0.1](distribution-0.1.md): estrutura do pacote portátil.
- [Licença](licenca.md): resumo e localização do texto legal.

## Histórico

- [Changelog](changelog.md): registro detalhado por sessão. Entradas antigas podem conter hipóteses depois
  corrigidas; para decisões vigentes, use o roadmap e o relatório de melhorias.

## Regras de manutenção documental

- Registrar estado aberto no roadmap, sem copiar toda a investigação.
- Registrar decisões vigentes no relatório de melhorias.
- Registrar detalhes de implementação, medições e correções no changelog.
- Remover handoffs e tarefas temporárias quando o trabalho terminar; o Git preserva o histórico.
- Não duplicar regras de build entre arquivos de agentes: `AGENTS.md` é a fonte canônica.
