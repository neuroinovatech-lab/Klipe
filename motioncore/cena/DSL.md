# O DSL de cena do MotionCore

Referência do formato que `motioncore.cena.Cena` desenha. Tudo aqui foi
extraído do código (`camadas.py`, `valores.py`, `textura.py`, `__init__.py`) —
se algo divergir, o código manda e este arquivo está errado.

Uma cena é um objeto JSON. Não há código dentro dela: um modelo pode emitir uma
cena e nada que ele escreveu é executado.

```json
{
  "duracao": 4.0,
  "fundo": "#101014",
  "params": { "titulo": "AGORA", "cor": "#E8940A" },
  "camadas": [
    { "tipo": "retangulo", "larg": "60%", "alt": 160, "cor": "@cor",
      "escalaX": [[0, 0], [0.35, 1, "outCubic"]] },
    { "tipo": "texto", "texto": "@titulo", "tamanho": 120, "peso": 900,
      "opacidade": [[0, 0], [0.25, 1]] }
  ]
}
```

| chave no topo | tipo | o que faz |
|---|---|---|
| `camadas` | lista | **obrigatória.** Desenhadas em ordem; a última fica por cima. |
| `duracao` | número | segundos. Informativa — quem renderiza decide quantos frames. |
| `fundo` | cor | pinta o quadro inteiro antes de tudo. Sem ela, fundo transparente. |
| `params` | objeto | valores nomeados; `"@nome"` em qualquer lugar é trocado por eles. |

`params` é resolvido **uma vez**, na construção. `"@nome"` sem entrada
correspondente levanta `KeyError` — não passa em branco.

## Sistema de coordenadas

A origem é o **centro do quadro**, não o canto. Uma camada sem `x`/`y` nasce no
meio.

- `x` positivo vai para a **direita**
- `y` positivo vai para **cima**

Isto vale para o posicionamento de camada. **Dentro de um `path` (`d`) e nos
pontos `de`/`para` de uma `linha`, vale a convenção do Skia: `y` positivo desce.**
É a pegadinha mais fácil de cair: `"para": [0, 100]` desce 100 px, enquanto
`"y": 100` sobe 100.

## As três formas de um valor

Qualquer campo numérico aceita:

```json
82                                  número fixo
[[0, 0], [0.4, 1, "outCubic"]]      keyframes: [segundos, valor, easing?]
{"mola": {"damping": 14}, "de": -60, "para": 0}    mola (spring de referencia)
{"ruido": {"escala": 0.01, "amp": 8}}              ruido — micro-movimento continuo
"50%"                               porcentagem — só onde marcado abaixo
```

**Keyframes.** O easing nomeado num keyframe governa o trecho que **começa**
nele. Fora do intervalo, o valor segura na ponta — não extrapola. Sem easing
declarado, o padrão é `suave` (= `inOutCubic`), **não** linear: keyframe linear
lê como maquete.

> Consequência: **easing no último keyframe nunca é lido**, porque ali não
> começa trecho nenhum. `[[0,0],[1,1,"outBack"]]` anima em `suave`, não em
> `outBack`, e ninguém avisa — nem o `validar()`, nem o desenho. Verificado: um
> easing inexistente nessa posição não levanta erro; no primeiro keyframe,
> levanta.

**Mola.** Campos: `damping` (14), `mass` (1), `stiffness` (200), `clamp` (false),
`em` (segundo em que a mola começa), `de` (0), `para` (1).

**Porcentagem.** `"50%"` é fração da largura (para `x`, `larg`, `rx`,
`largura_max`) ou da altura (para `y`, `alt`, `ry`), medida a partir do
**centro** — `"0%"` é o centro e `"50%"` é a borda.

### `ruido` — o que faz o objeto parado parecer vivo

```json
{"ruido": {"escala": 0.01, "amp": 8, "base": 0, "semente": 1}}
```

`escala` e por FRAME. A tabela abaixo saiu de medir uma peca profissional; os
numeros valem direto:

| escala | periodo | serve para |
|---|---|---|
| 0.003–0.005 | ~10 s | deriva de marca d'agua, blob de fundo |
| 0.006–0.008 | ~5 s | micro-deriva de card, tremor de camera |
| 0.01–0.015 | ~3 s | flutuacao de elemento, particula, logo |
| 0.02–0.03 | ~1,5 s | pulso de brilho, faisca |
| 0.04–0.06 | ~0,8 s | barra de onda, LED piscando |
| 0.1 | ~0,3 s | tremor violento |

Amplitude tipica: **2–4 px** (micro-deriva — invisivel de proposito, mas o olho
registra), 5–8 (logo), 10–20 (particula), 25–30 (blob de fundo).

Para PULSO, use `base` e mantenha `amp` entre **25% e 50%** dele: assim o valor
nunca zera nem dobra.

> Use sementes DIFERENTES em `x` e `y`. Com a mesma, os dois eixos andam
> juntos e o objeto desliza na diagonal em vez de vagar.

