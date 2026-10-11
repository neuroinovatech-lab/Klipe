# Assistente de edicao

A edicao assistida acontece na conversa com Codex ou Claude Code, com acesso
local ao projeto. Nao ha painel de assistente dentro do editor.
As ferramentas locais de analise e recorte continuam disponiveis para o agente.

Salve as alteracoes da timeline antes de uma analise baseada no arquivo.
`POST /api/assistant/analyze` recebe `{config, faces: false}` e o header
`X-Projeto` com o slug. Consulte `/api/assistant/job?id=...` para o resultado.
A analise e somente leitura: confere midias com FFprobe e sugere destaques,
zooms e SFX por regras locais, sem outra chamada de modelo de linguagem.
O agente deve revisar as sugestoes antes de alterar o projeto e preservar os
titulos, sons e zooms como clips editaveis. Save continua manual.
Pausas sao pontos para revisao, nao cortes automaticos. O relatorio estrutural
nao substitui assistir e ouvir o resultado.

## Visao opcional

O instalador Windows inclui este modulo por padrao. Dentro do editor, selecione
o video principal e abra **Propriedades > Video > Recorte**. Escolha o modo,
o intervalo, limpeza e suavidade; clique **Gerar recorte**, aguarde e use
**Aplicar na timeline**. Confira o resultado e use **Save** para salvar.

- **Remover cenario:** cria uma camada de fundo e outra de pessoa recortada.
  Sao separadas de proposito para permitir trocar o fundo e manter a pessoa.
- **Pessoa na frente dos titulos:** cria apenas a pessoa recortada e preserva
  o cenario original por baixo dos titulos.

O painel divide intervalos de ate 10 minutos em tarefas de ate 30 segundos.
Os ajustes nao sao ao vivo: gere novamente depois de modifica-los. Cancelar
aguarda o trecho atual terminar e nao altera a timeline. O processamento e local.

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
