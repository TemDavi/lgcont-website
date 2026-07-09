# Luciano Garces Contabilidade e Pericias

Meu primeiro projeto Web.
Website desenvolvido para o escritório de contabilidade "Luciano Garcês Contabilidade e Pericias"

![alt text](static/assets/home.png)

## 📖 Sobre

Desenvolvido com **Python** utilizando o framework **Flask** no backend. O sistema foi projetado para oferecer uma experiência intuitiva, facilitando a comunicação entre clientes e a empresa. além de disponibilizar uma área administrativa para gerenciamento do conteúdo e dos atendimentos.

### ✨ Principais funcionalidades

* 🏠 Página inicial com apresentação da empresa e dos serviços oferecidos;
* 👤 Área do cliente para acesso a funcionalidades exclusivas;
* ⚙️ Painel administrativo para gerenciamento do site;
* 📧 Integração com e-mail para envio e recebimento de solicitações;
* 💬 Sistema de atendimento por mensagens diretamente no site;
* 📱 Redirecionamento rápido para atendimento via WhatsApp;
* 📲 Interface responsiva para computadores, tablets e dispositivos móveis.

## 🛠 Tecnologias

### Backend
- Python
- Flask

### Frontend
- HTML5
- CSS3
- JavaScript

### Banco de dados
- MySQL
- SQLAlchemy ORM
- Flask-SQLAlchemy
- PyMySQL

### Autenticação, segurança e configuração
- Flask-Login
- Werkzeug Security para hash e validação de senhas
- itsdangerous para geração e validação de tokens de ativação
- python-dotenv para variáveis de ambiente
- Conexão MySQL com suporte a SSL

### E-mail
- SMTP com `smtplib` e `email.message`
- Templates HTML de e-mail com Jinja2

### Ferramentas e ambiente
- Git
- GitHub
- Visual Studio Code
- Ambiente virtual Python (`venv`)
- DBeaver para administração/teste do banco de dados

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

## Rodar o projeto

Com o ambiente virtual ativado:

```powershell
py app.py
```

Acesse:

```text
http://127.0.0.1:5000
```
