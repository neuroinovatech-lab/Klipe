# Transformar o video principal

Selecione um clipe da trilha de video principal. Abra Propriedades > Video >
Basico. Os ajustes aparecem no preview e sao usados no render.

- Escala X/Y: 1 e o tamanho original. O elo vincula os eixos, preservando a
  proporcao atual. Desvincule para ajustar largura e altura separadamente.
- Posicao X/Y: deslocamento em pixels da composicao. X positivo vai para a
  direita; Y positivo, no painel, vai para cima.
- Rotacao: angulo em graus.
- Ancora X/Y: ponto de referencia, em pixels a partir do centro, para escala
  e rotacao. Mudar apenas a ancora nao desloca a imagem.
- Pitch/Yaw: inclinacao em perspectiva, em graus, de -60 a 60.
- Espelhar: botoes independentes para horizontal e vertical.
- A chave Transformar desativa o conjunto sem apagar os valores.
- A seta circular restaura todos os ajustes. Desfazer recupera a alteracao.

Save continua manual. Os valores persistem ao salvar e reabrir. Sao ajustes
fixos por clipe; estes controles nao adicionam keyframes.

Arraste horizontalmente sobre um numero para ajustar com preview imediato.
Shift durante o arraste reduz a velocidade; Ctrl aumenta. Cada arraste e uma
unica etapa de Desfazer. Um clique permite digitar; as setas do campo e do
teclado continuam disponiveis. Os valores respeitam os limites do controle.

O botao Ir nao aplicava os ajustes: apenas movia o cursor ao inicio do clipe.
Ele foi retirado das propriedades do video principal. Nos outros tipos de
clipe, aparece como Ir ao inicio.

## Camadas e recorte

Transformar afeta somente o clipe principal selecionado. Titulos e B-rolls
sobrepostos mantem seus proprios ajustes; uma camada opaca pode cobrir o
resultado. Nao transforma automaticamente um recorte de pessoa separado.

A geracao de remocao de fundo requer video sem transformacoes ativas, zoom
ou alteracoes de velocidade. Desative/restaure Transformar antes de gerar.
Depois, mantenha os ajustes da pessoa recortada e do fundo alinhados.

## Render

Projetos antigos que usam apenas escala unica continuam compativeis.
Rotacao e perspectiva usam filtros FFmpeg de composicao; podem aumentar o
trabalho da CPU mesmo com codificacao por GPU. O preview WebGL e o render
foram comparados com frames sinteticos; pequenas diferencas de interpolacao
e cor entre os dois motores sao esperadas.
