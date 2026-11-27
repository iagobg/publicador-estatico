# Publicador estático

Uma VPS acompanha uma pasta de um repositório no GitHub, publica os arquivos quando o conteúdo muda e confirma por HTTP o que um visitante recebe.

## 1. Sobre o projeto e o problema resolvido

Quem hospeda um site de terceiros pode ter autorização para ler e republicar os arquivos, enquanto a administração do repositório fica com outra equipe. Nesse cenário, configurar GitHub Actions ou webhooks na origem depende de quem a mantém. Conferir a branch e copiar os arquivos manualmente pode deixar uma atualização passar. Durante a cópia, um visitante também pode receber arquivos de duas edições diferentes.

A motivação veio de uma rotina pessoal de hospedagem em VPS. Esta implementação usa como exemplo um **boletim de laboratório** com HTML e CSS próprios. O operador escolhe a pasta publicável, e a VPS inicia todas as consultas. Uma edição repetida custa uma consulta à árvore e zero downloads de arquivos.

## 2. Arquitetura e fluxo de funcionamento

```mermaid
flowchart TD
    A["Polling na VPS"] --> B["GitHub REST · árvore da branch em JSON"]
    B --> C["Python seleciona caminhos e hashes dos arquivos estáticos"]
    C --> D{"O conjunto publicado mudou?"}
    D -->|Não| A
    D -->|Sim| E["Baixa os blobs por hash e prepara a versão em disco"]
    E --> F["Troca o link current de forma atômica"]
    F --> G["Lê cada arquivo pelo servidor web e confere os bytes"]
    G -->|Confere| H["Registra a versão confirmada"]
    G -->|Falha| I["Restaura a última versão confirmada"]
    H --> A
    I --> A
```

A árvore da branch chega em JSON. O Python filtra por pasta, tipo de objeto, extensão e caminho. Para cada arquivo selecionado, guarda o caminho relativo, o tamanho e o identificador Git do conteúdo (*blob*). A lista ordenada de caminhos e hashes define a versão do site. Uma alteração apenas no README da origem, por exemplo, preserva a edição publicada.

Os downloads usam os hashes da árvore consultada. Assim, mesmo que a branch avance durante a cópia, os arquivos pertencem à mesma fotografia da origem. O publicador monta a pasta inteira antes de trocar `current`, a raiz do servidor web. Depois da troca, faz um GET de cada arquivo e compara seu conteúdo com o hash de origem. Se a leitura falhar, restaura o apontamento anterior. Na primeira publicação, a confirmação bem-sucedida estabelece a primeira versão recuperável.

## 3. Tecnologias e APIs utilizadas

