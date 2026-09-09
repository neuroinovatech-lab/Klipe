# MotionCore

Motor de texto/motion em Skia pra substituir O motor de navegador no Klipe.

O motor de navegador desenha texto em Chrome headless → PNG por frame → ProRes 4444 em
disco → ffmpeg lê de volta → QTRLE. São três idas e voltas entre disco, CPU e
GPU só pra desenhar letra. O MotionCore desenha na memória e joga os frames
crus no stdin do ffmpeg, que já grava o MOV com alpha.

## Estado

| Fase | O que é | Status |
|---|---|---|
| 1 | Prova de paridade (`stackedReveal`) | **pronta** |
| 2 | Legendas nativas (`outline`) + barra de progresso | **pronta** |
| 3 | Top-8 títulos | **pronta** |
| 4 | Fechar o projeto de referência (sem motor de navegador) | **pronta** |

Portado: `lower3rd`, `hero`, `flash`, `kinetic`, `panel`, `ribbon`, `counter`,
`quote`, `stackedReveal`, `pointList`, `compound2`, `cutMask`, legenda
`outline` e barra de progresso.

Os três últimos (`pointList`, `compound2`, `cutMask`) não entraram pelo tempo de
desenho deles — entraram porque **enquanto um único título precisar do motor de navegador,
o bundle inteiro sobe**: 13 s antes do primeiro frame.

Os oito saíram da **contagem de uso nos projetos**, não de intuição: lower3rd
(64 usos), hero (47), flash (29), kinetic (26), panel (22), ribbon (18),
counter (17), quote (15) — 76% de tudo que já foi posto em timeline. A lista
antiga do plano trazia letterings/scribble/headline, que somam menos de 1%.

Qualquer outra coisa continua indo pro motor de navegador — o `forge_render.py` separa a
fila sozinho e o que o MotionCore não sabe (ou falhar) cai de volta pro caminho
antigo. O `boxed` de legenda **não** está portado (falta a caixa de fundo por
palavra); ele está fora da lista de propósito, pra não sair errado calado.

> O motor de navegador ainda aparece aqui por dois motivos: é o **gabarito** da paridade
> (é ele que define o que é "certo") e é a **rede** dos estilos que faltam.
> Quando a fase 3 fechar, ele sai.

## Medições (i9-14900F, 1080x1920)

**Overlay de vídeo inteiro** (legenda + barra), projeto de 3 min, 52 legendas:

| | Tempo |
|---|---|
| motor de navegador monolítico | **~11 min** (1,76 GB de ProRes) |
| MotionCore | **42 s** (318 MB, já QTRLE) |

**Títulos**, 2 de 9 s (270 frames cada):

| | Tempo |
|---|---|
| motor de navegador (bundle 14,6s + render 30,5s) | **45,1 s** |
| MotionCore | **3,2 s** |

Sem contar o bundle (que amortiza num lote grande): 30,5s → 3,2s, **9,5x**.

Pra montar o projeto de 3 min que serve de régua:

```bash
python -m motioncore.bench3
```

O que trouxe cada pedaço, por frame:

| | ms/frame |
|---|---|
| ingênuo (uma saveLayer de tela cheia por sombra) | 1900 |
| sombra como blur de máscara de glifo | 62 |
| sombra pré-rasterizada uma vez | 12 |
| linha achatada em imagem quando a transform assenta | 5,2 |
| + pular frame idêntico ao anterior | ~1 |

## Paridade

O gabarito são stills do própriO motor de navegador. Pra rodar:

```bash
node motioncore/_ref_still.js motioncore/_parity_cases.json
```

```bash
python -m motioncore.parity --montagem
```

Sai uma tabela por caso. `--montagem` grava lado-a-lado + mapa de diferença
(vermelho = só no motor de navegador, verde = só no MotionCore) em
`_parity/<caso>/montagem/`.

Para as legendas, o gabarito sai do `edit_config` real:

```bash
python motioncore/_gen_caption_cases.py
```

```bash
node motioncore/_ref_still.js motioncore/_parity_captions.json
```

```bash
python -m motioncore.parity --spec motioncore/_parity_captions.json --montagem
```

### Como ler os números

- **núcleo** — sobreposição só dos pixels opacos (alpha > 200). É *este* que diz
  se a letra caiu na posição e no tamanho certos. Última rodada: **0,973** nos
  títulos e **0,958** nas legendas.
- **cobertura** — sobreposição de tudo com alpha > 8, sombra borrada incluída.
  Cai fácil pra ~0,87 numa legenda com glow de 28 px sem que nada esteja
  errado: uma diferença imperceptível na rampa do borrão faz milhares de pixels
  cruzarem o limiar. Não confundir com defeito.
- **deslocamento** — ≤ 1,5 px em todos os casos.

