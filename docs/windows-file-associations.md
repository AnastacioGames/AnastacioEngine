# Associações de arquivos no Windows

O `RangeEngine.exe` pode registrar as extensões do projeto no Registro do Windows. A associação de `.blend` abre o editor; a de `.range` abre o player autônomo ao dar duplo clique.

## Registrar e remover

Execute os comandos a partir da pasta que contém **ambos** `RangeEngine.exe` e `RangeRuntime.exe`:

```powershell
& ".\RangeEngine.exe" -R
& ".\RangeEngine.exe" -U
```

`-R` registra e mostra o resultado; `-U` remove as associações da Range Engine. As variantes silenciosas, adequadas para um instalador, são `-r` e `-u`.

O registro tenta primeiro `HKLM\Software\Classes`, para todos os usuários. Sem elevação, usa `HKCU\Software\Classes`, apenas para o usuário atual.

| Extensão | Programa | Executável | Ícone |
|---|---|---|---|
| `.blend` | `RangeEngine.BlendFile` | `RangeEngine.exe "%1"` | ícone 1 do editor |
| `.range` | `RangeEngine.RangeFile` | `RangeRuntime.exe "%1"` | ícone 0 do player |

`-u` remove apenas os valores e ProgIDs criados pela Range Engine; ele não restaura automaticamente uma aplicação que estivesse associada antes. Para escolher outra, use **Abrir com** no Explorer ou as configurações de aplicativos padrão do Windows.

## Validação manual

1. Rode `RangeEngine.exe -r`.
2. No Explorer, dê duplo clique em um `.blend` e confirme que abre no editor.
3. Dê duplo clique em um `.range` e confirme que abre no `RangeRuntime`.
4. Rode `RangeEngine.exe -u` e confirme no Explorer que as associações foram removidas.

Em 2026-09-24, o registro e a remoção foram validados diretamente no Registro em `HKCU`, inclusive os comandos e ícones, restaurando as associações preexistentes. O duplo clique visual permanece pendente porque não foram abertas janelas durante a validação.
