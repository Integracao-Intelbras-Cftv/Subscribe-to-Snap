#!/usr/bin/env python3
"""
Listener contínuo de eventos com imagem via CGI (HTTP API V3.81 - Subscribe to Snapshot):
  GET /cgi-bin/snapManager.cgi?action=attachFileProc&channel=1&heartbeat=5&Flags[0]=Event&Events=[All]

A câmera responde com multipart/x-mixed-replace e mantém a conexão aberta:

  --myboundary
  Content-Type: text/plain
  Content-Length: 512

  Events[0].EventBaseInfo.Code=TrafficJunction
  Events[0].EventBaseInfo.Action=Pulse
  ...
  --myboundary
  Content-Type: image/jpeg
  Content-Length: 123456

  <JPEG>
  --myboundary
  Content-Type: text/plain
  Content-Length: 9

  Heartbeat

- Digest Auth.
- Parser multipart por boundary + Content-Length (não trata cada chunk TCP como um evento).
- Heartbeat usado como sinal de vida: sem dados por 3x o heartbeat, a conexão é refeita.
- Reconexão com backoff exponencial + jitter.
- Status e corpo de respostas != 200 (ex.: 400 Bad Request) vão para o log.
"""

import argparse
import json
import logging
import os
import random
import re
import signal
import time
from datetime import datetime

import requests
import urllib3
from requests.auth import HTTPDigestAuth

try:
    from dotenv import load_dotenv  # opcional: lê as configurações do arquivo .env
    load_dotenv()
except ImportError:
    pass

CAMERA_IP = os.getenv("CAM_IP", "192.168.1.108")  # a porta HTTP pode vir junto do IP
USUARIO = os.getenv("CAM_USER", "admin")
SENHA = os.getenv("CAM_PASS", "admin123")
CANAL = os.getenv("CAM_CHANNEL", "1")                   # começa em 1; -1 = todos os canais
EVENTOS = os.getenv("CAM_EVENTS", "[All]")  # ou filtrar, ex.: [TrafficJunction]
HEARTBEAT = int(os.getenv("HEARTBEAT", "5"))
PASTA_IMAGENS = os.getenv("PASTA_IMAGENS", "imagens")
USAR_HTTPS = os.getenv("CAM_HTTPS", "false").strip().lower() in ("1", "true", "sim", "yes")

TIMEOUT_CONEXAO = 10
BACKOFF_BASE = 1.5
BACKOFF_MAX = 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("snap-listener")

_parar = False


def _sinal(signum, frame):
    global _parar
    _parar = True
    log.info("Sinal %s recebido, encerrando…", signum)


for _s in (signal.SIGINT, signal.SIGTERM):
    try:
        signal.signal(_s, _sinal)
    except (ValueError, OSError):
        pass


# ---------------------------------------------------------------- multipart

def ler_stream(resp):
    """Entrega os bytes assim que chegam (iter_content(4096) esperaria juntar 4096 bytes,
    atrasando heartbeats e eventos pequenos)."""
    raw = resp.raw
    ler = getattr(raw, "read1", None) or raw._fp.read1  # urllib3 2.x / 1.x
    while True:
        dados = ler(65536)
        if not dados:
            return
        yield dados


def iter_partes(resp):
    """Gera (headers, corpo) para cada parte do multipart/x-mixed-replace.
    Usa Content-Length da parte quando existir; senão, lê até o próximo boundary."""
    tipo = resp.headers.get("Content-Type", "")
    m = re.search(r'boundary="?([^";]+)"?', tipo, re.I)
    boundary = m.group(1) if m else "myboundary"
    if boundary.startswith("--"):  # alguns firmwares já mandam o boundary com "--"
        boundary = boundary[2:]
    marca = b"--" + boundary.encode()

    buffer = b""
    chunks = ler_stream(resp)

    def mais():
        nonlocal buffer
        dados = next(chunks, None)
        if dados is None:
            raise EOFError
        buffer += dados

    try:
        while True:
            # 1) Localiza o boundary
            while (i := buffer.find(marca)) < 0:
                buffer = buffer[-len(marca):]  # descarta lixo, guarda um possível boundary partido
                mais()
            buffer = buffer[i + len(marca):]

            # 2) Cabeçalhos da parte
            while (fim := buffer.find(b"\r\n\r\n")) < 0:
                mais()
            bloco, buffer = buffer[:fim], buffer[fim + 4:]
            headers = {}
            for linha in bloco.decode("latin-1").split("\r\n"):
                nome, sep, valor = linha.partition(":")
                if sep:
                    headers[nome.strip().lower()] = valor.strip()
            if not headers:  # "--boundary--" de fechamento ou linha vazia
                continue

            # 3) Corpo
            tamanho = headers.get("content-length")
            if tamanho and tamanho.isdigit():
                tamanho = int(tamanho)
                while len(buffer) < tamanho:
                    mais()
                corpo, buffer = buffer[:tamanho], buffer[tamanho:]
            else:
                while (fim := buffer.find(marca)) < 0:
                    mais()
                corpo, buffer = buffer[:fim].rstrip(b"\r\n"), buffer[fim:]
            yield headers, corpo
    except EOFError:
        return


# ---------------------------------------------------------------- eventos

def interpretar_texto(texto):
    """'Events[0].EventBaseInfo.Code=TrafficJunction' -> [{'EventBaseInfo.Code': 'TrafficJunction', ...}]"""
    eventos = {}
    for linha in texto.splitlines():
        chave, sep, valor = linha.strip().partition("=")
        if not sep:
            continue
        m = re.match(r"Events\[(\d+)\]\.(.+)", chave)
        indice, campo = (int(m.group(1)), m.group(2)) if m else (0, chave)
        eventos.setdefault(indice, {})[campo] = valor
    return [eventos[i] for i in sorted(eventos)]


