"""Publica uma versão estática e confirma o resultado pelo servidor HTTP."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from urllib.parse import quote, urlsplit

from origem import EXTENSOES, Falha, GitHub, baixar, sha_blob


def ler_link(link):
    return link.readlink() if link.is_symlink() else None


def apontar(link, destino):
    if destino is None:
        link.unlink(missing_ok=True)
        return
    temporario = link.with_suffix(".novo")
    temporario.unlink(missing_ok=True)
    temporario.symlink_to(destino)
    os.replace(temporario, link)


def preparar(origem, arquivos, pasta):
    # Um navegador só pode alcançar esta versão depois da troca de 'current'.
    site = pasta.parent / ".preparando"
    if site.exists():
        shutil.rmtree(site)
    try:
        for arquivo in arquivos:
            destino = site / arquivo.caminho
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(origem.conteudo(arquivo))
        site.rename(pasta)
    finally:
        if site.exists():
            shutil.rmtree(site)


def limpar_versoes(base):
    versoes = base / "versoes"
    protegidas = {ler_link(base / nome) for nome in ("current", "confirmado")}
    for pasta in versoes.iterdir():
        if re.fullmatch("[0-9a-f]{64}", pasta.name) and pasta.relative_to(base) not in protegidas:
            shutil.rmtree(pasta)


def ativar(origem, arquivos, base, url_site, destino, anterior):
    atual, confirmado = base / "current", base / "confirmado"
    if not (base / destino).exists():
        preparar(origem, arquivos, base / destino)
    apontar(atual, destino)
    try:
        for arquivo in arquivos:
            url = f"{url_site.rstrip('/')}/{quote(arquivo.caminho)}"
            servido = baixar(url, arquivo.tamanho, "servidor web")
            if sha_blob(servido) != arquivo.sha:
                raise Falha("servidor web entregou conteúdo diferente do esperado")
        apontar(confirmado, destino)
    except (Falha, OSError):
        apontar(atual, anterior)
        raise


def publicar(origem, base, url_site):
    atual, confirmado = base / "current", base / "confirmado"
    anterior = ler_link(confirmado)
    # Uma interrupção entre a troca e a confirmação é revertida no ciclo seguinte.
    if ler_link(atual) != anterior:
        apontar(atual, anterior)

    commit, arvore = origem.revisao()
    registro = base / "ultimo-commit.json"
    estado = {"origem": origem.base, "branch": origem.branch, "pasta": origem.pasta,
              "extensoes": sorted(EXTENSOES), "commit": commit, "versao": str(anterior)}
    if (anterior and (atual / "index.html").is_file() and registro.is_file()
            and registro.read_bytes() == json.dumps(estado).encode()):
        return f"SEM MUDANÇA | mesmo commit {commit[:10]} | árvore dispensada"

    arquivos = origem.listar(arvore)
    manifesto = json.dumps([(a.caminho, a.sha) for a in arquivos]).encode()
    versao = hashlib.sha256(manifesto).hexdigest()
    destino = Path("versoes") / versao
    if anterior == destino and (atual / "index.html").is_file():
        mensagem = f"SEM MUDANÇA | commit {commit[:10]} conferido | mesmos arquivos"
    else:
        ativar(origem, arquivos, base, url_site, destino, anterior)
        mensagem = f"PUBLICADO | commit {commit[:10]} | {len(arquivos)} arquivos confirmados via HTTP"

    # Uma falha anterior a este ponto deixa o mesmo commit elegível para nova tentativa.
    estado["versao"] = str(destino)
    temporario = registro.with_suffix(".novo")
    temporario.write_text(json.dumps(estado), encoding="ascii")
    os.replace(temporario, registro)
    return mensagem


def ciclo(origem, base, url_site):
    try:
        base.mkdir(parents=True, exist_ok=True)
        with (base / "publicador.lock").open("a") as trava:
            try:
                fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True, "OCUPADO | outro ciclo em andamento"
            (base / "versoes").mkdir(exist_ok=True)
            try:
                mensagem = publicar(origem, base, url_site)
            finally:
                limpar_versoes(base)
            return True, mensagem
    except (Falha, OSError) as erro:
        return False, f"ERRO | {erro}"


def ciclos(origem, base, url_site, intervalo):
    while True:
        yield ciclo(origem, base, url_site)
        time.sleep(intervalo)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uma-vez", action="store_true", help="executa um ciclo e devolve seu status")
    args = parser.parse_args()
    try:
        origem = GitHub(os.environ["GITHUB_REPO"], os.getenv("GITHUB_BRANCH", "main"),
                        os.environ["SOURCE_DIR"], os.getenv("GITHUB_TOKEN", ""))
        base = Path(os.environ["DEPLOY_DIR"]).resolve()
        url = os.environ["SITE_URL"]
        partes = urlsplit(url)
        if partes.scheme not in {"http", "https"} or not partes.hostname or partes.query or partes.fragment:
            raise Falha("SITE_URL deve apontar para a raiz HTTP(S) do site")
        intervalo = int(os.getenv("POLL_SECONDS", "120"))
        if intervalo < 1:
            raise Falha("POLL_SECONDS deve ser positivo")
    except (KeyError, ValueError, Falha) as erro:
        print(f"ERRO de configuração | {erro}", file=sys.stderr)
        return 2
    try:
        for sucesso, mensagem in ciclos(origem, base, url, intervalo):
            print(mensagem, file=sys.stdout if sucesso else sys.stderr, flush=True)
            if args.uma_vez:
                return 0 if sucesso else 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
