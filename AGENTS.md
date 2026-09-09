# AGENTS.md

## Visão geral

Klipe é um editor de vídeo local com timeline no navegador e motor próprio de
motion design. Não depende de um serviço externo para preview ou render básico.

- `editor.html`: interface e estado da timeline.
- `editor-server.js`: servidor Node, APIs locais e processos de render.
- `motioncore/`: compositor MotionCore sobre Skia.
- `forge_render.py`: render final com FFmpeg e aceleração opcional.
- `public/projects/<slug>/edit_config.json`: estado de cada projeto.

## Execução

```bash
npm install
python -m pip install -r requirements.txt
npm start
```

Cada projeto abre em `/p/<slug>`. O repositório público começa sem mídias ou
projetos de clientes; use a interface para criar o primeiro projeto.

## Regras de edição

1. Trate cada projeto como isolado. Nunca grave o conteúdo de um slug em outro.
2. O salvamento é manual: somente o botão Save ou `Ctrl+S` escreve o projeto.
3. Preserve alterações que já estejam na timeline; não regenere o projeto todo
   para fazer uma mudança pequena.
4. Não reutilize automaticamente o estilo de outro vídeo. Composição,
   tipografia, ritmo e SFX devem seguir o conteúdo e a referência atual.
5. Preview e render precisam produzir a mesma composição e a mesma mixagem.
6. Mídia de um projeto distribuível deve morar dentro dele ou em bibliotecas
   públicas incluídas no pacote. Não deixe referências a projetos externos.
7. Não inclua chaves, bancos locais, caches, renders ou mídia pessoal no pacote.
8. Meça durações de mídia com FFprobe. Não estime duração de SFX ou vídeo.

## Verificação mínima

- Valide a sintaxe de `editor-server.js` com `node --check`.
- Confirme que o `edit_config.json` é JSON válido.
- Verifique que toda mídia referenciada existe.
- Abra o projeto, dê play e teste Save.
- Em mudanças de render, compare imagem e áudio do preview com a saída final.
