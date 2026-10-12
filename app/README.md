# Klipe Desktop para Windows

O mesmo editor, projetos, timeline e MotionCore, em uma janela propria com icone.
Nao precisa abrir o navegador nem iniciar o servidor manualmente.

## Instalar e abrir

Execute `Instalar Klipe.bat`. O instalador prepara o editor, o WebView2 e gera o
executavel. Abra **Klipe Desktop** na area de trabalho ou `Klipe Desktop.bat`.
`Iniciar Klipe.bat` continua sendo a opcao de navegador.

Esta primeira versao usa o Klipe e suas dependencias na pasta instalada. O
`app/dist/Klipe.exe` e a janela desktop, nao um pacote offline completo. Nao
distribua apenas o executavel como se ele incluisse Node, Python, FFmpeg e os
modelos. O executavel ainda nao tem assinatura digital.

## Espaco de trabalho

O Desktop abre com menus **Arquivo**, **Editar**, **Exibir** e **Ferramentas**.
O motor de preview e render continua sendo o MotionCore; a interface nao muda
a resolucao ou o conteudo dos projetos.

- **Edicao:** biblioteca, monitor, propriedades e timeline.
- **Revisao:** esconde temporariamente os paineis laterais e amplia o monitor.
- Arraste as divisorias da biblioteca, das propriedades ou da timeline.
  As larguras e a altura ficam salvas localmente neste navegador/instalacao.
  As divisorias tambem aceitam foco pelo Tab e ajuste pelas setas.
- O botao no canto direito do monitor alterna o preview em tela cheia.
- **Exibir > Restaurar espaco de trabalho** volta ao layout inicial.
- **Interface antiga**, no topo, retorna ao layout anterior, sem recarregar
  nem salvar o projeto. Tambem fica em **Exibir > Interface classica**.
  O botao **Interface nova** permite voltar ao novo layout.
- Na aba **Video**, **Remover plano de fundo** abre a ferramenta antes chamada
  de **Recorte**. A geracao da mascara e a aplicacao na timeline nao mudaram.

Para experimentar no navegador, acrescente `?workspace=desktop` ao endereco
do projeto. A preferencia e local e pode ser diferente entre Desktop e navegador.
Nao edite o mesmo projeto em duas janelas ao mesmo tempo.

O tamanho minimo da janela Desktop e 960 x 640. Em janelas web menores, os
paineis laterais sao ocultados quando nao ha espaco para o monitor.
Ainda nao ha paineis destacaveis para outro monitor.

Os modos Edicao e Revisao tambem estao disponiveis na interface antiga.
Revisao oculta os paineis laterais; Edicao os restaura. Essa escolha muda
somente o espaco de trabalho, nao o projeto.

Em Propriedades > Video > Basico, Transformar agora inclui escala X/Y
vinculada ou independente, posicao, rotacao, ancora, inclinacao (pitch/yaw)
e espelhamento horizontal/vertical. Veja [Transformar](../docs/TRANSFORMAR.md).

## Processos e projetos

- Cada instancia desktop inicia seu proprio servidor em portas locais livres.
- Nao conecta a um programa desconhecido que ocupe a porta 3002.
- Ao fechar, encerra somente o servidor que iniciou e seus processos filhos.
- Um servidor ja aberto no navegador nao e encerrado pelo Desktop.
- Confirma antes de fechar com alteracoes nao salvas ou render Forge ativo.
- Save continua manual. Evite editar o mesmo projeto simultaneamente em duas janelas.
- Uma segunda janela desktop da mesma pasta e bloqueada.
- O servidor continua restrito ao proprio PC; esta versao nao e acesso pela rede.

O navegador integrado usa [pywebview/WebView2](https://pywebview.flowrl.com/api/).
Nao ha API Python de acesso a arquivos exposta ao JavaScript da pagina.

## Desenvolvimento

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/install-desktop.ps1
.venv-desktop/Scripts/python.exe app/klipe_app.py
```

Abrir uma instalacao/projeto especifico:

```powershell
app/dist/Klipe.exe --root C:\Klipe --project meu-projeto
```

O app procura a raiz pelo argumento `--root`, pela variavel `KLIPE_DIR`, nas
pastas acima do executavel ou no ultimo caminho salvo em `%APPDATA%/Klipe/app.json`.
O build nao encerra automaticamente nenhum Klipe aberto. Feche o executavel
antes de reconstruir, para nao travar o arquivo de destino.

O icone vem de `public/marca/klipe-mark.svg`, a mesma marca do editor. Para
atualizar suas sete resolucoes (16 a 256 px), execute com o Python principal:

```powershell
.venv/Scripts/python.exe app/generate_icon.py
.venv-desktop/Scripts/python.exe app/build_exe.py
```

O build inclui o ICO no executavel e na janela. Para testar sem substituir um
executavel aberto, use `app/build_exe.py --dist-dir app/dist/brand`.

## Testes e diagnostico

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py'
.venv-desktop/Scripts/python.exe app/klipe_app.py --smoke-test logs/desktop.json
```

O teste abre o WebView2, confere o DOM e encerra o servidor. Com `--project SLUG`,
tambem abre a janela visivel e verifica pixels do preview; grava JSON e PNG ao
lado do relatorio. Nao salva a timeline. Logs de erros ficam em
`%APPDATA%/Klipe/app.log` e `%APPDATA%/Klipe/logs/`.

Adicione `--smoke-close-test` para passar pelo fechamento normal (incluindo a
consulta de alteracoes), em vez de ignorar a protecao durante o teste. O
relatorio deve registrar `guardedClose: true` e `serverStopped: true`.

O build usa [PyInstaller](https://pywebview.flowrl.com/guide/freezing), em ambiente
isolado `.venv-desktop`, sem incluir bibliotecas pesadas do render na janela.
