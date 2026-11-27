# Operação em uma VPS Linux

O exemplo usa systemd, Python 3.10+ e Caddy já instalados. Execute os comandos a partir da raiz do clone. A aplicação roda no mesmo host que o servidor HTTP.

1. Crie a conta de sistema uma vez e instale os módulos usados em produção.

   ```bash
   sudo useradd --system --user-group --home-dir /nonexistent --shell /usr/sbin/nologin publicador-estatico
   sudo install -d -m 755 /opt/publicador-estatico
   sudo install -m 644 publicador.py origem.py /opt/publicador-estatico/
   ```

2. Prepare um `.env` a partir de `.env.example`. Preencha a origem, defina `DEPLOY_DIR=/var/lib/publicador-estatico` e mantenha `SITE_URL=http://127.0.0.1:8080` para o exemplo local. Instale a configuração e a unidade.

   ```bash
   sudo install -m 600 .env /etc/publicador-estatico.env
   sudo install -m 644 operacao/publicador-estatico.service /etc/systemd/system/
   ```

3. Acrescente o bloco de exemplo à configuração do Caddy, em um endereço livre. Ele serve exclusivamente a raiz `/var/lib/publicador-estatico/current`. Valide a configuração completa e recarregue o serviço. [Bloco Caddy](Caddyfile.exemplo)

   ```bash
   sudo caddy validate --config /etc/caddy/Caddyfile
   sudo systemctl reload caddy
   ```

   Para atender visitantes externos, use um nome DNS da sua hospedagem no endereço do bloco e o respectivo endereço HTTPS em `SITE_URL`. Assim a verificação passa pela mesma URL que eles acessam.

4. Inicie e confira o processo. O systemd cria o diretório de estado e o atribui à conta de serviço.

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now publicador-estatico.service
   sudo journalctl -u publicador-estatico.service -n 20 --no-pager
   curl --fail http://127.0.0.1:8080/
   ```

Ao mudar o arquivo de ambiente, reinicie a unidade. Para interromper as consultas, use `sudo systemctl stop publicador-estatico.service`. O servidor continua servindo a versão confirmada.

Um erro HTTP 401 ou 403 pede revisão da credencial, das permissões e da cota da API. Um 404 da origem pode indicar branch ou repositório incorreto (confira também o acesso a um repositório privado). Se a mensagem citar o servidor web, verifique `SITE_URL`, a raiz `current` e a permissão de leitura do servidor. O próximo ciclo repete a tentativa. Cada requisição tem timeout de 10 segundos.
