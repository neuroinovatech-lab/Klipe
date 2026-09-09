# Klipe

Editor de vídeo local com timeline no navegador e motor próprio de motion
design em Python/Skia (MotionCore).

## Recursos

- Timeline multipista para vídeo, Motion B-roll, títulos, legendas e áudio
- Preview local e render final com MotionCore e FFmpeg
- Composição, tipografia cinética, zooms, transições e SFX
- Projetos isolados em `public/projects/<slug>`
- Integrações opcionais com Veo e Omni por chave configurada localmente
- Launchers para Windows e macOS

## Requisitos

- Node.js 20 ou mais recente
- Python 3.11
- FFmpeg e FFprobe

## Instalação

```bash
npm install
python -m pip install -r requirements.txt
npm start
```

Abra `http://127.0.0.1:3002` no navegador. No Windows, também é possível usar
`Iniciar Klipe.bat`. No macOS, use `Iniciar Klipe.command`.

## Primeiro projeto

O repositório não inclui vídeos nem projetos de clientes. Abra o Klipe, crie
um projeto e importe uma mídia local. Cada projeto recebe seu próprio
`edit_config.json`.

O editor trabalha em modo manual: as alterações só são gravadas ao clicar em
**Save** ou pressionar `Ctrl+S`.

## Arquivos locais

Vídeos, áudios, renders, caches, bancos, fontes de terceiros e configurações
com chaves não entram no Git. Eles permanecem na máquina dentro das pastas
locais do Klipe.

Fontes opcionais podem ser instaladas localmente em `public/fonts/`. Consulte
o arquivo nessa pasta antes de adicionar qualquer fonte.

## macOS

Instale as dependências com Homebrew e execute o launcher:

```bash
brew install node python ffmpeg
chmod +x "Iniciar Klipe.command"
./Iniciar\ Klipe.command
```

NVENC é exclusivo de GPUs NVIDIA. No macOS, o render usa os encoders
disponíveis no FFmpeg instalado.

## Licença

Este repositório é privado e não é software de código aberto. O acesso deve ser
concedido individualmente pelo GitHub. Consulte [LICENSE](LICENSE). Mídias,
marcas e fontes de terceiros continuam sujeitas às licenças de seus autores.
