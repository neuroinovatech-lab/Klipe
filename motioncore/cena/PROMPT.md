# Prompt de geração — base

Instruções para emitir uma cena do DSL do MotionCore. Vale para **qualquer**
peça. O formato está em [DSL.md](DSL.md).

---

## Regra zero: nada é herdado

**O estilo vem do pedido, nunca do histórico.**

Existe uma pasta [estilos/](estilos/) com estilos já formulados. Eles só entram
quando o pedido chama por eles — porque nomeia (`"no estilo da prancha"`), ou
porque pede continuidade (`"a folha seguinte do mesmo caderno"`, `"igual ao
vídeo dos padrões"`).

**Sem esse chamado, não use nenhum.** Um pedido novo — review de filme,
tutorial, vídeo de produto, recap de futebol — é um projeto novo. Papel
envelhecido, tinta marrom e serifa editorial não têm nada a ver com o Homem-
Aranha, e enfiá-los ali não é coerência de marca: é o gerador impondo a última
coisa que fez.

O sintoma de que isso aconteceu é sempre o mesmo: a peça sai *competente e
errada*. Boa de execução, alheia ao assunto.

### Como saber se pode usar um estilo pronto

| o pedido diz | o que fazer |
|---|---|
| "no estilo da prancha", "como o vídeo X" | carregue aquele estilo |
| "continuação de X", "mesma série" | carregue, e trate as diferenças como decisão |
| não menciona referência nenhuma | **não carregue nada** — construa do assunto |

Na dúvida, **não herde**. Errar para o lado do genérico é reparável; errar para
o lado do estilo errado faz a peça parecer de outro vídeo.

### Como o motor aprende sem virar enviesado

O repertório precisa crescer — mas crescer em **repertório**, não em
**tendência**. São duas coisas diferentes e vão para lugares diferentes:

| o que se aprendeu | vai para | quando é usado |
|---|---|---|
| um visual novo que deu certo numa peça | `estilos/<nome>.md` | **só quando chamado pelo nome** |
| uma armadilha do motor (o `y` que sobe na camada e desce no path) | `DSL.md` | sempre |
| uma regra que faz qualquer motion funcionar | este arquivo | sempre |
| uma primitiva nova (hachura, textura, setor anular) | o DSL, em código | fica disponível a todos |

A distinção é simples de aplicar: **pergunte se aquilo seria verdade num vídeo
sobre outro assunto.** "Nada aparece do nada" é verdade em qualquer peça — é
regra. "Papel envelhecido com hachura de buril" só é verdade numa prancha — é
estilo, e vai para a pasta com nome próprio.

Um catálogo grande de estilos deixa o sistema mais capaz. Um estilo aplicado
sem pedido deixa o sistema pior — e a diferença entre os dois é exatamente esta
tabela.

---

## Construindo um mundo do zero

Quando não há estilo pedido, ele sai do **assunto**, não do seu repertório.
Três perguntas, nessa ordem:

**1. Onde essa coisa vive?** Um review de filme vive em cartaz, marquise, tela
de cinema, letreiro. Um tutorial vive em manual, seta, número de passo. Um
recap de futebol vive em placar, escalação, quadro tático. É daqui que sai o
vocabulário — não de "o que fica bonito".

**2. Qual é o material?** Papel, vidro, néon, plástico, tinta spray, LED,
metal. O material decide textura, cor e como as coisas entram. Peça sem
material escolhido é a que sai com cara de template.

**3. Qual é o gesto?** Como a coisa aparece: a pena correndo, o cartaz colando,
o letreiro acendendo, a nota adesiva grudando, o corte de tesoura. Um gesto por
peça, repetido — é ele que dá unidade.

Responda as três **antes** de escrever a primeira camada. Se não conseguir
responder, o briefing está raso: peça a referência que falta em vez de inventar.

## Regras que valem sempre

Estas não são estilo — são o que faz qualquer motion funcionar.

**Nada aparece do nada.** Toda camada entra por `opacidade`, `traco`, `escala`
ou deslocamento. Aparição instantânea lê como falha de render.

**Escalone o que é irmão.** Elementos iguais entrando juntos leem como um bloco
só. Com defasagem, leem como padrão.

**Um acento por batida.** Uma cor, um elemento, uma coisa que salta. Duas, e
nenhuma é lida.

**Nada assenta antes do fim.** Se toda animação termina antes do último frame,
o resto da peça é uma foto. Em faixa que divide tela com alguém falando, isso é
fatal — o olho resolve a parte parada e volta pro rosto.

**O texto na tela diz o que foi dito.** Texto que não sai da fala vira legenda
decorativa, e a peça perde a ancoragem.

## Antes de responder

1. `validar(cena)` tem que voltar vazio. Campo com nome errado é recusado e a
   mensagem diz qual era o certo.
2. Se um efeito que você quer não existir no DSL, **não invente campo**.
   Resolva com o que existe ou deixe de fora — campo inventado é ignorado em
   silêncio e o vídeo sai errado sem ninguém saber.
3. Releia a regra zero. Se você usou papel envelhecido num vídeo que não pediu
   papel envelhecido, comece de novo.

## Saída

Só o JSON. Sem cerca de código, sem comentário antes ou depois.
