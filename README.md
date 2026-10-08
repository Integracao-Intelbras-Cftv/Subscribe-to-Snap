# Subscribe to Snap

Programa que **fica conectado a uma câmera e recebe os eventos dela em tempo real, com as imagens**.

Ele usa o comando da HTTP API (V3.81, "Subscribe to Snapshot"):

```
GET /cgi-bin/snapManager.cgi?action=attachFileProc&channel=1&heartbeat=5&Flags[0]=Event&Events=All
```

O que ele faz:

- Conecta na câmera com usuário e senha (autenticação Digest).
- Mostra cada evento na tela (tipo, ação, canal e placa, quando houver).
- Salva a imagem de cada evento na pasta `imagens/`.
- Se a conexão cair, reconecta sozinho.

Há duas formas de rodar. **Escolha só uma:**

- [Opção A: sem Docker](#opção-a-sem-docker), só com Python. Mais simples para testar no seu computador.
- [Opção B: com Docker](#opção-b-com-docker). Melhor para deixar rodando direto num servidor.

---

## Antes de começar (vale para as duas opções)

Confira estes três itens. Se algum falhar, o programa também vai falhar.

1. **O computador alcança a câmera.** Abra `http://IP_DA_CAMERA` no navegador (exemplo: `http://192.168.1.108`). A tela de login da câmera precisa aparecer. Se não aparecer, resolva a rede primeiro (cabo, VPN, IP errado).
2. **Você sabe o usuário e a senha da câmera.** Faça login na própria tela do navegador para confirmar.
3. **Você sabe a porta HTTP**, caso não seja a 80. Se você precisou digitar `http://192.168.1.108:8080` no navegador, a porta é `8080`.

### Baixar o código

Escolha um dos jeitos:

- **Sem git:** nesta página do GitHub, clique no botão verde **Code** e depois em **Download ZIP**. Extraia o ZIP numa pasta, por exemplo `C:\Subscribe-to-Snap`.
- **Com git:**
  ```
  git clone https://github.com/Integracao-Intelbras-Cftv/Subscribe-to-Snap.git
  cd Subscribe-to-Snap
  ```

### Criar o arquivo de configuração `.env`

Os dados da câmera ficam num arquivo chamado `.env`, que você cria a partir do modelo `.env.example`.

**Windows** (abra o terminal **dentro da pasta do projeto**: no Explorador de Arquivos, clique na barra de endereço, digite `cmd` e aperte Enter):

```
copy .env.example .env
notepad .env
```

**Linux / macOS:**

```
cp .env.example .env
nano .env
```

Troque os valores pelos da sua câmera e salve:

```
CAM_IP=192.168.1.108
CAM_USER=admin
CAM_PASS=sua_senha_aqui
CAM_CHANNEL=1
CAM_EVENTS=All
```

> ⚠️ **Cuidados com o `.env`**
> - O nome do arquivo é exatamente `.env`, com o ponto na frente e **sem** `.txt` no final. O Bloco de Notas às vezes salva como `.env.txt`, e aí o programa não encontra as configurações. Para conferir, rode `dir` (Windows) ou `ls -a` (Linux/macOS) na pasta.
> - Não use espaços antes nem depois do `=`.
> - Se a porta não for a 80, coloque-a junto do IP: `CAM_IP=192.168.1.108:8080`.

O que significa cada configuração está em [Configurações](#configurações).

---

## Opção A: sem Docker

### 1. Instalar o Python (só na primeira vez)

Você precisa do **Python 3.9 ou mais novo**. Para ver se já está instalado:

```
python --version
```

Se aparecer algo como `Python 3.12.4`, pule para o passo 2.

Se aparecer *"python não é reconhecido como um comando..."* ou *"command not found"*:

- **Windows:** baixe em <https://www.python.org/downloads/>. Na **primeira tela** do instalador, marque a caixa **"Add python.exe to PATH"** antes de clicar em *Install Now*. Depois **feche e abra o terminal de novo**.
- **Ubuntu/Debian:** `sudo apt install python3 python3-pip` (nesse caso, use `python3` no lugar de `python` nos comandos abaixo).
- **macOS:** `brew install python` (e use `python3` no lugar de `python`).

### 2. Instalar as dependências (só na primeira vez)

Dentro da pasta do projeto:

```
python -m pip install -r requirements.txt
```

### 3. Rodar

```
python snap_listener.py
```

Pronto. Veja em [Como saber se está funcionando](#como-saber-se-está-funcionando) o que deve aparecer na tela.

Para **parar**, aperte `Ctrl + C`.

---

## Opção B: com Docker

### 1. Instalar o Docker (só na primeira vez)

- **Windows / macOS:** instale o [Docker Desktop](https://www.docker.com/products/docker-desktop/) e **deixe-o aberto**. O ícone da baleia precisa estar na bandeja do sistema.
- **Linux:** siga <https://docs.docker.com/engine/install/>.

Para conferir:

```
docker --version
docker compose version
```

### 2. Subir o programa

Dentro da pasta do projeto, com o `.env` já criado:

```
docker compose up -d --build
```

O programa fica rodando em segundo plano e **volta sozinho** se o computador ou o Docker reiniciar.

### 3. Comandos do dia a dia

| Quero... | Comando |
|---|---|
| Ver os eventos chegando (`Ctrl + C` só sai da visualização; o programa continua rodando) | `docker compose logs -f` |
| Parar | `docker compose down` |
| Aplicar uma mudança feita no `.env` | `docker compose up -d` |
| Atualizar depois de baixar código novo | `docker compose up -d --build` |
| Rodar uma vez com todos os detalhes (modo debug) | `docker compose run --rm snap-listener --debug` |

As imagens ficam na pasta `imagens/` do projeto, no seu computador.

<details>
<summary>Sem Docker Compose (só <code>docker run</code>)</summary>

```
docker build -t snap-listener .
```

Depois, **um** dos comandos abaixo, conforme o seu terminal:

```
# PowerShell
docker run -d --name snap-listener --restart unless-stopped --env-file .env -v "${PWD}/imagens:/app/imagens" snap-listener

# Prompt de Comando (cmd)
docker run -d --name snap-listener --restart unless-stopped --env-file .env -v "%cd%/imagens:/app/imagens" snap-listener

# Linux / macOS
docker run -d --name snap-listener --restart unless-stopped --env-file .env -v "$(pwd)/imagens:/app/imagens" snap-listener
```

Para ver os logs: `docker logs -f snap-listener`. Para parar e remover: `docker rm -f snap-listener`.

</details>

---

## Como saber se está funcionando

Se der tudo certo, a tela fica assim:

```
2026-10-08 13:48:22 INFO Conectando: http://192.168.1.108/cgi-bin/snapManager.cgi?action=attachFileProc&channel=1&heartbeat=5&Flags[0]=Event&Events=All
2026-10-08 13:48:22 INFO Inscrição ativa (HTTP 200, multipart/x-mixed-replace; boundary=myboundary)
2026-10-08 13:48:23 INFO EVENTO TrafficJunction [Pulse] canal=0 placa=ABC1D23
2026-10-08 13:48:23 INFO   imagem image/jpeg (154320 bytes) -> imagens/20261008_134823_113534_TrafficJunction.jpg
```

- **`Inscrição ativa (HTTP 200 ...)`**: a conexão com a câmera deu certo.
- **`EVENTO ...`**: chegou um evento.
- **`imagem ... ->`**: a imagem do evento foi salva naquele arquivo.

Se aparecer `Inscrição ativa` e mais nada, a conexão está certa, só não aconteceu nenhum evento ainda. Leia o item *"Conecta, mas nenhum evento aparece"* em [Problemas comuns](#problemas-comuns).

Para ver **todos os campos** de cada evento e também os heartbeats (o sinal de vida que a câmera manda a cada 5 segundos), rode com `--debug`:

```
python snap_listener.py --debug
```

---

## Configurações

As configurações podem ficar no `.env` ou ser passadas na linha de comando. A linha de comando tem prioridade.

| No `.env` | Na linha de comando | Padrão | O que é |
|---|---|---|---|
| `CAM_IP` | `--ip` | `192.168.1.108` | IP da câmera. Se a porta HTTP não for 80: `192.168.1.108:8080` |
| `CAM_USER` | `--usuario` | `admin` | Usuário da câmera |
| `CAM_PASS` | `--senha` | `admin123` | Senha da câmera |
| `CAM_CHANNEL` | `--canal` | `1` | Canal monitorado. Começa em `1`; `-1` = todos os canais |
| `CAM_EVENTS` | `--eventos` | `All` | `All` = todos os eventos. Para filtrar: `[TrafficJunction]` ou `[TrafficJunction,CrossLineDetection]` |
| `HEARTBEAT` | `--heartbeat` | `5` | De quantos em quantos segundos a câmera manda sinal de vida |
| `CAM_HTTPS` | `--https` | `false` | `true` para acessar por HTTPS (o certificado não é validado) |
| `PASTA_IMAGENS` | — | `imagens` | Onde salvar as imagens |
| — | `--debug` | desligado | Mostra todos os campos de cada evento e os heartbeats |

Exemplo sem `.env`, tudo pela linha de comando:

```
python snap_listener.py --ip 192.168.1.108 --usuario admin --senha minhaSenha --canal 1 --eventos [TrafficJunction]
```

Para ver a ajuda: `python snap_listener.py -h`

---

## Problemas comuns

| O que aparece | O que significa | O que fazer |
|---|---|---|
| `'python' não é reconhecido...` / `command not found` | O Python não está instalado ou não está no PATH | Volte ao [passo 1 da opção A](#1-instalar-o-python-só-na-primeira-vez). No Windows, tente `py` no lugar de `python`. No Linux/macOS, use `python3` |
| `ModuleNotFoundError: No module named 'requests'` | Faltou instalar as dependências | `python -m pip install -r requirements.txt` |
| `Connection to ... timed out` / `ConnectTimeoutError` | O computador não está alcançando a câmera | Confira o IP e a porta no `.env`. Abra `http://IP_DA_CAMERA` no navegador: se não abrir lá, o problema é de rede (VPN, cabo, firewall) |
| `Connection refused` | A câmera respondeu, mas não nessa porta | A porta HTTP está errada. Coloque a porta certa: `CAM_IP=IP:PORTA` |
| `HTTP 401 Unauthorized` | Usuário ou senha errados | Confira `CAM_USER` e `CAM_PASS`. Muitas tentativas erradas podem **bloquear o usuário na câmera** por alguns minutos |
| `HTTP 400 Bad Request` | A câmera não aceitou os parâmetros | Use `CAM_CHANNEL=1` e `CAM_EVENTS=All`. Confira se o canal existe nesse equipamento e se o nome do evento está escrito certo, entre colchetes |
| `HTTP 404` ou `HTTP 501` | O firmware não tem esse comando | Atualize o firmware da câmera ou confirme com o suporte se o modelo suporta `snapManager.cgi` |
| `Inscrição ativa` e nenhum evento aparece | A conexão está certa, mas nenhum evento aconteceu | Confira se o evento está **habilitado e configurado** na câmera (por exemplo, regra de leitura de placas). Provoque um evento e rode com `--debug` para ver se os heartbeats estão chegando |
| `Read timed out` seguido de `Reconectando...` | Os dados pararam de chegar (nem o heartbeat veio) | Normalmente é instabilidade de rede, e o programa reconecta sozinho. Se acontecer sempre, aumente `HEARTBEAT` (exemplo: `10`) |
| `Content-Type inesperado` | A câmera respondeu algo que não é o fluxo de eventos | Rode com `--debug` e confira a mensagem. Pode ser uma página de erro do firmware |
| O programa ignora o `.env` | O arquivo foi salvo como `.env.txt` ou está em outra pasta | Veja os cuidados em [Criar o arquivo de configuração](#criar-o-arquivo-de-configuração-env) |
| Docker: `error during connect` / `Cannot connect to the Docker daemon` | O Docker não está rodando | Abra o Docker Desktop e espere ele terminar de iniciar |
| Docker: o programa funciona sem Docker, mas dá timeout dentro do Docker | O container não alcança a rede da câmera (comum com algumas VPNs) | Teste primeiro sem Docker. No Linux, dá para usar `network_mode: host` no `docker-compose.yml` |

---

## Como funciona (para quem vai integrar)

A câmera mantém a conexão HTTP aberta e manda uma resposta `multipart/x-mixed-replace` sem fim. Cada parte tem os próprios cabeçalhos:

```
--myboundary
Content-Type: text/plain
Content-Length: 512

Events[0].EventBaseInfo.Code=TrafficJunction
Events[0].EventBaseInfo.Action=Pulse
Events[0].EventBaseInfo.Index=0
...
--myboundary
Content-Type: image/jpeg
Content-Length: 154320

<bytes do JPEG>
--myboundary
Content-Type: text/plain
Content-Length: 9

Heartbeat
```

Pontos importantes se você for reimplementar em outra linguagem:

- **Não trate cada pedaço recebido (chunk) como um evento.** Um evento pode chegar dividido em vários pedaços, e um pedaço pode ter vários eventos. Separe as partes pelo *boundary* (informado no `Content-Type` da resposta) e leia exatamente `Content-Length` bytes de cada parte. O JPEG pode conter, por acaso, o mesmo texto do boundary.
- **A imagem vem numa parte separada**, logo depois do texto do evento correspondente.
- **`Heartbeat` é só um sinal de vida.** Se nem ele chegar dentro de alguns intervalos, considere a conexão morta e reconecte.
- **Só considere a inscrição ativa depois de receber `HTTP 200`.** Em caso de erro, registre o status e o corpo da resposta.
- **Reconecte com espera progressiva** (1s, 1,5s, 2,25s... até 60s) para não sobrecarregar a câmera.

O código em [`snap_listener.py`](snap_listener.py) segue exatamente esses passos: `iter_partes` separa as partes, `interpretar_texto` transforma o texto em campos e `escutar_uma_vez` / `main` cuidam da conexão e da reconexão.

---

## Boas práticas

- Troque a senha padrão da câmera.
- **Nunca envie o arquivo `.env` para o GitHub**, porque ele tem a sua senha. Ele já está no `.gitignore`.
- Prefira HTTPS (`CAM_HTTPS=true`) quando a câmera estiver fora da rede local.
- Mantenha o firmware da câmera atualizado.
