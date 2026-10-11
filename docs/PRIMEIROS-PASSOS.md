# Seu primeiro vídeo no Klipe

[Voltar à apresentação](../README.md) · [Instalar](INSTALACAO.md) · [Novidades](NOVIDADES.md)

Este guia é para quem nunca usou o Klipe. Comece com um vídeo curto de teste e
guarde o original. Você não precisa usar todos os efeitos de uma vez.

## 1. Instalar e abrir

No Windows, baixe o [ZIP oficial](https://github.com/neuroinovatech-lab/Klipe/archive/refs/heads/main.zip),
extraia tudo e abra **Instalar Klipe.bat**. Confirme com **S** e espere a mensagem
de conclusão. A primeira instalação usa internet e pode demorar por causa dos
downloads. Não feche a janela enquanto ela estiver trabalhando.

Depois, escolha uma forma de abrir:

| Opção | O que acontece |
| --- | --- |
| **Klipe Desktop** ou **Klipe Desktop.bat** | Abre o editor em uma janela própria. Inicia seus processos locais automaticamente. |
| **Klipe** ou **Iniciar Klipe.bat** | Abre no navegador. Mantenha a janela do servidor aberta enquanto edita. |

As duas opções usam o mesmo editor e os projetos da mesma instalação. Evite
editar o mesmo projeto nas duas ao mesmo tempo: uma gravação pode substituir
a outra. Não mova a pasta depois de instalar e não envie somente o `.exe` para
outro PC. Consulte [instalação e atualização](INSTALACAO.md) para mais detalhes.

## 2. Criar um projeto

1. Clique em **Novo**, na barra superior.
2. No campo **Slug do projeto**, escreva um nome como `video-da-cliente`. Slug é apenas o nome da pasta: use letras, números e traços, sem espaços ou acentos.
3. Em **Vídeo principal**, selecione o arquivo do seu computador. Você também pode criar sem vídeo e importar depois.
4. Sem vídeo, escolha o formato: **9:16** para vertical, **16:9** para horizontal, **1:1** para quadrado ou **4:5** para retrato. Com vídeo, o Klipe detecta suas dimensões.
5. Clique em **Criar** e aguarde o carregamento.
6. Dê **Play** para conferir imagem e som. Confira o formato do projeto antes de começar os efeitos.

O projeto fica em `public/projects/video-da-cliente/`, dentro da pasta do Klipe.
O endereço `/p/video-da-cliente` abre essa edição enquanto o servidor estiver
ligado. Um link `127.0.0.1` funciona no próprio computador, não no PC de uma cliente.

## 3. Entender a tela

| Nome na edição | Significado |
| --- | --- |
| **Preview** | A imagem que você está conferindo. Ainda não é um arquivo exportado. |
| **Timeline** | A linha do tempo na parte de baixo. Cada bloco ocupa um intervalo do vídeo. |
| **Trilha** | Uma linha da timeline, usada para organizar vídeos, títulos ou áudio. |
| **Clipe** | Um bloco de vídeo, texto, imagem ou som. Clique nele para editar suas propriedades. |
| **Propriedades / Properties** | Painel que muda conforme o item selecionado. |
| **B-roll** | Imagem ou vídeo de apoio, além do vídeo principal. |
| **Motion B-roll** | Elemento visual animado, como uma composição com textos e gráficos. |
| **Render** | Processo que junta as camadas e cria o arquivo final. |

Se um controle não aparecer, confira primeiro qual clipe está selecionado.
Mova o marcador de tempo para dentro do intervalo do efeito para enxergá-lo.

## 4. Cortar, reenquadrar e dar movimento

Selecione o vídeo principal na timeline. Em **Propriedades → Vídeo → Básico**,
use **Posição X**, **Posição Y** e **Escala** para ajustar seu enquadramento.
X move para os lados; Y move na vertical; escala aumenta ou diminui a imagem.
Confira se o rosto continua dentro do quadro.

Posição e escala definem o enquadramento do clipe. Para uma aproximação que
acontece ao longo do tempo, use os recursos de **Zoom** e confira a animação
com Play, não apenas com o vídeo pausado. Comece com movimentos discretos.

Para cortes, use a área **CUT** e confira o áudio antes e depois da emenda.
Retire silêncio de início sem cortar a primeira palavra. Transições ajudam na
passagem entre trechos, mas não substituem um corte bem posicionado.

## 5. Textos, legendas, imagens e áudio

- **Títulos e templates:** use as ferramentas de texto/template para adicionar um elemento; selecione o bloco na timeline para ajustar texto, duração e estilo em Propriedades.
- **Legendas:** confira a transcrição, principalmente nomes próprios. Uma legenda que já veio gravada dentro do vídeo não é texto editável do Klipe.
- **Imagens e B-roll:** importe material de apoio e ajuste o intervalo, enquadramento e movimento. Em vídeo vertical, confira se a foto não ficou cortada e se não cobre o rosto.
- **Motion B-roll:** use composições animadas disponíveis ou peça uma composição personalizada ao agente. Confira textos e elementos no tamanho final do vídeo.
- **Música e SFX:** SFX são efeitos sonoros. Ajuste o volume para que a fala permaneça compreensível; ouça as transições com fones antes de entregar.

Mantenha títulos afastados das bordas. Fotos precisam de enquadramento adequado
à área em que aparecem; não presuma que uma imagem horizontal cabe em qualquer
layout vertical. Recursos personalizados feitos por código podem exigir ajustes
do agente além dos controles de texto da interface.

## Remover fundo e colocar texto atras da pessoa

Selecione o **vídeo principal** e abra **Propriedades → Vídeo → Recorte**.
Não há necessidade de um painel de chat dentro do editor para usar esse botão.

| Modo | Resultado |
| --- | --- |
| **Remover cenário** | Cria uma camada de fundo e outra da pessoa recortada. As duas camadas são intencionais: permitem trabalhar no fundo separadamente. |
| **Pessoa na frente dos títulos** | Mantém o cenário original e coloca a pessoa recortada acima dos títulos, criando a aparência de texto atrás do corpo. |

1. Escolha o modo e preencha **Início (s)** e **Fim (s)**. Para experimentar, use primeiro um trecho de poucos segundos.
2. Comece com os ajustes padrão de **Limpeza da máscara** e **Suavidade da borda**.
3. Clique em **Gerar recorte** e aguarde a conclusão.
4. Clique em **Aplicar na timeline**. Gerar sozinho ainda não insere as camadas na edição.
5. Dê Play e confira cabelo, mãos, roupas, microfones e o começo/fim do trecho.
6. Clique em **Save** para guardar a alteração. Use `Ctrl+Z` se quiser desfazer a aplicação.

**Máscara** é a região que define o que fica visível. Limpeza ajusta o recorte;
suavidade amacia a borda. Valores mais altos não significam necessariamente um
resultado melhor: podem apagar detalhes ou deixar contornos suaves demais.
Depois de alterar esses ajustes, gere novamente; eles não mudam o recorte ao vivo.

Para texto atrás da pessoa, adicione um título no mesmo intervalo do recorte.
A pessoa deve cobrir parte do texto; se o título estiver longe dela, o efeito
de profundidade pode não ficar evidente. Legendas ficam acima da pessoa recortada.

**Limites importantes:** o recorte é automático e pode falhar, especialmente em
cabelo, mãos, objetos e microfones. Nesta versão, o processamento visual exige
uma fonte contínua desde o início, sem cortes ou deslocamento de origem, e o
trecho sem zoom, transformação ou mudança de velocidade. Projetos incompatíveis
recebem um aviso. Faça o teste de recorte antes de remontar a timeline; se mudar
essas condições, reavalie a compatibilidade e gere novamente.

O painel aceita intervalos de até 10 minutos, divididos em tarefas de até
30 segundos. Cancelar aguarda o trecho atual terminar. Se a timeline mudar entre
gerar e aplicar, será necessário gerar de novo para preservar o sincronismo.
O processamento é local; o modelo é baixado durante a preparação do módulo.

## 6. Salvar o trabalho

Clique em **Save** ou pressione `Ctrl+S`. Espere a confirmação. O salvamento é
manual: ver o resultado no preview não garante que ele foi salvo.

**Salvar projeto** guarda a timeline e suas referências de mídia.
**Renderizar** cria o vídeo para assistir ou publicar. Para continuar editando
em outro dia, preserve a pasta do projeto, não apenas o MP4 final.

O Desktop avisa ao fechar com alterações não salvas ou render Forge em andamento.
Se estiver salvando, espere terminar. Esse aviso não substitui um backup e não
protege contra queda de energia. Salve com frequência.

## 7. Exportar o MP4

1. Revise o preview e clique em **Save**.
2. Clique em **Render**, na barra superior.
3. Confira as opções de saída disponíveis. Para o primeiro teste, mantenha os padrões antes de experimentar configurações avançadas.
4. Em pasta de destino, use **Escolher** para selecionar onde guardar o vídeo. Confira o nome do arquivo.
5. Clique em **Iniciar Render** e aguarde a conclusão. Não feche o Desktop ou o servidor durante a exportação.
6. Abra o arquivo final e confira começo, meio e fim: títulos, recorte, transições, fala e música.

O tempo depende do PC, duração, resolução, efeitos e cache. Um arquivo pequeno
não prova que faltaram títulos: tamanho também depende da compressão. Assista ao
arquivo final. Se houver diferença para o preview, guarde o erro e o tempo exato
do problema antes de tentar novamente.

## 8. Enviar um projeto editável para outra pessoa

1. Salve e feche o projeto antes de copiar os arquivos.
2. Copie a pasta inteira `public/projects/nome-do-projeto/`, incluindo `edit_config.json` e suas mídias.
3. Confira se o projeto usa fotos, sons, fontes ou outros arquivos fora dessa pasta. Inclua os arquivos necessários e ajuste referências com ajuda do agente; copiar só a pasta não resolve dependências externas automaticamente.
4. Compacte a pasta em ZIP. A pessoa instala o Klipe separadamente, extrai a pasta do projeto dentro de `public/projects/` da instalação dela e abre o projeto pelo nome.
5. Confira o preview no outro PC antes de considerar a entrega pronta. Para um estilo personalizado, inclua instruções em `AGENTS.md` e a versão do Klipe utilizada.

Enviar só o MP4 permite assistir, mas não editar separadamente títulos, efeitos
e camadas. Não envie sua instalação inteira com configurações, chaves ou bancos
privados. Fontes e arquivos de terceiros podem ter restrições de distribuição.

## Ajuda na conversa

O chat do agente fica fora do editor. Você pode editar manualmente ou pedir ajuda
na conversa de um agente que tenha acesso aos arquivos locais. O Klipe não inclui
assinatura de Codex/Claude nem configura acesso a esses serviços por você.

Um pedido inicial útil:

> Leia o AGENTS.md e a skill do Klipe neste repositório. Trabalhe no projeto
> public/projects/meu-video. Preserve minha edição e não renderize ainda.
> Adicione um título editável entre 3 e 6 segundos, sem cobrir o rosto.
> Confira no preview e me diga o que mudou.

Salve antes de pedir alterações nos arquivos e evite editar simultaneamente com
o agente. O [guia técnico de edição assistida](ASSISTENTE.md) explica as ferramentas
locais e seus limites. Não há um botão de assistente interno a ser ativado.

## Duvidas frequentes

| Problema | O que conferir |
| --- | --- |
| Abriu sem os vídeos do demo | É esperado: o repositório público não traz projetos particulares. Crie seu projeto e importe seu vídeo. |
| O efeito não aparece | O marcador de tempo está dentro do bloco? A trilha está visível? Há outra camada cobrindo o efeito? |
| Save falhou | Não feche nem recarregue a página. Confira se a pasta é gravável e se outro programa está usando o arquivo. Guarde a mensagem de erro. |
| Recorte não pode ser aplicado | Espere gerar e veja se a timeline mudou. Se mudou, gere novamente. |
| O fundo sumiu, mas surgiram duas trilhas | É o comportamento do modo Remover cenário: fundo e pessoa separados. |
| Ficou uma borda estranha | Teste limpeza e suavidade em um trecho curto. Nem toda tomada dá um bom recorte automático. |
| Não consigo corrigir uma legenda | Confira se ela é um elemento do projeto ou se já está gravada no vídeo original. |
| Render falhou | Anote o erro, confira espaço, destino gravável e existência das mídias. Veja também o guia de instalação. |
| Desktop não abre | Confira se a pasta da instalação não foi movida. Execute o instalador novamente; não apague seus projetos. |
| A janela travou | Não force o encerramento antes de avaliar alterações não salvas. Registre o que fez e veja os logs indicados no guia de instalação. |

Ao pedir ajuda, informe Windows/macOS, Desktop/navegador, o que clicou, a mensagem
de erro e uma captura da tela. Não publique vídeos de clientes, chaves ou logs
com dados pessoais em uma issue pública.
