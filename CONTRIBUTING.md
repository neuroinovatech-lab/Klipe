# Contribuindo com o Klipe

O Klipe é um produto proprietário. Contribuições são aceitas somente de pessoas
autorizadas a acessar o repositório.

## Fluxo

1. Crie uma branch curta a partir de `main`.
2. Mantenha a alteração limitada ao comportamento solicitado.
3. Execute as verificações locais.
4. Abra um pull request explicando impacto no preview, timeline e render.

```bash
npm run check
python -m compileall -q motioncore
```

## Regras importantes

- Não adicione vídeos, áudios, bancos, renders, chaves ou dados de clientes.
- Preserve o isolamento entre `public/projects/<slug>`.
- Preview e render devem manter composição e mixagem equivalentes.
- Alterações de timeline precisam preservar projetos já salvos.
- Use UTF-8 para textos em português.
- Inclua uma forma objetiva de verificar correções de render ou interface.

## Pull requests

Descreva o problema, a solução e os testes executados. Para mudanças visuais,
inclua capturas do antes e depois sem expor conteúdo privado.
