# API Python do Rec Play

Toca no jogo os Takes gravados no editor. Um Take guarda a pose de cada ator, e o nome é o que aparece na lista de Takes.

## KX_Scene

| Membro | O que faz |
| --- | --- |
| `scene.takes` | Lista com os nomes dos Takes da cena. |
| `scene.play_take(nome)` | Toca todos os atores do Take. Retorna `False` se o nome não existir. |

## KX_GameObject

| Método | O que faz |
| --- | --- |
| `obj.play_take(nome)` | Toca só este objeto. Retorna `False` se o Take não existir ou não tiver este ator. |
| `obj.stop_take()` | Para no ponto atual. |
| `obj.is_playing_take()` | `True` enquanto o objeto segue um Take. |

Enquanto toca, o ator fica sem lógica e sem física. As duas voltam quando o Take acaba ou com `stop_take()`.

```python
import bge

def abrir_porta(cont):
    scene = bge.logic.getCurrentScene()
    porta = scene.objects['Porta']
    if not porta.is_playing_take():
        porta.play_take('Take 1')
```

Teste automático: `tools/debug/editor_rec_api.py` e `tools/debug/jogo_rec_api.py`.
