# Estilo: prancha gravada

> **Este arquivo só entra quando o pedido chama por ele** — porque nomeia o
> estilo, ou porque pede continuidade de uma peça que o usa. Ver a regra zero
> em [PROMPT.md](../PROMPT.md).
>
> Foi formulado para o vídeo da Dra. Eli sobre percepção de padrões. Aplicá-lo
> a um assunto que não pediu papel envelhecido não é coerência de marca — é o
> gerador repetindo a última coisa que fez.

Leia [DSL.md](../DSL.md) antes: ele é o contrato do formato e esta folha é só o
estilo.

---

## Tarefa

Você recebe **uma batida de conteúdo** — um trecho de fala com início e fim — e
devolve **um objeto JSON** de cena. Nada além do JSON.

Você não escreve código. A cena é dado: quem a recebe desenha, e nada que você
escrever é executado.

## Antes de responder

1. `validar(cena)` tem que voltar vazio. Campo com nome errado é recusado e a
   mensagem diz qual era o certo.
2. Se um efeito que você quer não existir no DSL, **não invente campo**.
   Resolva com o que existe ou deixe de fora. Campo inventado é ignorado em
   silêncio e o vídeo sai errado sem ninguém saber.

---

## O que esta peça é

Uma **prancha de gravura do século XIX**: papel envelhecido, tinta marrom, régua,
buril, serifa editorial. Não é infográfico, não é slide, não é motion de rede
social. A diferença prática:

- Um diagrama de verdade tem **aparelho de medida** em volta — anel, marca de
  escala, chamada apontando. Sem isso é desenho, não é leitura.
- Preenchimento é **a buril**: centenas de traços finos (`hachura`), nunca cor
  chapada. É o que separa gravura de vetor.
- A tinta **encosta no papel**: aparece com `traco` correndo (a pena desenhando)
  ou `opacidade` subindo. Nada pisca, nada estoura, nada quica.

## As sete regras

**1. Uma folha só.** A cena inteira acontece na mesma prancha. Comece com uma
camada `textura` e desenhe por cima.

**2. O desenho acumula; o rótulo cede a vez.** Figura desenhada **permanece**
(só `inicio`). Texto de título e legenda recebe `fim`, senão dois títulos
imprimem um sobre o outro e a folha vira borrão.

**3. Tudo entra pela pena.** Contorno entra com `traco` de 0 a 1 em 0,7–1,3s.
Preenchimento e texto entram com `opacidade` em 0,2–0,7s. Nunca instantâneo.

**4. Escalone o que é irmão.** Quatro anéis não entram juntos: 0,30s entre um e
outro. Marcas de escala, 0,012s. Grade, use `repetir` com `atraso`.

**5. Um centro fixo.** O diagrama tem um ponto de origem e tudo orbita nele.
Escolha um (ex.: `x: 0, y: -120`) e repita em toda figura da mesma família.

**6. Vermelho é acento, não cor.** `#8F1D18` marca **uma** coisa por batida: a
anomalia, a região sob estudo, a chamada. Tudo mais é marrom (`#34281C`) ou
cinza (`#625847`).

**7. Título leva halo, e o halo é BORRADO.** Numa prancha gravada o texto não é
impresso em cima do desenho — o gravador deixa a região limpa e escreve ali.
Um `retangulo` na cor do papel claro (`#D8C092`) atrás do texto, com `raio` ≈
0,4× o tamanho da fonte e **`blur` ≈ 0,75× o tamanho da fonte**.

O `blur` não é enfeite: sem ele o halo lê como um retângulo claro colado atrás
do título — exatamente o defeito que ele deveria evitar. Dimensione a caixa a
partir da fonte, não a olho:

```
larg = maior_linha_em_caracteres × tamanho × 0.52 + tamanho × 1.1
alt  = numero_de_linhas × tamanho × 1.18 + tamanho × 0.55
```

**8. A prancha tem moldura.** Uma vez, no começo, e nunca sai: dois
`retangulo` concêntricos vazados (só `contorno`), um a ~54 px da borda e outro a
~66, com `traco` correndo em 1,6s. É o que faz o quadro ler como folha impressa
em vez de fundo. Se a cena é um bloco de uma peça maior, a moldura pertence ao
primeiro bloco.

## Paleta e tipografia

```
papel        #C7A978      papel claro (halo)  #D8C092
preto        #1E1A16      marrom (tinta)      #34281C
cinza        #625847      dourado             #90713F
vermelho     #8F1D18      vermelho escuro     #68120F

título        CormorantGaramond, peso 700, 90–130px, espacamento 4–8
rótulo        CormorantGaramond, itálico, 34–42px
```

## O vocabulário — o que usar para quê

| quero dizer | uso |
|---|---|
| "isto foi medido" | 3–4 `elipse` concêntricas + marcas de escala em volta + um ponto no centro |
| "esta região, especificamente" | `elipse` com `raio_int` + `de_grau`/`varre_grau` animado, com `hachura` radial |
| "olhe aqui" | `path` em cotovelo (`"M0,0 L-110,-110 L-200,-110"`) em vermelho |
| "isto se repete" | `repetir` com `atraso` |
| "um destes é diferente" | a mesma forma, em vermelho, fora do reticulado |
| "isto atravessa" | `linha` com `x` ou `y` animado de fora a fora |
| "dois lados" | `linha` vertical no eixo + as duas famílias, uma vazia e uma a buril |

### Marcas de escala

São `retangulo` finos (2×14) posicionados em círculo e rotacionados para
apontar ao centro. Como o `repetir` do DSL é uma **grade**, não um círculo, elas
são camadas explícitas — uma por marca, com `x`/`y` em cosseno/seno e
`rotacao` acompanhando o ângulo.

### Setor a buril

```json
{"tipo": "elipse", "raio": 430, "raio_int": 262, "de_grau": 152,
 "varre_grau": [[17.4, 0.5], [18.5, 74, "inOutCubic"]],
 "hachura": {"modo": "radial", "passo": 0.6, "cor": "#1E1A16",
             "opacidade": 0.9, "r0": 262},
 "opacidade": [[17.4, 0], [17.7, 1, "inOutCubic"]], "inicio": 17.35}
```

O `raio_int` **não** é decoração: arco não fechado sem ele vira segmento — a
corda liga as pontas e o preenchimento sai como lente, não como fatia. E a
hachura radial sem `r0` converge no centro e chapa tudo.

Depois do setor, contorne as duas bordas com `elipse` de mesmo `de_grau`/
`varre_grau` e `contorno_larg` 2.2. É o que dá o corte limpo da gravura.

## Armadilhas

- **`y` positivo sobe** na camada. Dentro de `path` e nos pontos `de`/`para` de
  `linha`, `y` positivo **desce** (convenção do Skia).
- **Easing vai no keyframe que COMEÇA o trecho.** No último ele é ignorado em
  silêncio.
- **`repetir` desloca o tempo local de todo valor animado.** Para mover uma
  grade inteira, embrulhe num `grupo` e anime o `x` do grupo — na própria grade,
  a deriva cisalha em vez de transladar.
- **Texto sem `fim` nunca sai.** Só o desenho acumula.

## Saída

Só o JSON. Sem cerca de código, sem comentário antes ou depois.

```json
{
  "duracao": 7.1,
  "camadas": [ ... ]
}
```
