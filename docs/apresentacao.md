# Apresentação prática · 5 minutos

| Tempo | O que fazer | O que mostrar |
| --- | --- | --- |
| 0:00–1:00 | “Eu hospedo conteúdo mantido por outra pessoa e preciso acompanhar as atualizações com acesso de leitura.” Descreva a antiga conferência de versão e cópia manual. | O boletim fictício representa os arquivos autorizados para hospedagem. |
| 1:00–2:00 | Abra o diagrama no README. Siga um arquivo desde o JSON da árvore até o GET feito à VPS. | O hash identifica o conteúdo. A troca de um link ativa a pasta preparada. O token fica na máquina que publica. |
| 2:00–4:00 | Execute `python3 demo.py --intervalo 4 --manter` e abra a URL impressa. Acompanhe o terminal e atualize o navegador. | Mostre edição 1, ciclo repetido, erro 503 com a página ainda acessível e chegada da edição 2. Identifique a origem simulada e o servidor HTTP real. |
| 4:00–5:00 | Reserve o último minuto para perguntas e um ajuste curto. | Mude o intervalo para dois segundos e mostre no terminal quando a nova consulta ocorre. |

### Onde encontrar os seis requisitos

| Requisito | Evidência que você pode abrir |
| --- | --- |
| 1. Motor em Python | `main` lê a configuração e chama `ciclos`. [publicador.py](../publicador.py) |
| 2. Duas integrações de rede | `GitHub.listar` consulta a API REST. Após a troca, `publicar` lê cada arquivo pela URL do servidor HTTP da VPS. [origem.py](../origem.py) · [publicador.py](../publicador.py) |
| 3. Transformação de dados | `selecionar` transforma a árvore JSON em uma lista ordenada de arquivos, tamanhos e hashes. Mostre por que `site/.rascunho.json` e `site/notas.md` ficam de fora. [origem.py](../origem.py) · [dados da demonstração](../demo.py) |
| 4. Autenticação | `baixar` acrescenta o Bearer quando a origem fornece um token. A demonstração gera sua própria credencial e um teste provoca HTTP 401. [origem.py](../origem.py) · [.env.example](../.env.example) |
| 5. Gatilho e ação | `ciclos` espera o intervalo configurado. `preparar` grava a versão e `apontar` troca a raiz servida. Comprove a ação abrindo a página. [publicador.py](../publicador.py) |
| 6. Erros e resiliência | A origem indisponível produz erro legível e uma nova tentativa no próximo ciclo. Se o servidor responder 200 com bytes incorretos, o publicador reverte a troca. [testes de integração](../tests/test_publicador.py) |

### Perguntas para ensaiar

- **Por que polling?** A VPS consegue consultar uma origem com acesso de leitura. Configurar um webhook ou instalar um workflow exigiria a participação do administrador da origem.
- **Como a atualização é detectada?** A assinatura da versão usa os caminhos e os hashes dos arquivos selecionados. Adicionar, remover, renomear ou editar um desses arquivos muda a assinatura. Reordenar as entradas da API preserva o resultado.
- **O que acontece se o processo cair durante a troca?** `confirmado` guarda a última versão verificada. Ao reiniciar, o publicador restaura `current` antes de consultar a origem novamente.
- **Como conferir a integração real?** Use os dois terminais da seção 4 do README com o repositório público deste boletim. O modo `--uma-vez` facilita acompanhar um ciclo isolado.
