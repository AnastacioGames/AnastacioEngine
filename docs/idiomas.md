# Idiomas do jogo

Traduza os textos do jogo sem escrever código. As traduções ficam numa tabela (`locale/translations.csv`,
ao lado do `.range`) que abre no Excel, no LibreOffice ou no Google Sheets.

## Passo a passo

1. **Salve o `.range`.** A pasta `locale/` é criada ao lado dele.
2. **Propriedades ▸ Cena ▸ Game Languages ▸ Enable Languages.** Escolha em que idioma os textos estão escritos
   e a primeira tradução. Todos os textos da cena já entram na tabela.
3. **Escreva as traduções.** `Open Table` abre a tabela no Text Editor (Alt+S salva), ou abra o arquivo
   `locale/translations.csv` numa planilha. Cada linha é um texto e cada coluna é um idioma. Célula vazia mostra o
   idioma original. O painel mostra quantos textos faltam em cada idioma.
4. **Confira na viewport.** `Preview Language` mostra os textos no idioma escolhido. O arquivo sempre guarda o
   original.
5. **Menu de idioma.** Selecione um texto e use `Make it a Language Button` (aba do texto ▸ Translation). No
   jogo, um clique nele passa para o próximo idioma, e ele mostra o nome do idioma ("Português (Brasil)").

A escolha do jogador fica salva. Na primeira vez, o jogo usa o idioma do sistema operacional.

## Mais coisas

- **Texto novo:** clique em `Translate All Texts` de novo. O painel avisa quando há textos fora da tabela.
- **Mais idiomas:** `Add Language`. O `X` ao lado de um idioma remove a coluna.
- **Letras que a fonte não tem (russo, japonês…):** `Generate Atlases` grava as letras de cada idioma. Para usar
  outra fonte num idioma, preencha `font` no `locale.json` (botão `Config`).
- **Language Button:** em Game ▸ Components dá para escolher a ação (Next, Previous ou Set num idioma), uma
  tecla e se o texto mostra o nome do idioma.
- **Guia dentro da engine:** botão `Guide` do painel.

## Em scripts (opcional)

```python
import Range
Range.locale.language = "pt-BR"                  # troca todos os textos na hora
Range.locale.tr("hud.lap", lap=2, total=3)       # célula "Volta {lap} de {total}"
Range.locale.next()                              # próximo idioma
Range.locale.languages                           # ['pt-BR', 'en', 'ru']
Range.locale.name()                              # 'Português (Brasil)'
```

Com logic bricks: sensores Mouse Over + Left Button → controlador Python em modo **Module** com
`range_locale.next` (ou `range_locale.previous`).
