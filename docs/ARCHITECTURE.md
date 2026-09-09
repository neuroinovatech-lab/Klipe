# Arquitetura do Klipe

## Fluxo principal

```text
Navegador
  editor.html
      |
      | HTTP local / JSON
      v
Servidor Node
  editor-server.js
      |-- projetos e configurações
      |-- importação e transcrição
      |-- preview do MotionCore
      `-- processos de render
              |
              v
Motor Python
  motioncore/ + forge_render.py
      |-- Skia: títulos, legendas e motion
      |-- FFmpeg: vídeo, áudio e composição
      `-- arquivo final
```

## Estado do projeto

Cada projeto vive em `public/projects/<slug>`. O arquivo `edit_config.json`
descreve mídia, cortes, B-rolls, zooms, títulos, legendas, SFX e música. A rota
`/p/<slug>` mantém a aba vinculada ao projeto correto.

## Preview e render

O player em `public/klipe_player.js` combina o vídeo principal com as camadas
da timeline. Títulos e legendas complexos são desenhados pelo MotionCore. O
render final usa os mesmos dados e finaliza a composição por FFmpeg.

## Limites de plataforma

- Windows: launcher completo e integrações nativas com Explorer e NVENC.
- macOS: editor, servidor, Skia e FFmpeg; integrações específicas do Windows
  podem exigir alternativas do sistema.
- Linux: os componentes centrais são portáveis, mas não há launcher oficial.

## Dados ignorados

Mídias, projetos locais, bancos, caches, renders, fontes e segredos não fazem
parte do histórico Git. Consulte `.gitignore` antes de adicionar novos ativos.