> Deixe o eixo Y com **menos** amplitude que o X (proporcao ~2:1). Tremor
> vertical le como defeito de render; horizontal le como energia.

### Easings (31, mais bezier)

Alem dos nomeados, qualquer keyframe aceita uma **bezier cubica** no lugar do
nome: `[[0, 0], [1, 1, [0.22, 1, 0.36, 1]]]`. Sao os quatro pontos de controle
do CSS. Serve para portar uma curva de referencia exata em vez de escolher "o
nomeado mais parecido".



`linear`, `suave`, `entra`, `sai` e as famílias `in/out/inOut` de `Quad`,
`Cubic`, `Quart`, `Quint`, `Expo`, `Sine`, `Circ`, `Back`, mais `outElastic`,
`outBounce`, `inBounce`.

`suave` = `inOutCubic`, `entra` = `inCubic`, `sai` = `outCubic`. Nome
desconhecido levanta erro **no desenho**, não na validação.

## Campos comuns a toda camada

| campo | animável | padrão | nota |
|---|---|---|---|
| `tipo` | — | — | obrigatório |
| `x`, `y` | sim | 0 | aceita `"%"` |
| `escala` | sim | 1 | multiplica `escalaX`/`escalaY` |
| `escalaX`, `escalaY` | sim | 1 | |
| `rotacao` | sim | 0 | graus |
| `opacidade` | sim | 1 | `<= 0.001` pula o desenho |
| `traco` | sim | 1 | recorta o contorno progressivamente (0→1 = a pena correndo) |
| `revelar` | sim | 1 | cortina; ver abaixo |
| `inicio`, `fim` | não | — | segundos; fora da janela a camada nem é avaliada |
| `blur` | não | 0 | raio CSS (dividido por 2 para virar sigma) |

`revelar` também aceita a forma longa `{"prog": <animável>, "dir": "esq"}`, com
`dir` em `esq` (padrão), `dir`, `cima`, `baixo`. É **wipe**, não revelação por
caractere.

## Tipos de camada

Sete: `texto`, `retangulo`, `elipse`, `linha`, `path`, `grupo`, `textura`.

### `texto`

| campo | padrão | nota |
|---|---|---|
| `texto` | — | **obrigatório**, não pode ser vazio |
| `fonte` | Inter | só o nome da família já serve |
| `peso` | 400 | |
| `tamanho` | 82 | |
| `cor` | `#FFFFFF` | |
| `italico` | false | |
| `entrelinha` | natural | `null` = altura natural da fonte, que **não** é 1 |
| `alinha` | `center` | |
| `espacamento` | 0 | letter-spacing |
| `largura_max` | — | onde quebra a linha; aceita `"%"` |
| `contorno`, `contorno_larg` | — | stroke do texto |
| `sombra` | `[]` | lista de `{x, y, blur, cor}` |

`\n` no texto é quebra obrigatória e sobrevive à quebra por largura.

### `retangulo`

`larg` (200), `alt` (200), `raio` (0, canto arredondado). Todos animáveis;
`larg`/`alt` aceitam `"%"`.

### `elipse`

`raio`, ou `rx`/`ry` separados (100). `de_grau` (0) e `varre_grau` (360)
recortam um arco — **ambos animáveis**, e é assim que um setor "abre".
`raio_int` (0) transforma o setor em anel.

> Arco não fechado **sem** `raio_int` vira segmento: a corda liga as pontas e o
> preenchimento sai como lente, não como fatia.

### `linha`

`de` (`[0,0]`) e `para` (`[100,0]`), cada um `[x, y]`. Lembre: aqui `y` desce.

### `path`

`d` — **obrigatório**, sintaxe SVG. `centrar` (true) recentra o path na origem
da camada; ponha `false` para usar as coordenadas como escritas.

### `grupo`

`camadas` — lista de filhas. O transform do grupo se aplica a todas.

> **Use um grupo para deslocar uma grade.** Ver a armadilha do `repetir`.

### `textura`

Papel envelhecido, ocupa o quadro inteiro. Cara de gerar e **cacheada pelos
parâmetros** — nasce uma vez por cena.

`cor` (`#C7A978`), `grao` (0.055), `manchas` (9), `vinheta` (0.55), `falhas`
(22), `facho` (true), `semente` (1879).

> Duas cenas com a mesma `semente` produzem a mesma folha. Lado a lado no mesmo
> vídeo, isso denuncia a repetição — troque a semente.

## Preenchimento e contorno

Vale para `retangulo`, `elipse`, `linha` e `path`:

- `cor` — preenche. Aceita cor CSS **ou** um objeto de degradê.
- `contorno` + `contorno_larg` (2) — contorna.
- `hachura` — preenche com traços finos, a textura de buril.

**Degradê** como `cor`:

