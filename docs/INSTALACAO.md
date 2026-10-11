# Instalar o Klipe

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
- FFmpeg e FFprobe se estiverem faltando.
- Dependencias do editor pelo `package-lock.json` e um ambiente Python `.venv`.
- Remocao de fundo em `.venv-vision`, com o modelo oficial MediaPipe em `models/`.
- Atalho na area de trabalho e caminhos locais em `.klipe-runtime.json`.
- Janela Desktop com WebView2 e executavel gerado em `app/dist/Klipe.exe`.

Os pacotes Windows usam o [WinGet da Microsoft](https://learn.microsoft.com/en-us/windows/package-manager/winget/install),
com identificadores exatos e verificacao de integridade do gerenciador. O Node
pode pedir autorizacao do Windows. O instalador nao desativa antivirus nem muda
a politica de execucao permanente do PowerShell. Downloads usam internet; seus
videos nao sao enviados. A transcricao pode baixar seu modelo no primeiro uso.

O instalador reutiliza dependencias compativeis. Se for interrompido, execute-o
novamente. Ele nao apaga projetos, videos, renders ou configuracoes de edicao.
O tamanho e o tempo variam com os downloads e a conexao; reserve alguns GB livres.

## Abrir e atualizar

Use o atalho ou `Iniciar Klipe.bat`. O navegador abre somente depois de o servidor
responder. Mantenha a janela do Klipe aberta; `Ctrl+C` encerra o servidor iniciado
por ela. Portas ocupadas sao evitadas sem encerrar outros programas.

Antes de atualizar, salve e feche o Klipe e faca backup de `public/projects/`.
Atualize os arquivos do aplicativo e execute `Instalar Klipe.bat` novamente para
atualizar as dependencias. Nao substitua projetos por pastas vazias de um ZIP.

## Problemas comuns

- **WinGet nao encontrado:** instale/atualize o [Instalador de Aplicativo](https://aka.ms/getwinget)
  da Microsoft Store e execute novamente. Em PC corporativo, fale com o administrador.
- **Download bloqueado ou sem internet:** confira a conexao/proxy. O erro aparece
  na janela e em `logs/instalacao-*.log`; nao e necessario apagar seus projetos.
- **Editor nao abre:** veja `logs/servidor-*.err.log` e execute o instalador outra vez.
- **Pasta sem permissao:** extraia em uma pasta do seu usuario, fora de Program Files.
- **Aviso de seguranca:** esta versao nao tem assinatura digital. Confirme que o
  download veio do repositorio oficial; nao desative protecoes do Windows.

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