| Componente | Papel |
| --- | --- |
| Python 3.10+ em Linux | `urllib` faz as requisições, `json` interpreta a árvore, `hashlib` verifica os conteúdos e `fcntl` impede ciclos simultâneos. |
| API REST do GitHub por HTTPS | Consulta a árvore de uma branch e baixa os blobs por identificador. Um token Bearer pode conceder leitura de conteúdo. [Git Trees](https://docs.github.com/en/rest/git/trees#get-a-tree) · [Git Blobs](https://docs.github.com/en/rest/git/blobs#get-a-blob) |
| Servidor HTTP da VPS | Serve a pasta ativa e responde à verificação independente do publicador. O exemplo de operação usa o Caddy. [Caddy file_server](https://caddyserver.com/docs/caddyfile/directives/file_server) |
| systemd | Mantém o processo de polling ativo na VPS e direciona a saída para o journal. |

## 4. Pré-requisitos e como executar

Use Linux, Git e Python 3.10 ou superior. A biblioteca padrão cobre todas as dependências.

```bash
git clone https://github.com/iagobg/publicador-estatico.git
cd publicador-estatico
```

**Demonstração em um terminal, inclusive sem internet após o clone**

```bash
python3 demo.py --manter
```

Abra no navegador o endereço de loopback que o programa imprimir. Ele escolhe portas livres, cria uma área temporária e executa quatro ciclos com o mesmo publicador usado na VPS. A origem é uma simulação local da API com um token gerado em memória. O servidor de arquivos atende requisições HTTP reais. Pressione Enter no final para liberar as portas.

**Executar com a API real do GitHub**

1. Copie o modelo e restrinja a leitura antes de preencher uma credencial.

   ```bash
   cp .env.example .env
   chmod 600 .env
   ```

2. Edite `.env`. Para publicar o boletim deste repositório, use `GITHUB_REPO=iagobg/publicador-estatico`, `GITHUB_BRANCH=main` e `SOURCE_DIR=exemplo/site`. Os demais valores do modelo atendem ao teste local. Para uma origem própria, escolha uma pasta dedicada a conteúdo pronto para publicação. Use `.` se toda a raiz tiver essa finalidade.

   | Variável | Significado |
   | --- | --- |
   | `GITHUB_REPO`, `GITHUB_BRANCH` | Repositório no formato `conta/nome` e branch consultada. |
   | `SOURCE_DIR` | Pasta de origem que contém o `index.html`. |
   | `GITHUB_TOKEN` | Opcional para conteúdo público. Para uma origem privada, use um token de acesso restrito ao repositório, com `Contents: Read-only`. O publicador envia o token à API de origem. |
   | `DEPLOY_DIR` | Diretório exclusivo do publicador para versões, links e trava. |
   | `SITE_URL` | URL que o servidor web associa a `DEPLOY_DIR/current`. |
   | `POLL_SECONDS` | Tempo de espera entre o término de um ciclo e o início do próximo. O exemplo usa 120 segundos. |

3. Em um terminal, na raiz do clone, inicie o servidor de arquivos de laboratório. A página ficará disponível após o primeiro deploy.

   ```bash
   python3 -m http.server 8080 --bind 127.0.0.1 --directory estado/current
   ```

4. Em outro terminal, no mesmo clone, carregue as variáveis e inicie o polling.

   ```bash
   set -a
   . ./.env
   set +a
   python3 publicador.py
   ```

   Abra [o boletim local](http://127.0.0.1:8080/) depois de aparecer `PUBLICADO`. Para rodar um único ciclo, use `python3 publicador.py --uma-vez`. Nesse modo, o código de saída é 0 para sucesso, 1 para falha de execução e 2 para erro de configuração.

Para instalação persistente, siga o procedimento com usuário de serviço, raiz HTTP e consulta de logs. [Operação na VPS](operacao/README.md)

**Escopo da publicação.** O site precisa conter um `index.html` na pasta selecionada. O filtro aceita arquivos web estáticos, ignora nomes ocultos, links simbólicos e submódulos, e rejeita árvores truncadas. Os limites por edição são 100 arquivos, 4 MiB por arquivo e 32 MiB no total. Publique apenas conteúdo cuja redistribuição esteja autorizada. O HTML e o JavaScript são entregues ao navegador como vieram da origem.

## 5. Demonstração e resultados

**Com a API real do GitHub.** A partir de um clone novo, o publicador consultou a branch pública e ativou o boletim. Um cliente HTTP leu o HTML e o CSS do servidor local e comparou os bytes com os arquivos do clone. O segundo ciclo reconheceu a mesma versão.

![Teste com api.github.com: dois arquivos confirmados, ciclo repetido sem downloads e duas respostas HTTP 200 com conteúdo idêntico ao clone.](docs/github-real.png)

**Falha e recuperação reproduzíveis.**
Captura de uma execução de `python3 demo.py --intervalo 1`. Na terceira consulta, a origem devolveu HTTP 503. Logo abaixo, o GET feito como visitante retornou HTTP 200 com a edição 1. A última consulta publicou a edição 2 e verificou os dois arquivos pelo servidor.

![Terminal com quatro ciclos: primeira edição publicada, versão repetida, falha HTTP 503 com a página ainda acessível e publicação da edição 2.](docs/demonstracao.png)

O comando abaixo testa filtragem, autenticação, bloqueio de concorrência, recuperação após interrupção e reversão de uma versão servida incorretamente.

```bash
python3 -m unittest discover -s tests -v
```

O roteiro relaciona cada requisito à função que o implementa e propõe um ajuste que pode ser feito durante a arguição. [Apresentação prática de cinco minutos](docs/apresentacao.md)

## 6. Melhorias futuras

- Usar requisições condicionais com ETag para reduzir a transferência da árvore nos ciclos sem alterações.
- Respeitar o tempo de espera indicado pela API quando a cota de consultas se esgotar.
- Validar referências locais de HTML e CSS antes da troca, para identificar recursos que o autor esqueceu de incluir.
