# Atualizar o Klipe

## Botao dentro do editor

Em **Configuracoes > Atualizacoes**, clique em **Verificar atualizacoes**.
Se houver uma nova versao, salve seus projetos em todas as janelas e clique em
**Instalar atualizacao**. Aguarde a confirmacao, feche e abra o Klipe novamente.
Nao basta atualizar a pagina: o servidor tambem precisa reiniciar.

O botao consulta o repositorio oficial quando voce pede. Nao atualiza durante a
edicao, nao envia videos e nao salva ou recarrega projetos automaticamente.
Requer Git instalado, um clone oficial na branch `main` e codigo sem alteracoes
locais. Ele nao faz `reset`, `clean`, stash ou merge de conflitos.

Se a versao tambem mudar dependencias ou o executavel Desktop, o painel avisa
antes de modificar o codigo. Salve e feche **todos** os Klipes/servidores e abra
**Atualizar Klipe.bat**. Esse atualizador baixa o codigo e executa o instalador
para preparar dependencias, FFmpeg e Desktop. Aguarde **Atualizacao concluida**.
Se a instalacao falhar, o codigo pode ja estar atualizado; execute
`Instalar Klipe.bat` novamente antes de voltar a editar.

## Minha instalacao veio de ZIP

O ZIP nao tem historico Git. O botao informa isso sem tentar converter ou
sobrescrever sua pasta. Para habilitar futuras atualizacoes pelo botao:

1. Salve e feche o Klipe. Guarde uma copia de `public/projects/` e dos seus
   arquivos externos (fontes, musicas, videos e presets particulares).
2. Instale [Git for Windows](https://git-scm.com/downloads/win).
3. Peca ao seu agente para criar uma **nova pasta permanente**, clonar
   `https://github.com/neuroinovatech-lab/Klipe.git` e executar `Instalar Klipe.bat`.
4. Copie os projetos e dependencias pessoais para a nova instalacao, sem copiar
   `.git`, ambientes `.venv`, `node_modules` ou arquivos de codigo antigos.
5. Confira preview, Save e um render curto. Mantenha a pasta anterior ate validar.

Tambem e possivel continuar usando ZIP, com o procedimento de atualizacao
manual do [guia de instalacao](INSTALACAO.md).

## Protecoes e problemas comuns

- **Alteracoes locais:** o atualizador para. Seu agente deve revisar e guardar
  as mudancas; nao use comandos para apagar codigo so para liberar o botao.
- **Repositorio diferente ou historico divergente:** nao ha atualizacao automatica.
- **Render ativo:** espere terminar. Finalize tambem importacoes e recortes.
- **Sem internet:** tente novamente. Nao e necessario apagar projetos.
- **Queda de energia:** feche todas as instancias. Peca ao agente para conferir
  `git status`, o ultimo commit e `.klipe-update.lock`. Remova somente esse arquivo
  de trava depois de confirmar que nao existe atualizacao em execucao.
- **Voltar uma versao:** cada atualizacao guarda o commit anterior em
  `refs/klipe/backups/`. Peca ao agente para recuperar em outra pasta; nao ha
  rollback destrutivo automatico. Dependencias podem precisar ser reinstaladas.

`public/projects/`, configuracoes locais, fontes pessoais e ambientes ficam
fora da atualizacao. Atualizacoes que tentem gravar nessas areas sao recusadas.
Mantenha seus proprios backups: a referencia Git nao e backup de videos.

## FFmpeg 9.0.2

O instalador agora usa FFmpeg/FFprobe **9.0.2**, com download de versao fixa e
SHA256 conferido antes da extracao. Ficam em
`%LOCALAPPDATA%\Klipe\ffmpeg\9.0.2\bin`, separados de instalacoes anteriores.
O render foi adaptado para `-/filter_complex`, tambem compativel com 8.0.1.
H.264 NVENC usa explicitamente perfil High e formato yuv420p.

Quem ja atualizou o **codigo** pode salvar, fechar e executar
`Atualizar FFmpeg.bat`. Nao use o FFmpeg 9 com o render antigo: a opcao
`-filter_complex_script` foi removida nessa versao.

O atualizador guarda uma copia de `.klipe-runtime.json` antes de mudar os
caminhos. Para voltar, feche o Klipe e peca ao agente para restaurar os caminhos
anteriores desse backup; confira tambem o caminho em Configuracoes > Render
e variaveis `KLIPE_FFMPEG`/`KLIPE_FFPROBE`, que podem ter prioridade.
A instalacao anterior do FFmpeg nao e apagada.

Nos dois trechos Full HD de 12 segundos testados localmente, com cache quente,
RTX 5070 e H.264 NVENC High/CQ19, a mediana caiu aproximadamente **4% e 6%**.
Nao e garantia para outros projetos. Um dos arquivos ficou aproximadamente
**55% maior**; versao mais nova nao significa sempre arquivo menor ou GPU 100%.
