# Klipe — app de desktop e modo web

Duas portas de entrada pro **mesmo** Klipe, no mesmo servidor e na mesma porta.
Não existe "versão app" e "versão web" — existe o Klipe, e duas formas de olhar
pra ele. Os projetos, o cache de render e o login são os mesmos nos dois.

| | como abre | quando usar |
|---|---|---|
| **App** | `Klipe.exe` | dia a dia. Janela própria, ícone na barra, sem barra de endereço, sem console preto. |
| **Web** | `Klipe Web.bat` | quando quiser abrir do celular ou de outro PC da rede — o `.bat` mostra o endereço. |

Se você abrir o modo web primeiro e depois o app, **o app se pluga no servidor
que já está de pé** em vez de subir outro. E nesse caso, fechar a janela não
derruba nada — quem é dono do servidor é quem o subiu.

## Gerar o exe

```bash
python app/build_exe.py
```

Sai em `app/dist/Klipe.exe` (~15 MB). Pode copiar pra qualquer lugar ou fazer
atalho na área de trabalho.

Duas coisas que o exe **não** empacota, de propósito:

- **Navegador.** Usa o WebView2 que já vem no Windows. É por isso que são 15 MB
  e não 200.
- **O Klipe.** Ele abre o `editor-server.js` que está na pasta do projeto —
  então mexer no editor continua valendo na hora, sem recompilar o exe.

## Onde ele procura a pasta do projeto

Nesta ordem: variável `KLIPE_DIR` → ao lado do exe → pastas acima → o que ficou
salvo da última vez. Se não achar nada, pergunta uma vez e guarda em
`%APPDATA%/Klipe/app.json`.

Ou seja: se você deixar o exe dentro da pasta `motionforge`, ele acha sozinho.
Se levar pra área de trabalho, ele pergunta na primeira abertura e não pergunta
mais.

## Se o exe abrir e sumir

Ele grava tudo em **`%APPDATA%\Klipe\app.log`** — abra esse arquivo primeiro.
Um app `--windowed` não tem console, então sem o log a falha some sem deixar
rastro. O servidor tem log próprio em `server.log`, na mesma pasta.

Duas pedras já pagas nesse caminho (o `build_exe.py` já cuida das duas):

- **`pythonnet` não vem junto com o `pywebview`.** É ele que faz a ponte pro
  WebView2. Sem ele o app morre na hora de abrir a janela.
- **O `_ctypes` do Anaconda precisa da `ffi-*.dll`**, que mora em
  `Library/bin/` — pasta que o PyInstaller não varre. Sem ela o exe morre com
  `ImportError: DLL load failed while importing _ctypes`.

E cuidado com a mensagem do pywebview: ele responde **"You must have pythonnet
installed"** para *qualquer* falha ao carregar o backend, inclusive quando o
pythonnet está instalado e o problema é outro. Foi por isso que o app passou a
tentar `import clr` sozinho no começo e registrar o erro **de verdade** no log.

## Detalhes que valem saber

- **Login persiste.** A janela guarda cookies em `%APPDATA%/Klipe/webview`, em
  vez de pedir senha toda vez.
- **Fechar durante um render pergunta antes.** Fechar a janela derruba o
  servidor, e isso cancelaria o render em andamento — então ele confirma
  primeiro. (Só quando a janela é dona do servidor.)
- **Ao fechar, mata a árvore de processos.** Um render deixa ffmpeg, Chrome
  headless e Python rodando embaixo do servidor; encerrar só o Node deixaria
  esses órfãos comendo CPU.