Quando os dois caem juntos, é bug de verdade. Quando só a cobertura cai, é a
sombra. Confira na montagem antes de sair caçando.

Sempre que mexer em `text.py` ou num estilo, rode a paridade de novo — os
gabaritos já estão em disco, então custa segundos.

## Arquitetura

```
anim.py      spring/interpolate do motor de navegador portados 1:1 (bate em 2e-16)
fonts.py     @font-face do template antigo + matching de peso do CSS
text.py      caixa de linha do CSS, quebra gulosa, text-shadow, cache de imagem
scene.py     wrapper de clip da timeline (posX/posY/scale/rotation/opacity)
styles/      um módulo por estilo: build() / draw() / signature()
render.py    loop de frames → stdin do ffmpeg → QTRLE (sem disco intermediário)
parity.py    compara com os stills do motor de navegador
```

### Contrato de um estilo

```python
def build(ctx, registry, w, h) -> list        # mede o texto (custo fixo)
def anim(ctx, blocos) -> tuple                # TODOS os valores animados
def draw(canvas, ctx, registry, w, h, blocos) # desenha um frame
def signature(ctx, blocos) -> tuple           # opcional: frames iguais
```

`signature()` é o que deixa o render pular frame repetido — e é onde mora o
bug mais perigoso do motor: **se a assinatura esquecer algo que muda na tela, o
frame anterior é repetido e o vídeo sai errado, calado.** Por isso `draw()` e
`signature()` leem os mesmos valores, do mesmo `anim()`. Escrevendo as duas
listas na mão elas divergem — foi o que aconteceu na primeira versão: 92 frames
repetidos indevidamente, um deles com diferença de 137 níveis de alpha.

Pra provar que não mente:

```bash
python motioncore/_check_signature.py
```

Ele desenha todo frame de verdade e compara com o anterior. Se a assinatura
disse "igual" e os pixels diferem, acusa. **Rodar sempre que mexer num estilo.**

Relacionado: o `spring()` arredonda em 1e-6 de propósito. Sem isso ele converge
assintoticamente e dois frames visualmente idênticos teriam valores diferentes
na 12ª casa — dedup nenhum seria seguro.

## Armadilhas já pagas

- **`text-shadow` não é saveLayer.** Uma camada de tela cheia por sombra custava
  1,9 s por frame. É blur da máscara do glifo.
- **O spring de referencia é iterativo**, não fórmula fechada. Integra um passo por
  frame com deltaTime limitado a 64 ms. Fórmula analítica erra justo na entrada.
- **`interpolate` extrapola por padrão.** O `scale` do `stackedReveal` depende
  disso pra estourar acima de 1. Clampar mata o "pop".
- **O Blink arredonda ascent/descent** pra inteiro antes de montar a caixa de
  linha. Sem isso a linha desloca fração de pixel.
- **Peso 900 sem face 900 não vira negrito sintético.** O CSS cai pro 800. O
  `stackedReveal` pede 900 e o Montserrat só tem até 800.
- **Medir com `Font.measureText` ignora kerning** — dá 4 px a mais em
  "SEM PARAR". O shaping do skparagraph resolve.
- **O Skia desenha com alpha pré-multiplicado.** Converter na leitura custa
  40 ms/frame em Python; no ffmpeg (`unpremultiply=inplace=1`) some no ruído.
- **`gap: 16` no CSS vale pros dois eixos** — entre palavras E entre linhas.
  Aplicar só entre palavras deixou o `kinetic` com as linhas 16 px coladas.
- **`text-align` padrão é `left`, não centro.** `quote`, `lower3rd` e `panel`
  não declaram, então alinham à esquerda quando o texto quebra.
- **`line-height: normal` não é 1** — é a altura natural da fonte
  (ascent+descent+lineGap). Assumir 1 onde o TSX não declara desloca a linha.
- **Quando o texto quebra, a caixa fica com a largura DISPONÍVEL inteira**, não
  a da maior linha (shrink-to-fit = `min(max-content, disponível)`). É isso que
  decide onde termina o painel do `lower3rd`.
- **O Chrome conta o `letter-spacing` depois do último caractere** na largura;
  o skparagraph não. Sem somar de volta, texto centralizado sai meio
  espaçamento à direita — 4 px num título com `letter-spacing: 8`.
- **`inset` de filho absoluto mede da caixa de PADDING do pai**, não da de
  conteúdo. O brilho do `quote` estava 160 px estreito por causa disso.
- **`'Playfair Display'` (com espaço) não casa com o `@font-face`
  `'PlayfairDisplay'`.** O Chrome pula pro próximo da lista e desenha em
  **Georgia**. Ou seja: o `quote` (e `compound`/`compound3`/`compound4`) saem em
  Georgia hoje, não em Playfair. O MotionCore reproduz isso de propósito —
  "consertar" mudaria o visual de tudo que já foi entregue.
