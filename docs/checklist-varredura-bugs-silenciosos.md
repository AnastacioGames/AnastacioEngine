# Checklist reutilizável: varredura de bugs silenciosos

Use esta checklist para revisar um subsistema antes de considerá-lo estável.

## Preparação

- [ ] Delimitar pastas, módulos carregados e integrações externas.
- [ ] Ler changelog, issues e documentação relevante.
- [ ] Registrar data, commit-base e arquivos/pastas cobertos.
- [ ] Preservar alterações não relacionadas no worktree.

## Frentes de inspeção

- [ ] Ownership manual: alocação, liberação, referências e retornos antecipados.
- [ ] Contratos: `TODO`, `FIXME`, pré-condições, ponteiros nulos e erros ignorados.
- [ ] Limites: buffers, índices, contadores, overflow e tamanhos extremos.
- [ ] Stubs/defaults: retornos constantes, funções vazias e fallbacks silenciosos.
- [ ] API pública: argumentos, tipos, retornos, propriedades e nomes persistidos.
- [ ] Callbacks/ciclo de vida: registro, desregistro, recarga e duplicação.
- [ ] Validade de dados: ponteiros, referências CPython, objetos removidos e dados corrompidos.

## Registro de cada achado

- [ ] ID, local exato e sintoma/risco.
- [ ] Reprodução mínima ou condição de entrada.
- [ ] Causa provável e informação necessária para o reparo.
- [ ] Prioridade e estado: corrigido, dúvida registrada ou falso positivo.
- [ ] Teste de validação executado e resultado.

## Encerramento

- [ ] Executar o ciclo funcional aplicável.
- [ ] Para C/C++, executar build do alvo afetado.
- [ ] Para Python, importar e testar registro/desregistro repetido.
- [ ] Atualizar changelog e registrar limitações restantes.

## Relatório desta execução

O resultado da varredura de `source/source/blender` está separado em:

[relatorio-varredura-bugs-silenciosos.md](relatorio-varredura-bugs-silenciosos.md)
