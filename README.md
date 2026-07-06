# Luciano Garces Contabilidade e Pericias

Aplicacao Flask para o site institucional, solicitacoes de atendimento, painel administrativo e area do cliente.

## Estrutura

- `app.py`: cria a aplicacao Flask, inicializa Flask-Login, registra rotas publicas, administrativas e de cliente.
- `config.py`: le as variaveis do `.env` e monta a conexao MySQL para o SQLAlchemy.
- `models.py`: define os dados de usuários, clientes, atendimentos e também `Conversa` e `Mensagem`.
- `templates/index.html`: pagina institucional publica.
- `templates/base.html`: layout base das telas de login, admin e cliente.
- `templates/admin/`: telas do painel administrativo.
- `templates/cliente/`: telas da area do cliente.
- `static/style.css`: estilos do site e dos paineis.
- `static/script.js`: menu mobile e atualizacao automatica do ano no rodape.
- `static/assets/`: imagens e arquivos estaticos.
- `.env.example`: exemplo de configuracao local.
- `requirements.txt`: dependencias Python.

## Criar o banco no MySQL

Abra o MySQL e execute:

```sql
CREATE DATABASE site_contabilidade
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

O projeto usa `db.create_all()` no startup. Assim, quando o banco existir e o `.env` estiver correto, o Flask cria as tabelas automaticamente:

- `solicitacoes_atendimento`
- `usuarios`
- `clientes`
- `servicos_cliente`
- `pendencias`
- `atividades`
- `agendamentos`
- `conversas`
- `mensagens`

## Instalar dependencias

No PowerShell, dentro da pasta do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

As principais bibliotecas usadas sao `Flask`, `Flask-SQLAlchemy`, `Flask-Login`, `PyMySQL` e `python-dotenv`.

## Configurar o `.env`

Crie um arquivo `.env` na raiz do projeto usando o `.env.example` como base:

```env
FLASK_SECRET_KEY=troque-por-uma-chave-secreta-forte
FLASK_APP=app.py
MYSQL_USER=root
MYSQL_PASSWORD=sua-senha-do-mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=site_contabilidade
PUBLIC_BASE_URL=https://seu-dominio.com
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=seu-email@gmail.com
MAIL_PASSWORD=sua-senha-de-app
MAIL_DEFAULT_SENDER=seu-email@gmail.com
MAIL_USE_TLS=true
MAIL_USE_SSL=false
ACTIVATION_TOKEN_HOURS=24
```

Para Gmail, use uma **senha de app** em `MAIL_PASSWORD`, nunca a senha normal da conta.
Em producao, `PUBLIC_BASE_URL` deve ser o endereco HTTPS real do site.

## Rodar o projeto

Com o ambiente virtual ativado:

```powershell
py app.py
```

Acesse:

```text
http://127.0.0.1:5000
```

## Criar o primeiro administrador

Com o banco criado e o `.env` configurado, execute:

```powershell
flask criar-admin
```

O comando pergunta nome, e-mail e senha. Tambem e possivel passar os dados direto:

```powershell
flask criar-admin --nome "Administrador" --email "admin@email.com" --senha "senha-forte"
```

Depois acesse:

```text
http://127.0.0.1:5000/login
```

O usuario com tipo `admin` sera redirecionado para `/admin`.

## Usar o painel administrativo

Depois de entrar como administrador:

- `/admin`: mostra resumo com solicitacoes, clientes, servicos em andamento e pendencias abertas.
- `/admin/perfil`: mostra os dados da conta do administrador conectado.
- `/admin/solicitacoes`: lista solicitacoes de atendimento e permite filtrar por status.
- `/admin/solicitacoes/<id>`: mostra detalhes da solicitacao, observacao interna e acoes de aprovar ou rejeitar.
- `/admin/clientes`: lista clientes cadastrados.
- `/admin/servicos`: lista todos os servicos em andamento e permite atualizar seus status.
- `/admin/pendencias`: lista todas as pendencias abertas e permite resolve-las.
- `/admin/agenda` e `/admin/agenda/novo`: lista e cria agendamentos.
- `/admin/busca?q=texto`: pesquisa clientes, solicitacoes e servicos.
- `/admin/relatorios`: indicadores e graficos do sistema.
- `/admin/mensagens`: lista todas as conversas e destaca mensagens não lidas.
- `/admin/mensagens/<id>`: abre o chat, marca mensagens recebidas como lidas e permite responder ou fechar.
- `/admin/clientes/<id>/conversas/nova`: cria uma conversa geral ou vinculada a um serviço do cliente.
- `/admin/configuracoes`: informacoes basicas do sistema e usuario.
- `/admin/clientes/novo`: cadastra um cliente e cria o usuario de login dele.
- `/admin/clientes/<id>`: mostra dados do cliente, servicos e pendencias.

No detalhe do cliente, o administrador pode adicionar servicos, alterar status de servicos, adicionar pendencias e marcar pendencias como `pendente` ou `resolvida`.
Na lista de clientes, tambem e possivel filtrar por clientes com servicos, com pendencias abertas ou por tipo de cliente.

## Modulos do CRM

O painel registra automaticamente em `atividades` a criacao e aprovacao de solicitacoes, cadastro de clientes, criacao e atualizacao de servicos e criacao ou resolucao de pendencias. A tabela `agendamentos` guarda titulo, cliente, data, hora e status. Em bancos existentes, basta reiniciar a aplicacao: o `db.create_all()` cria as duas novas tabelas sem apagar dados.

Para testar: entre como administrador, confira os seis indicadores em `/admin`, crie um compromisso em `/admin/agenda/novo`, use a pesquisa da barra superior e abra `/admin/relatorios`. Depois entre como cliente para conferir a sidebar, os servicos, pendencias, proximos agendamentos e `/cliente/mensagens`. As rotas continuam protegidas por perfil.

## Fluxo de solicitacao de atendimento

O visitante pode abrir `/solicitar-atendimento` pelo botao `Solicitar Atendimento` na pagina principal ou pelo link abaixo do login.

O formulario publico coleta:

- nome;
- email;
- telefone;
- cpf_cnpj;
- tipo_cliente;
- servico_desejado;
- mensagem.

Ao enviar, a solicitacao entra como `pendente` em `solicitacoes_atendimento`. No painel administrativo:

1. Acesse `/admin/solicitacoes`.
2. Filtre por status, se necessario.
3. Abra os detalhes da solicitacao.
4. Altere o status para `em_contato`, registre uma observacao interna, aprove ou rejeite.

Ao aprovar, o sistema:

- bloqueia duplicidade de usuario com o mesmo e-mail;
- cria um `Usuario` com tipo `cliente`;
- cria um `Cliente` vinculado ao usuario;
- envia um link de ativacao assinado para o e-mail informado;
- marca `precisa_definir_senha=True`;
- marca a solicitacao como `convertida_cliente`.

O link expira no prazo definido por `ACTIVATION_TOKEN_HOURS` (24 horas por padrao).
Se o SMTP falhar, a aprovacao e desfeita e o administrador recebe uma mensagem de erro.

## Como o cliente faz login

Ao ter uma solicitacao aprovada, o cliente recebe um e-mail, abre o link de ativacao e cria a propria senha. Depois disso, usa o e-mail e essa senha em `/login`.

Quando o cliente entra com senha temporaria, ele e direcionado para `/cliente/definir-senha` e precisa cadastrar uma senha definitiva antes de acessar a area do cliente.

Depois do login, ele e redirecionado para `/cliente`, onde pode:

- ver resumo;
- ver seus servicos em `/cliente/servicos`;
- ver suas pendencias em `/cliente/pendencias`;
- atualizar telefone e endereco em `/cliente/perfil`.
- iniciar e acompanhar conversas em `/cliente/mensagens`.

## Sistema de mensagens

As tabelas `conversas` e `mensagens` são criadas automaticamente por `db.create_all()` ao reiniciar a aplicação. Uma conversa pertence a um cliente e pode, opcionalmente, apontar para um serviço. O administrador vê todas; o cliente vê apenas as próprias. Ao abrir o chat, as mensagens recebidas pelo usuário conectado são marcadas como lidas.

Para testar como administrador:

1. Entre em `/login` com uma conta admin.
2. Abra um cliente em `/admin/clientes` e clique em `Nova conversa`.
3. Escolha o assunto e, opcionalmente, um serviço; envie uma mensagem.
4. Confira o contador no dashboard e na sidebar depois que o cliente responder.
5. Use `Fechar conversa` para bloquear novos envios naquele atendimento.

Para testar como cliente:

1. Entre com a conta vinculada ao cliente usado no teste.
2. Abra `/cliente/mensagens`, leia a conversa e responda.
3. Clique em `Nova conversa` para iniciar outro assunto.
4. Confirme que as conversas de outros clientes não podem ser abertas e que os contadores somem após a leitura.

Mensagens vazias são rejeitadas e cada texto aceita até 2.000 caracteres. Os templates usam o escape padrão do Jinja e não aplicam `safe` ao conteúdo enviado.

## Testar o formulario publico

1. Abra a pagina inicial.
2. Preencha nome, telefone, e-mail e mensagem.
3. Selecione um servico, se quiser.
4. Clique em `Enviar mensagem`.
5. A pagina deve exibir uma mensagem de sucesso.

Para conferir no MySQL:

```sql
USE site_contabilidade;
SELECT id, nome, telefone, email, servico_desejado, status, criado_em FROM solicitacoes_atendimento ORDER BY id DESC;
```

## Cuidados basicos de seguranca

- Nunca salve senhas em texto puro. O projeto usa `generate_password_hash` e `check_password_hash`.
- Nao publique o arquivo `.env`.
- Use uma `FLASK_SECRET_KEY` forte em producao.
- Mantenha a senha SMTP somente no `.env` e use uma credencial exclusiva para o aplicativo.
- Use HTTPS em producao.
- Crie um usuario MySQL com permissao limitada ao banco do projeto.
- Desative `debug=True` em producao.
