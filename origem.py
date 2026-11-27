"""Seleção dos arquivos públicos a partir da API REST do GitHub."""

import hashlib
from http.client import HTTPException
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class Falha(Exception):
    """Erro operacional que deve aparecer no log do ciclo."""


EXTENSOES = {".html", ".css", ".js", ".json", ".png", ".jpg", ".jpeg", ".svg",
             ".webp", ".gif", ".ico", ".woff", ".woff2"}
MIB = 1024 * 1024


def baixar(url, limite, servico, *, accept="*/*", token=""):
    req = Request(url, headers={"Accept": accept, "User-Agent": "publicador-estatico"})
    if token:
        # O urllib não encaminha este cabeçalho durante redirecionamentos.
        req.add_unredirected_header("Authorization", f"Bearer {token}")
    try:
        with urlopen(req, timeout=10) as resposta:
            dados = resposta.read(limite + 1)
    except HTTPError as erro:
        raise Falha(f"{servico} respondeu HTTP {erro.code}") from erro
    except (URLError, OSError, HTTPException) as erro:
        raise Falha(f"{servico} indisponível ou tempo de espera excedido") from erro
    if len(dados) > limite:
        raise Falha(f"{servico} excedeu o limite de tamanho da resposta")
    return dados


def caminho_publico(nome):
    return all(parte and not parte.startswith(".") and "\\" not in parte
               and parte.isprintable() for parte in nome.split("/"))


@dataclass(frozen=True)
class Arquivo:
    caminho: str
    sha: str
    tamanho: int


def selecionar(arvore, pasta):
    if arvore["truncated"] is not False:
        raise Falha("árvore incompleta na origem")
    prefixo = "" if pasta == "." else pasta + "/"
    arquivos = []
    for item in arvore["tree"]:
        if item["type"] != "blob" or item["mode"] not in {"100644", "100755"}:
            continue
        if not item["path"].startswith(prefixo):
            continue
        nome = item["path"][len(prefixo):]
        if not caminho_publico(nome) or PurePosixPath(nome).suffix.lower() not in EXTENSOES:
            continue
        tamanho, sha = item["size"], item["sha"]
        if not 0 <= tamanho <= 4 * MIB or not re.fullmatch("[0-9a-f]{40}", sha):
            raise Falha("tamanho ou identificador de arquivo inválido")
        arquivos.append(Arquivo(nome, sha, tamanho))

    if not any(a.caminho == "index.html" and a.tamanho > 0 for a in arquivos):
        raise Falha("index.html ausente ou vazio na pasta selecionada")
    if len(arquivos) > 100 or sum(a.tamanho for a in arquivos) > 32 * MIB:
        raise Falha("site excede 100 arquivos ou 32 MiB")
    return sorted(arquivos, key=lambda a: a.caminho)


def sha_blob(dados):
    # Git inclui o tipo e o comprimento antes dos bytes do arquivo.
    return hashlib.sha1(f"blob {len(dados)}\0".encode() + dados).hexdigest()


class GitHub:
    def __init__(self, repo, branch, pasta, token="", api="https://api.github.com"):
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or not caminho_publico(repo):
            raise Falha("configure GITHUB_REPO no formato conta/repositorio")
        if not branch or (pasta != "." and not caminho_publico(pasta)):
            raise Falha("confira GITHUB_BRANCH e SOURCE_DIR")
        self.base = f"{api}/repos/{repo}/git"
        self.branch = quote(branch, safe="")
        self.pasta = pasta
        self.token = token

    def listar(self):
        dados = baixar(f"{self.base}/trees/{self.branch}?recursive=1", 8 * MIB,
                       "API de origem", accept="application/vnd.github+json", token=self.token)
        try:
            return selecionar(json.loads(dados), self.pasta)
        except (KeyError, TypeError, ValueError, AttributeError) as erro:
            raise Falha("JSON de árvore inválido na origem") from erro

    def conteudo(self, arquivo):
        dados = baixar(f"{self.base}/blobs/{arquivo.sha}", arquivo.tamanho, "API de origem",
                       accept="application/vnd.github.raw+json", token=self.token)
        if len(dados) != arquivo.tamanho or sha_blob(dados) != arquivo.sha:
            raise Falha("conteúdo recebido diverge do blob anunciado")
        return dados
