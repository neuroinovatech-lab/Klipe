# Assistente de edicao

Abra um projeto e entre em **IA > Assistente**. A analise usa a timeline atual,
incluindo alteracoes ainda nao salvas. Ela confere os arquivos com FFprobe e
sugere destaques, aproximacoes suaves e SFX da biblioteca local. As sugestoes
sao heuristicas locais, nao uma nova chamada de modelo de linguagem.

Selecione os itens desejados e aplique. Os titulos continuam editaveis, os sons
ficam na faixa SFX e os zooms na sua faixa. Uma acao Desfazer remove a aplicacao.
Use Save para gravar o projeto. Pausas ficam como pontos para revisao; nao ha
corte automatico de fala. O relatorio confere estrutura, nao substitui assistir
e ouvir o resultado.

## Visao opcional

Com Python 3.11, na raiz do Klipe:

```sh
python tools/setup_assistant_vision.py
```

Isso instala OpenCV e MediaPipe em `.venv-vision` e baixa o modelo Selfie
Multiclass diretamente do Google em `models/`. O ambiente principal de render
nao muda. Para usar outro ambiente, defina `KLIPE_VISION_PYTHON`.
Fonte do modelo e SHA-256 ficam em `models/selfie_multiclass.source.json`.

**Conferir rostos** amostra o video para sugerir uma faixa livre para os novos
titulos. A deteccao pode falhar em perfis, oclusoes e imagens pequenas. Fotos,
zooms e layouts complexos ainda precisam de conferencia visual.

**Recorte de pessoa** gera ate 30 segundos por vez, como camada transparente
na timeline. O video principal continua no projeto. A pessoa recortada aparece
acima dos titulos, permitindo texto atras do corpo. Confira cabelo e maos.
O trecho deve estar sem zoom, transformacao ou alteracao de velocidade; se
mudar essas propriedades depois, gere o recorte novamente. Nao ha promessa de
rotoscopia perfeita. Nao use uma mascara de uma tomada em outra.
Nesta versao, as duas analises visuais exigem uma fonte continua desde o
inicio, sem cortes nem deslocamento de origem. Projetos remontados recebem
um aviso em vez de resultados fora de sincronismo.

O preview e o render leem `brolls[].foreground`. A camada fica acima dos
titulos e abaixo das legendas. Desmarque **Acima dos titulos** nas propriedades
do B-roll para voltar a uma camada comum.

## Referencias da implementacao

Implementacao propria; nenhum codigo ou asset do EDIT-IA-PRO foi incorporado.
APIs de segmentacao: [MediaPipe Image Segmenter para Python](https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter/python).
Modelo: [catalogo oficial e cartao do modelo](https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter#multi-class_selfie_segmentation_model).
O instalador baixa dados do modelo, nao scripts externos.

## Verificacao

```sh
node --test tests/assistant.test.cjs
python -m unittest discover -s tests -p "test_assistant_render.py"
node --check editor-server.js
```