def resumo_evento(ev):
    code = ev.get("EventBaseInfo.Code", "?")
    acao = ev.get("EventBaseInfo.Action", "?")
    canal = ev.get("EventBaseInfo.Index", "?")
    placa = ev.get("TrafficCar.PlateNumber") or ev.get("Object.Text") or ""
    return f"{code} [{acao}] canal={canal}" + (f" placa={placa}" if placa else "")


def salvar_imagem(corpo, evento):
    os.makedirs(PASTA_IMAGENS, exist_ok=True)
    code = (evento or {}).get("EventBaseInfo.Code", "evento")
    nome = f"{datetime.now():%Y%m%d_%H%M%S_%f}_{code}.jpg"
    caminho = os.path.join(PASTA_IMAGENS, nome)
    with open(caminho, "wb") as f:
        f.write(corpo)
    return caminho


def consumir(resp):
    ultimo_evento = None
    for headers, corpo in iter_partes(resp):
        if _parar:
            return
        tipo = headers.get("content-type", "").lower()

        if tipo.startswith("image/"):
            caminho = salvar_imagem(corpo, ultimo_evento)
            log.info("  imagem %s (%d bytes) -> %s", tipo, len(corpo), caminho)
            continue

        texto = corpo.decode("utf-8", "replace").strip()
        if texto.lower() == "heartbeat":
            log.debug("heartbeat")
            continue

        eventos = interpretar_texto(texto)
        if not eventos:
            log.info("Parte %s não reconhecida: %r", tipo or "sem Content-Type", texto[:200])
            continue
        for ev in eventos:
            log.info("EVENTO %s", resumo_evento(ev))
            log.debug("  %s", json.dumps(ev, ensure_ascii=False))
        ultimo_evento = eventos[-1]


# ---------------------------------------------------------------- conexão

def normalizar_eventos(eventos):
    """A lista de eventos precisa ir entre colchetes: com Events=All a câmera responde
    HTTP 500 (visto na VIP-9460-ULTRA-IA-FT); com Events=[All] funciona."""
    eventos = eventos.strip()
    return eventos if eventos.startswith("[") else f"[{eventos}]"


def montar_url(base):
    # O requests/urllib3 envia os colchetes como %5B/%5D (o uri do Digest sai igual).
    # Se o firmware responder 400, confira no log se é por causa dessa codificação.
    return (f"{base}/cgi-bin/snapManager.cgi?action=attachFileProc&channel={CANAL}"
            f"&heartbeat={HEARTBEAT}&Flags[0]=Event&Events={EVENTOS}")


def escutar_uma_vez(sessao, url):
    """Abre a inscrição e consome até cair. Retorna True se chegou a receber 200 OK."""
    log.info("Conectando: %s", url)
    try:
        # Read timeout = 3 heartbeats: se nem o heartbeat chegar, a conexão está morta.
        with sessao.get(url, stream=True, timeout=(TIMEOUT_CONEXAO, HEARTBEAT * 3)) as resp:
            tipo = resp.headers.get("Content-Type", "")
            if resp.status_code != 200:
                log.error("HTTP %s %s | Content-Type: %s | corpo: %r",
                          resp.status_code, resp.reason, tipo, resp.content[:500])
                return False
            if "multipart" not in tipo.lower():
                log.warning("Content-Type inesperado: %r (esperado multipart/x-mixed-replace)", tipo)
            log.info("Inscrição ativa (HTTP 200, %s)", tipo)
            consumir(resp)
            log.warning("Stream encerrado pela câmera.")
            return True
    except (requests.RequestException, urllib3.exceptions.HTTPError, OSError) as e:
        # Durante o stream, read1 lança as exceções do urllib3 sem o requests embrulhar
        log.error("Falha na conexão/stream: %s", e)
        return False


def main():
    global CANAL, EVENTOS, HEARTBEAT
    p = argparse.ArgumentParser(description="Inscrição em eventos via snapManager.cgi?action=attachFileProc")
    p.add_argument("--ip", default=CAMERA_IP, help="IP da câmera (aceita IP:porta)")
    p.add_argument("--usuario", default=USUARIO)
    p.add_argument("--senha", default=SENHA)
    p.add_argument("--canal", default=CANAL, help="Canal (começa em 1; -1 = todos)")
    p.add_argument("--eventos", default=EVENTOS, help="[All] (padrão), [TrafficJunction] ou [A,B]")
    p.add_argument("--heartbeat", type=int, default=HEARTBEAT)
    p.add_argument("--https", action="store_true", default=USAR_HTTPS,
                   help="Usar HTTPS (sem validar certificado)")
    p.add_argument("--debug", action="store_true", help="Mostra todos os campos de cada evento")
    args = p.parse_args()

    CANAL, EVENTOS, HEARTBEAT = args.canal, normalizar_eventos(args.eventos), args.heartbeat
    if args.debug:
        log.setLevel(logging.DEBUG)
    if args.https:
        urllib3.disable_warnings()

    url = montar_url(f"{'https' if args.https else 'http'}://{args.ip}")
    backoff = 1.0
    with requests.Session() as sessao:
        sessao.auth = HTTPDigestAuth(args.usuario, args.senha)
        sessao.verify = not args.https
        while not _parar:
            if escutar_uma_vez(sessao, url):
                backoff = 1.0  # conexão chegou a funcionar: recomeça a espera do zero
            if _parar:
                break
            espera = min(BACKOFF_MAX, backoff * (1 + random.random()))
            log.warning("Reconectando em %.1fs…", espera)
            time.sleep(espera)
            backoff = min(BACKOFF_MAX, backoff * BACKOFF_BASE)
    log.info("Listener finalizado.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
