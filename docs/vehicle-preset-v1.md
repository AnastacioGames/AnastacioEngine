# `vehicle_preset_v1.json`

Preset versionado dos parâmetros físicos que a engine consegue salvar e
reaplicar sem depender da lógica arcade do jogo.

## Contrato

```json
{
  "version": 1,
  "chassisMass": 800.0,
  "coordinateSystem": {"right": 0, "up": 2, "forward": 1},
  "rayCastMask": 1,
  "wheels": [{
    "connectionPoint": [0.5, 0.8, 0.3],
    "downDirection": [0.0, 0.0, -1.0],
    "axleDirection": [-1.0, 0.0, 0.0],
    "suspensionRestLength": 0.3,
    "wheelRadius": 0.3,
    "hasSteering": true,
    "suspensionStiffness": 20.0,
    "suspensionDampingRelaxation": 2.3,
    "suspensionDampingCompression": 4.4,
    "friction": 1000.0,
    "rollInfluence": 0.1
  }]
}
```

Todos os números são finitos e usam SI: metros, quilogramas e os valores
Bullet já usados pelos setters de suspensão/atrito. `right`, `up` e `forward`
formam obrigatoriamente uma permutação de `0, 1, 2`; a convenção do projeto é
`0, 2, 1`. O `axleDirection` usa a convenção pública de `addWheel()` e
`getWheelConfig()` (não a inversão interna do Bullet).

Os campos mostrados são obrigatórios. Há de 1 a 32 rodas, sem pontos de
conexão duplicados, raio positivo, comprimento de repouso não negativo,
tunings não negativos e vetores de direção não nulos nem colineares. Chaves
desconhecidas são ignoradas para permitir extensões futuras; `version` diferente
de 1 falha. JSON truncado, tipos errados, NaN/infinito e texto após o documento
também falham.

## Operação atual

`vehicle.savePreset(path)` captura o veículo ativo e grava em `path@`,
renomeando-o sobre o arquivo final somente após a escrita completa.
`vehicle.loadPreset(path)` lê e valida o arquivo inteiro antes de alterar o
veículo. Massa e tunings são enfileirados para a próxima fronteira segura de
física; eixos e máscara são aplicados pela API física existente.

Por enquanto, o carregamento requer exatamente a mesma estrutura de rodas:
mesma quantidade e, em cada índice, os mesmos pontos, direções, comprimento,
raio e `hasSteering` (com pequena tolerância de ponto flutuante). Os campos
estruturais são preservados no arquivo, mas não são aplicados live:
reconstruí-los requer reassociar os objetos visuais/motion states de cada roda,
infraestrutura que ainda não existe. Uma diferença estrutural falha antes de
qualquer alteração; o veículo original é mantido intacto.

## Rebuild estrutural explícito

`vehicle.rebuildPreset(path, wheelObjects)` recria o veículo para aplicar um
preset com outra geometria ou quantidade de rodas. `wheelObjects` é uma
sequência de objetos de jogo visuais, um por entrada de `wheels` e na mesma
ordem. A API valida o arquivo e todos os objetos antes de criar o candidato;
em seguida cria novos motion states, troca o veículo antes do próximo tick de
física e destrói o anterior. Por exemplo, uma moto pode fornecer as rodas
`[roda_dianteira, roda_traseira]`; um triciclo, três objetos. A chamada não
cria nem remove objetos da cena e não transfere forças, freios ou direção que
estavam ativos no veículo anterior.

## Legado

Os JSONs Nativo e Arcade do VehicleConfigEditor não contêm pontos/direções de
roda nem as referências visuais. Eles não podem virar um v1 independente sem
inventar geometria. Um adaptador futuro deve partir de um v1 exportado do
veículo correspondente, sobrepor apenas massa/suspensão/raio/atrito que tenham
mapeamento inequívoco e listar explicitamente todos os assists preservados no
JSON original (tração, drift, downforce, animações, motor e controles).
