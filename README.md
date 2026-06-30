# Luciano Garces Contabilidade e Pericias

Aplicacao Flask para o site institucional, solicitacoes de atendimento, painel administrativo e area do cliente.

## Estrutura

- `app.py`: cria a aplicacao Flask, inicializa Flask-Login, registra rotas publicas, administrativas e de cliente.
- `config.py`: le as variaveis do `.env` e monta a conexao MySQL para o SQLAlchemy.
- `models.py`: define `SolicitacaoAtendimento`, `Usuario`, `Cliente`, `ServicoCliente` e `Pendencia`.
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
- `/admin/solicitacoes`: lista solicitacoes de atendimento e permite filtrar por status.
- `/admin/solicitacoes/<id>`: mostra detalhes da solicitacao, observacao interna e acoes de aprovar ou rejeitar.
- `/admin/clientes`: lista clientes cadastrados.
- `/admin/clientes/novo`: cadastra um cliente e cria o usuario de login dele.
- `/admin/clientes/<id>`: mostra dados do cliente, servicos e pendencias.

No detalhe do cliente, o administrador pode adicionar servicos, alterar status de servicos, adicionar pendencias e marcar pendencias como `pendente` ou `resolvida`.

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
