# Novidades do Klipe

[Apresentação](../README.md) · [Primeiros passos](PRIMEIROS-PASSOS.md) · [Instalação](INSTALACAO.md)

## Atualização de 11 de outubro de 2026

| Novidade | Para que serve | Onde usar |
| --- | --- | --- |
| Desktop Windows | Abre o Klipe em janela própria, sem depender de uma aba do navegador. | Atalho Klipe Desktop ou Klipe Desktop.bat |
| Marca oficial no Desktop | Usa o símbolo do editor na janela, no executável e no atalho, em múltiplos tamanhos. | Instalação atualizada do Desktop |
| Instalador integrado | Prepara Node, Python, FFmpeg, ambientes do editor, recorte e Desktop. | Instalar Klipe.bat |
| Fechamento sem bloquear a janela | Verifica alterações não salvas fora do evento que fecha a interface. Mantém o aviso antes de descartar alterações. | Botão de fechar do Desktop |

## Outros recursos recentes

- **Posição e escala no vídeo principal:** controles por clipe para reenquadrar em Propriedades → Vídeo → Básico.
- **Remover fundo em Propriedades:** o recurso fica em Vídeo → Recorte, junto ao clipe selecionado.
- **Dois modos de composição:** Remover cenário cria fundo e pessoa separados; Pessoa na frente dos títulos conserva o cenário e permite texto atrás do corpo.
- **Limpeza e suavidade:** ajustes de máscara com geração e aplicação explícitas. Alterar o ajuste exige gerar novamente.
- **Correções do preview:** sincronização do recorte com o vídeo, incluindo mudanças de tempo e proteção durante carregamento das camadas.
- **Pasta de render:** seleção pelo diálogo de pastas do sistema, com destino indicado no painel de exportação.
- **Edição assistida externa:** o chat permanece na conversa com o agente. O painel interno de assistente foi retirado do editor; as ferramentas locais continuam disponíveis.
- **Skill e AGENTS.md no repositório:** instruções para o agente preservar o projeto, manter elementos editáveis e conferir preview e render.

## O que não mudou

Save continua manual. O projeto editável precisa de configuração e mídias; MP4
é a entrega final, não um substituto da timeline. Desktop e navegador utilizam
o mesmo editor, e o navegador continua disponível.

O ZIP público não leva projetos de clientes. As ferramentas são implementações
do Klipe; não foi incorporado código ou assets do EDIT-IA-PRO.

## Limites desta versão

- Desktop disponível para Windows; macOS mantém o fluxo de navegador.
- O executável precisa da pasta instalada e de suas dependências. Ainda não há um instalador offline autossuficiente ou assinatura digital.
- Recorte automático não equivale a rotoscopia perfeita. Há restrições de timeline e de transformação descritas no guia de primeiros passos.
- Modelos e dependências exigem download na preparação; integrações com serviços externos têm configuração e condições próprias.
- Não há garantia de desempenho igual em todos os PCs nem de superioridade sobre Remotion em qualquer projeto.

Para atualizar, salve, feche e faça backup antes de seguir o
[passo a passo de atualização](INSTALACAO.md#abrir-e-atualizar).
