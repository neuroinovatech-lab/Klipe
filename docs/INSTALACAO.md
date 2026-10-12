# Instalar o Klipe

[Voltar](../README.md) · [Primeiro video](PRIMEIROS-PASSOS.md) · [Novidades](NOVIDADES.md)

No Windows, o caminho mais simples e baixar o ZIP e executar o instalador.
Nao e preciso saber programar, instalar Conda ou copiar comandos para comecar.
Use Windows 10/11 de 64 bits, internet, WinGet e alguns GB livres para os
programas, modelos e arquivos temporarios. Videos e renders exigem espaco extra.

## Windows: dois cliques

1. Baixe o [ZIP oficial](https://github.com/neuroinovatech-lab/Klipe/archive/refs/heads/main.zip).
2. Extraia o ZIP inteiro para uma pasta permanente e gravavel, como `Documentos\Klipe`.
3. Abra `Instalar Klipe.bat`, leia o resumo e confirme com **S**.
4. Espere a mensagem **Pronto**. Abra **Klipe Desktop** na area de trabalho.
   O atalho **Klipe** continua disponivel para usar o navegador.

Nao execute de dentro do ZIP. Nao mova a pasta depois: os ambientes Python e o
atalho guardam caminhos absolutos. Para outra maquina, baixe uma copia limpa e
execute o instalador nela; transfira projetos separadamente.

## O que e instalado

- Node.js 22 se nao houver um Node compativel (22 ou mais novo).
- Python 3.11 se nao houver uma instalacao compativel.
- FFmpeg e FFprobe 9.0.2 em pasta propria, com SHA256 verificado; versoes anteriores sao preservadas.
- Dependencias do editor pelo `package-lock.json` e um ambiente Python `.venv`.
- Remocao de fundo em `.venv-vision`, com o modelo oficial MediaPipe em `models/`.
- Atalho na area de trabalho e caminhos locais em `.klipe-runtime.json`.
- Janela Desktop com WebView2 e executavel gerado em `app/dist/Klipe.exe`.

Node e Python usam o [WinGet da Microsoft](https://learn.microsoft.com/en-us/windows/package-manager/winget/install),
com identificadores exatos. FFmpeg usa um pacote fixo de gyan.dev, com SHA256
registrado em `tools/ffmpeg-release.json` e conferido antes de extrair. O Node
pode pedir autorizacao do Windows. O instalador nao desativa antivirus nem muda
a politica de execucao permanente do PowerShell. Downloads usam internet; seus
videos nao sao enviados. A transcricao pode baixar seu modelo no primeiro uso.

O instalador reutiliza dependencias compativeis. Se for interrompido, execute-o
novamente. Ele nao apaga projetos, videos, renders ou configuracoes de edicao.
O tamanho e o tempo variam com os downloads e a conexao; reserve alguns GB livres.

## Abrir e atualizar

**Novo:** em clones Git oficiais, use **Configuracoes > Atualizacoes**.
Para versoes que alterem dependencias/Desktop, use **Atualizar Klipe.bat**
com o aplicativo fechado. [Passo a passo, ZIP e recuperacao](ATUALIZACOES.md).

**Desktop:** use **Klipe Desktop** ou `Klipe Desktop.bat`. Ele abre a janela e
inicia seus processos locais. Salve antes de fechar. Fechar durante um render
pode cancela-lo; espere a exportacao terminar.

**Navegador:** use **Klipe** ou `Iniciar Klipe.bat`. O navegador abre depois de o
servidor responder. Mantenha a janela do servidor aberta; `Ctrl+C` encerra o
servidor iniciado por ela. Portas ocupadas sao evitadas sem fechar outros apps.

Nao edite o mesmo projeto em duas janelas ao mesmo tempo. Nao e necessario
instalar uma extensao de navegador para usar o editor.

Antes de atualizar, salve e feche o Klipe e faca backup de `public/projects/`.
Atualize os arquivos do aplicativo e execute `Instalar Klipe.bat` novamente para
atualizar as dependencias. Nao substitua projetos por pastas vazias de um ZIP.

Se voce nao usa Git, uma forma de preservar a instalacao anterior e:

1. Salve, feche e copie `public/projects/` para um backup fora da instalacao.
2. Baixe o ZIP atualizado e extraia em outra pasta permanente, como `Documentos\Klipe-atualizado`.
3. Execute `Instalar Klipe.bat` nessa nova pasta. O atalho passara a apontar para ela.
4. Copie suas pastas de projeto para `public/projects/` da nova instalacao. Confira tambem dependencias externas, como fontes e musicas, conforme o guia de primeiros passos.
5. Abra um projeto e confira preview, Save e um render curto antes de descartar a instalacao anterior.

Nao copie ambientes `.venv`, `node_modules` ou apenas `app/dist/Klipe.exe` para
substituir a instalacao em outro PC. Cada maquina deve executar o instalador.

## Problemas comuns

- **WinGet nao encontrado:** instale/atualize o [Instalador de Aplicativo](https://aka.ms/getwinget)
  da Microsoft Store e execute novamente. Em PC corporativo, fale com o administrador.
- **Download bloqueado ou sem internet:** confira a conexao/proxy. O erro aparece
  na janela e em `logs/instalacao-*.log`; nao e necessario apagar seus projetos.
- **Editor nao abre:** veja `logs/servidor-*.err.log` e execute o instalador outra vez.
- **Pasta sem permissao:** extraia em uma pasta do seu usuario, fora de Program Files.
- **Aviso de seguranca:** esta versao nao tem assinatura digital. Confirme que o
  download veio do repositorio oficial; nao desative protecoes do Windows.
- **Desktop ja aberto:** procure a janela na barra de tarefas. O app impede duas instancias Desktop da mesma pasta.
- **Erro ao atualizar o executavel:** salve e feche o Desktop antes de executar o instalador. O build nao encerra editores abertos automaticamente.
- **Desktop travou ao fechar:** atualize para a versao com fechamento assincrono; houve uma correcao especifica desse problema. Antes de forcar o encerramento, considere alteracoes nao salvas.

Logs do Desktop ficam em `%APPDATA%/Klipe/app.log` e `%APPDATA%/Klipe/logs/`.
Cole `%APPDATA%/Klipe` na barra de endereco do Explorador de Arquivos para
encontrar essa pasta. Logs de instalacao ficam em `logs/` dentro do Klipe.
Revise dados pessoais antes de compartilhar qualquer log.

## Opcoes avancadas

Diagnosticar programas disponiveis sem instalar ou gravar configuracao:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/install-windows.ps1 -CheckOnly
```

Instalar sem o modulo opcional de remocao de fundo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/install-windows.ps1 -SkipVision
```

`-Yes` confirma os downloads sem a pergunta inicial. Sem `-SkipVision`, o recorte
e instalado por padrao. O modo sem recorte mantem a edicao e o render basico.
`-NoShortcut` evita criar/substituir o atalho, util em testes. Para testar a
inicializacao sem abrir o navegador e encerrar ao concluir, execute
`powershell -NoProfile -ExecutionPolicy Bypass -File tools/start-windows.ps1 -SmokeTest`.
`-SkipDesktop` mantem apenas a versao de navegador. O modulo Desktop pode ser
instalado depois com `tools/install-desktop.ps1`. Feche o Desktop antes de atualizar.

## macOS

O instalador automatico desta versao e para Windows. O Mac continua com o fluxo
documentado no [README](../README.md#macos); nao execute os arquivos `.bat` nele.
