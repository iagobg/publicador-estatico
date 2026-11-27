"""Demonstração sem internet. Apenas a API de origem é simulada."""

import argparse
from contextlib import ExitStack, contextmanager
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import secrets
import tempfile
from threading import Thread
from urllib.request import urlopen

from origem import GitHub, sha_blob
from publicador import ciclos


class Boletim:
    def __init__(self):
        self.token = secrets.token_urlsafe()
        self.indisponivel = False
        self.arvores = {}
        self.blobs = {}
        self.trocar_edicao(1)

    def trocar_edicao(self, numero):
        pasta = Path(__file__).parent / "exemplo" / "site"
        pagina = (pasta / "index.html").read_text(encoding="utf-8")
        self.arquivos = {
            "site/index.html": pagina.replace("Edição 1", f"Edição {numero}").encode(),
            "site/assets/estilo.css": (pasta / "assets/estilo.css").read_bytes(),
            "site/.rascunho.json": b"{}",
            "site/notas.md": b"Rascunho",
            "outra-pasta/index.html": b"Arquivo fora do site",
        }
        self.comitar()

    def comitar(self):
        itens = []
        for nome, dados in sorted(self.arquivos.items()):
            sha = sha_blob(dados)
            self.blobs[sha] = dados
            itens.append(dict(path=nome, type="blob", mode="100644", sha=sha, size=len(dados)))
        corpo = json.dumps({"tree": itens, "truncated": False}).encode()
        self.arvore = hashlib.sha1(corpo).hexdigest()
        self.arvores[self.arvore] = corpo
        self.commit = hashlib.sha1(("commit " + self.arvore).encode()).hexdigest()

    def responder(self, req):
        if req.headers.get("Authorization") != f"Bearer {self.token}":
            req.send_error(401)
            return
        if self.indisponivel:
            req.send_error(503)
            return
        base = "/repos/exemplo/boletim"
        if req.path == base + "/branches/main":
            revisao = {"commit": {"sha": self.commit, "commit": {"tree": {"sha": self.arvore}}}}
            req.enviar(json.dumps(revisao).encode(), "application/json")
            return
        arvore = req.path.removeprefix(base + "/git/trees/").removesuffix("?recursive=1")
        if arvore in self.arvores:
            req.enviar(self.arvores[arvore], "application/json")
            return
        sha = req.path.removeprefix(base + "/git/blobs/")
        if sha in self.blobs:
            req.enviar(self.blobs[sha], "application/octet-stream")
            return
        req.send_error(404)


class ApiLocal(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.boletim.responder(self)

    def enviar(self, corpo, tipo):
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *args):
        pass


class SiteLocal(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@contextmanager
def servidor(handler, boletim=None):
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as http:
        http.boletim = boletim
        thread = Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{http.server_port}"
        finally:
            http.shutdown()
            thread.join()


def demonstrar(intervalo, manter):
    boletim = Boletim()
    with ExitStack() as recursos:
        base = Path(recursos.enter_context(tempfile.TemporaryDirectory()))
        api = recursos.enter_context(servidor(ApiLocal, boletim))
        site = recursos.enter_context(servidor(partial(SiteLocal, directory=base / "current")))
        origem = GitHub("exemplo/boletim", "main", "site", boletim.token, api)
        print(f"Origem simulada | servidor HTTP real | polling a cada {intervalo} s")
        print(f"Abra o boletim em {site}/\n", flush=True)
        agenda = ciclos(origem, base, site, intervalo)
        etapas = [
            ("Primeira publicação", "PUBLICADO", 1),
            ("Mesmo commit na branch", "SEM MUDANÇA", 1),
            ("Novo commit só de documentação", "SEM MUDANÇA", 1),
            ("Queda da API de origem", "ERRO", 1),
            ("API recuperada com nova edição", "PUBLICADO", 2),
        ]
        for titulo, estado, edicao in etapas:
            boletim.indisponivel = estado == "ERRO"
            if titulo == "Novo commit só de documentação":
                boletim.arquivos["README.md"] = b"Nova nota de uso"
                boletim.comitar()
            if edicao == 2:
                boletim.trocar_edicao(2)
            sucesso, mensagem = next(agenda)
            print(titulo)
            print("  " + mensagem)
            with urlopen(site + "/", timeout=5) as resposta:
                html = resposta.read().decode()
                esperado = f'Edição {edicao}'
                if f'<p id="edicao">{esperado}</p>' not in html:
                    raise RuntimeError("O visitante recebeu uma edição inesperada")
                print(f"  GET / -> HTTP {resposta.status} | {esperado}\n", flush=True)
            if sucesso != (estado != "ERRO") or not mensagem.startswith(estado):
                raise RuntimeError("O resultado do ciclo divergiu do cenário esperado")
        if manter:
            input("Pressione Enter para encerrar a demonstração. ")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intervalo", type=int, default=2, metavar="SEGUNDOS")
    parser.add_argument("--manter", action="store_true", help="mantém o site aberto após os cinco ciclos")
    args = parser.parse_args()
    if args.intervalo < 1:
        parser.error("o intervalo deve ser positivo")
    demonstrar(args.intervalo, args.manter)
