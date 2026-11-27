import fcntl
from contextlib import ExitStack
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.request import urlopen

from demo import ApiLocal, Boletim, SiteLocal, servidor
from origem import Falha, GitHub, selecionar, sha_blob
from publicador import apontar, ciclo


class TesteArvore(unittest.TestCase):
    def test_apenas_arquivos_publicos_da_pasta(self):
        def item(nome, modo="100644"):
            return dict(path=nome, mode=modo, type="blob", sha=sha_blob(b"x"), size=1)
        itens = [item("site/index.html"), item("site/estilo.css"), item("site/.config/x.json"),
                 item("site/../x.js"), item("site//x.js"), item("site/link.html", "120000"),
                 item("site/notas.md"), item("site-extra/fora.js")]
        arquivos = selecionar(dict(tree=itens, truncated=False), "site")
        self.assertEqual([a.caminho for a in arquivos], ["estilo.css", "index.html"])

    def test_rejeita_arvore_incompleta_ou_sem_pagina(self):
        for truncada in (True, False):
            with self.subTest(truncada=truncada), self.assertRaises(Falha):
                selecionar(dict(tree=[], truncated=truncada), "site")


class TestePublicacao(unittest.TestCase):
    def setUp(self):
        recursos = ExitStack()
        self.addCleanup(recursos.close)
        self.base = Path(recursos.enter_context(TemporaryDirectory()))
        self.boletim = Boletim()
        api = recursos.enter_context(servidor(ApiLocal, self.boletim))
        self.site = recursos.enter_context(servidor(partial(SiteLocal, directory=self.base / "current")))
        self.origem = GitHub("exemplo/boletim", "main", "site", self.boletim.token, api)

    def rodar(self, url=None):
        return ciclo(self.origem, self.base, url or self.site)

    def test_reverte_quando_o_servidor_entrega_bytes_incorretos(self):
        self.assertTrue(self.rodar()[0])
        self.boletim.trocar_edicao(2)
        pasta = Path(__file__).resolve().parents[1] / "exemplo/site"
        with servidor(partial(SiteLocal, directory=pasta)) as site_desatualizado:
            sucesso, log = self.rodar(site_desatualizado)
            self.assertFalse(sucesso)
            self.assertIn("conteúdo diferente", log)
        with urlopen(self.site, timeout=5) as resposta:
            self.assertIn("Edição 1", resposta.read().decode())
        self.assertTrue(self.rodar()[0])
        with urlopen(self.site, timeout=5) as resposta:
            self.assertIn("Edição 2", resposta.read().decode())

    def test_falha_inicial_401_e_recuperacao(self):
        self.origem.token = ""
        self.assertIn("HTTP 401", self.rodar()[1])
        self.assertFalse((self.base / "current").is_symlink())
        self.origem.token = self.boletim.token
        self.assertTrue(self.rodar()[0])

    def test_trava_e_recuperacao_de_troca_interrompida(self):
        self.assertTrue(self.rodar()[0])
        with (self.base / "publicador.lock").open("a") as trava:
            fcntl.flock(trava, fcntl.LOCK_EX)
            self.assertIn("OCUPADO", self.rodar()[1])
        anterior = (self.base / "confirmado").readlink()
        apontar(self.base / "current", Path("versoes") / ("a" * 64))
        self.boletim.indisponivel = True
        self.assertIn("HTTP 503", self.rodar()[1])
        self.assertEqual((self.base / "current").readlink(), anterior)


if __name__ == "__main__":
    unittest.main()
