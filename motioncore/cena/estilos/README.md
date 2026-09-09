# Estilos

Catálogo de visuais já formulados. **Nenhum é usado por padrão** — cada um só
entra quando o pedido o chama pelo nome ou pede continuidade de uma peça que o
usa. Ver a regra zero em [../PROMPT.md](../PROMPT.md).

| estilo | mundo | quando pedir |
|---|---|---|
| [prancha-gravada](prancha-gravada.md) | prancha científica do século XIX — papel envelhecido, tinta marrom, buril, serifa editorial | assunto expositivo, conceito abstrato, "explicar como funciona" |

## Título ou template? A pergunta é quantos textos ele tem

Um motion que deu certo pode ser guardado de duas formas, e escolher errado
gera frustração dos dois lados: título que não aceita o conteúdo, ou template
que ninguém consegue adaptar.

| o motion tem | vira | por quê |
|---|---|---|
| **um texto**, e o resto é moldura | **título** (`style: "cena"`) | o desenho é fixo, o texto é a variável — troca no painel e serve qualquer assunto |
| **muita coisa**: lista, vários textos com tempos próprios, elementos que entram um a um | **template** | não existe "o texto" para trocar; o que se reaproveita é o arranjo inteiro |

O teste é direto: **dá para trocar o texto e a peça continuar fazendo sentido?**
Se sim, é título. Se trocar um texto obrigaria a mexer em tempo, altura e nos
outros textos, é template.

Exemplo real, da mesma peça: o **selo** ("Não existe receita de bolo") é uma
frase numa moldura — título. A **ficha das quatro perguntas** tem quatro itens
que aterrissam em segundos diferentes, com o cartão crescendo junto — template.
Tentar transformar a ficha em título produziria um cartão com as quatro
perguntas empilhadas no mesmo instante, que não é a peça.

### E só entra o que for bom mesmo

Nem todo motion que funcionou merece virar biblioteca. Catálogo grande de coisa
mediana é pior que catálogo pequeno de coisa boa: aumenta o que se precisa
olhar antes de escolher, e nada ali resolve nada.

**Nada é salvo automaticamente.** Nem ao salvar o projeto, nem ao renderizar.
Só quando alguém pedir, explicitamente, para aquele motion virar estilo — o
mesmo espírito da regra zero em [../PROMPT.md](../PROMPT.md): o repertório
cresce por decisão, não por acúmulo.

## Como um estilo entra aqui

Quando uma peça estabelece um visual que valeu a pena, ele vira um arquivo
nesta pasta. O que precisa estar escrito, aprendido daquela peça:

1. **O mundo em uma frase** — e o que ele NÃO é (a comparação corta mais que a
   definição: "não é infográfico, não é slide").
2. **As regras que sustentam o look**, numeradas. Não descrições vagas:
   "escalone 0,30s entre anéis irmãos" vale mais que "use entrada suave".
3. **Paleta e tipografia**, com os valores exatos.
4. **Uma tabela "quero dizer X → uso Y"** — é o que transforma sentido em
   desenho sem prender à primeira ideia.
5. **As armadilhas específicas daquele estilo**, com o porquê. Não a proibição
   sozinha: o motivo é o que faz a regra sobreviver ao próximo caso.

Cada estilo novo deixa o sistema mais capaz **sem** deixá-lo mais enviesado —
porque ele fica esperando ser chamado, não ligado por padrão.

## Como testar um estilo novo

O mesmo teste que validou a prancha: pegue uma peça já pronta naquele estilo,
descreva-a pelo **sentido** (não pelo desenho), gere, e compare com a original.

Na prancha isso deu 49 camadas contra 49 reais, com o vocabulário batendo
(elipses 7=7, arcos 7=7, hachura 1=1). As três diferenças eram lacunas do texto
do estilo — faltavam a moldura, o ponto central e o `blur` do halo — e viraram
regra escrita. É esse ciclo que faz o estilo ficar bom: o que o teste acha
vira linha, e a próxima geração já nasce com ela.