```json
{"tipo": "radial", "cores": ["#2A2A55", "#0A0A12"], "raio": 900, "centro": [0,0]}
{"tipo": "linear", "cores": ["#FFF", "#000"], "de": [0,-400], "para": [0,400], "paradas": [0, 1]}
```

**Hachura**:

```json
{"modo": "paralela", "angulo": 34, "passo": 5, "cor": "#68120F",
 "opacidade": 0.7, "largura": 0.9}
{"modo": "radial", "passo": 0.5, "r0": 262, "cor": "#1E1A16", "opacidade": 0.9}
```

`passo` é em **pixels** na paralela e em **graus** na radial. No modo radial,
`r0` é o raio de onde os traços partem — sem ele numa figura anelar, os traços
convergem no centro e chapam tudo.

## `repetir` — a grade

```json
"repetir": {"cols": 13, "linhas": 5, "espX": 74, "espY": 74,
            "atraso": 0.018, "ordem": "linha"}
```

`ordem`: `linha` (varre da esquerda), `centro` (irradia do meio), `aleatorio`
(pipoca, determinístico).

`atraso` desloca o tempo **local** de cada cópia — é o que transforma grade em
padrão: sem ele as N cópias animam em uníssono e o olho lê um bloco só.

> **A armadilha.** Esse deslocamento vale para **todo** valor animado da camada,
> `x` inclusive. Uma deriva declarada na própria grade não a translada — ela a
> **cisalha**, porque cada cópia lê a deriva num instante diferente.
>
> Para mover a grade inteira, embrulhe num `grupo` e anime o `x` **do grupo**:
> ele resolve no tempo real da cena, e a onda do `atraso` continua por dentro.

`inicio`/`fim` também são avaliados no tempo local de cada cópia.

## O crítico: `validar()`

```python
validar(spec)                  # só ERROS — é o que Cena() usa pra recusar
validar(spec, avisos=True)     # erros + avisos (prefixados com "aviso:")
```

**Erros** — a cena não desenha, ou desenha errado calada. Bloqueiam:

| erro | mensagem |
|---|---|
| chave desconhecida no topo | `chave 'duraca' desconhecida — você quis dizer 'duracao'?` |
| `tipo` inexistente | lista os sete válidos |
| campo que não existe naquele tipo | `campo 'opacidad' não existe em 'retangulo' — você quis dizer 'opacidade'?` |
| `texto` vazio, `path` sem `d` | |
| easing inexistente | `easing 'naoExiste' não existe` |
| keyframe malformado | `keyframe precisa ser [tempo, valor] ou [tempo, valor, easing]` |
| tempo de keyframe não numérico | |
| campo errado em `repetir`, `hachura`, `revelar` | com sugestão |
| `ordem` ou `dir` inválidas | lista as válidas |

A validação é recursiva dentro de `grupo`, e o caminho do erro é completo
(`camadas[3].camadas[0].opacidade[7]`).

**Avisos** — a cena desenha certo, mas há configuração morta:

| aviso | por quê |
|---|---|
| easing no último keyframe | nunca é lido; ele governa o trecho que *começa* nele |

Chave começando com `_` é ignorada em qualquer nível — é o escape para anotar a
própria cena sem que o crítico reclame.

### Por que easing morto é aviso e não erro

Foi uma decisão medida, não uma concessão. Os helpers `surge()` e `desenha()`
do projeto escrevem `[[t0, 0], [t1, 1, "inOutCubic"]]` — easing no último
keyframe. Isso aparece **300 vezes só na prancha**, e mais 146 nas três faixas.

Como o easing que eles pedem (`inOutCubic`) é exatamente o padrão (`suave`), o
desenho nunca saiu errado. Transformar isso em erro derrubaria toda cena que
existe hoje para corrigir algo que, ali, não tem efeito nenhum.

Mas o aviso precisa existir, porque **nem sempre é inofensivo**: o
`lower_third.json` pede `outCubic` e `outBack` em último keyframe, e esses não
são o padrão — aquela cena anima diferente do que está escrito, e sempre animou.

O que ainda **não** é checado: tipo do valor (texto onde se espera número só
falha no desenho) e `"@param"` não declarado (levanta `KeyError` na construção).

## Custo

- Texto é medido **uma vez** na construção da cena; desenhar é o custo por frame.
- `textura` é cacheada pelos parâmetros.
- `Cena.assinatura(t)` devolve uma tupla dos valores animados naquele instante:
  dois frames com a mesma assinatura são o mesmo pixel. Ela é derivada da mesma
  leitura que o desenho usa, então **não pode** divergir dele — que é o bug de
  classe inteira que o motor antigo tinha.

## Quando não usar o DSL

Ele não é Turing-completo, de propósito. Quando a peça precisa de algo que o DSL
não expressa — `PathMeasure` com lógica própria, filtro de imagem, geometria
calculada — o caminho é um módulo Python em `styles/`. DSL para os 95%, código
para os 5% que são de verdade novos.
