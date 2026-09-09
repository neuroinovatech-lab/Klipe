# Como pedir um vídeo novo

O que escrever para o pipeline montar uma peça. Quem consome isto usa
[PROMPT.md](PROMPT.md) (o estilo) e [DSL.md](DSL.md) (o formato).

A regra que decide a qualidade do resultado: **descreva o que a peça DIZ, não
como desenhá-la.** "Uma grade onde um quadrado sai do eixo" é o desenho, e
prende o resultado à sua primeira ideia. "Aqui ela fala que o cérebro flagra o
que foge do padrão" é o sentido — e daí sai a grade, o intruso e o anel que o
encontra, porque o vocabulário já sabe fazer isso.

---

## O que o pipeline PRECISA

**1. O vídeo de origem** — caminho e duração.

**2. As falas com tempo.** Vem da transcrição. Sem elas o texto na tela não
tem como estar ancorado no que ela realmente diz — e texto solto é a diferença
entre uma peça e um vídeo com legenda enfeitada.

**3. As batidas de conteúdo.** Onde cada ideia começa e acaba. Não é fatia de
relógio: é onde o assunto vira. Uma batida por ideia, tipicamente 4 a 14s.

## O que VOCÊ decide

**4. O mundo da peça.** Uma frase. É o que impede o resultado de sair genérico.

Se você quer um **visual novo**, descreva onde a coisa vive: "letreiro de
cinema", "manual técnico", "quadro tático". Se quer **continuar** uma peça
anterior, diga o nome dela — só assim o estilo antigo é carregado. Sem menção,
nada é herdado: um review de filme não puxa o papel envelhecido do vídeo sobre
percepção só porque ele veio antes.

Os estilos já formulados estão em [estilos/](estilos/), e cada um só entra
quando é chamado.

**5. Onde a imagem dela entra.** Nas batidas em primeira pessoa, o papel sai e
ela aparece. Escolha por conteúdo, não por relógio: onde ela fala de si.

**6. O que NÃO fazer.** Mais útil do que parece. "Nada de ícone", "sem cor fora
da paleta", "não cortar silêncio".

---

## Exemplo — projeto novo, sem herdar nada

Repare que o campo "mundo" descreve **onde a coisa vive**, e não cita nenhuma
peça anterior. Por isso nada do vídeo da prancha entra aqui.

> **Vídeo:** `projects/aranha-review/video.mp4`, 74s, 1080x1920.
> **Transcrição:** `projects/aranha-review/transcricao.json`.
>
> **Mundo:** sala de cinema à noite. Letreiro de marquise, luz de néon na
> parede, ingresso picotado, retícula de quadrinho impressa. Vermelho e azul
> sujos, como cartaz colado há uma semana. Nada de papel envelhecido nem
> serifa clássica — isto não é documentário.
>
> **Batidas:**
>
> | # | tempo | o que ele diz | o que a tela mostra |
> |---|---|---|---|
> | 1 | 0–8,0 | "fui ver esperando pouco e saí falando sozinho" | a marquise acende com o título |
> | 2 | 8,0–19,5 | elogia a ação e a câmera | os golpes marcados como painéis de quadrinho, um por vez |
> | 3 | 19,5–31,0 | o roteiro tropeça no meio | a retícula da impressão desalinha, sai de registro |
> | 4 | 31,0–43,0 | **"e aí veio a cena que me pegou"** | tudo apaga, sobra ele |
> | 5 | 43,0–56,0 | compara com os filmes anteriores | três ingressos lado a lado, um picotado |
> | 6 | 56,0–66,0 | a nota | o número aceso em néon na parede |
> | 7 | 66,0–74,0 | **"vale o ingresso?"** | volta pra ele, o letreiro apaga |
>
> **Imagem dele:** batidas 4 e 7 (a reação pessoal e a pergunta final).
>
> **Não fazer:** sem emoji, sem contador de nota girando, sem "SUBSCRIBE"
> piscando. O texto na tela só pode dizer o que ele disse. Não cortar silêncio.

---

## Som: biblioteca primeiro, gerar só no buraco

Numa edição com efeito sonoro, a ordem é sempre esta:

**1. Procure na biblioteca.** São 51 arquivos em `public/sfx/`, por categoria
(`whooshes`, `pop_click`, `writing`, `riser_synth`, `foley`…). Som gravado
ganha de som gerado em quase todo caso — textura, cauda, presença. Se existe um
que serve, é ele.

**2. Se não existe nada que sirva, gere.** O gerador vive fora do Klipe, em
`ferramentas/gerador_sfx/`, e é chamado por Configurações › Sons. Peça o som
pelo **contexto**, não pelo nome do arquivo: "porta de madeira rangendo
devagar" rende mais que "porta". Ele faz efeitos curtos — até 11s no modelo
pequeno.

**3. Ouça antes de usar.** Gerador erra bastante. O botão existe para você
julgar se serve, não para entrar direto na linha do tempo.

Três coisas que decidem se isso ajuda ou atrapalha:

- **O gerador nasce desligado**, e continua desligado até alguém ligar. Ele
  baixa gigabytes de modelo, e a maioria das edições não precisa dele.
- **Duração de SFX se MEDE com `ffprobe`**, gerado ou não. Chutar o tamanho é
  como o som entra cortado ou some antes da hora.
- **As categorias vazias são onde ele mais rende.** Hoje `ambience` está com
  zero arquivos, e `bass_drop`, `reverse` e `transition_sweep` com um cada.
  Ambiente (sala, rua, carro, silêncio de estúdio) é justamente o que modelo
  local faz bem e o que falta na biblioteca — comece por aí antes de tentar
  substituir o que já existe.

## O que sai disso

Uma cena por batida, validada pelo crítico antes de desenhar, renderizada em
camada com alpha — o vídeo dela continua na track principal e o motion é
independente, movível.

## Erros que custam caro

- **Batida grande demais.** Acima de ~15s a folha para de acontecer e o olho
  desiste. Divida.
- **Texto que ela não falou.** Quebra a peça inteira: a partir dali o
  espectador lê o texto como legenda, não como parte do que ela diz.
- **Mais de um acento por batida.** O vermelho marca UMA coisa. Duas, e nenhuma
  é lida.
- **Descrever o desenho em vez do sentido.** Prende o resultado à sua primeira
  ideia e desperdiça o vocabulário que já existe.
