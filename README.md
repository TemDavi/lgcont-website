<p align="center">
  <img src="static/assets/WebSite.png" alt="LG Contabilidade" width="100%">
</p>

# Luciano Garcês Contabilidade e Perícias

Sistema web em Flask para o escritório Luciano Garcês Contabilidade e Perícias, com site institucional, solicitação de atendimento, área do cliente e painel administrativo.

![Página inicial](static/assets/home.png)

## 📖 Sobre

O projeto centraliza o atendimento do escritório em uma aplicação Flask. A parte pública apresenta os serviços e permite solicitar atendimento. A área administrativa permite acompanhar solicitações, clientes, serviços, pendências, agenda, mensagens, configurações, relatórios e backups. A área do cliente permite acompanhar serviços, pendências, conversas e dados da própria conta.

## ✨ Principais Funcionalidades

- 🏠 Página inicial institucional com serviços, sobre, diferenciais e FAQ.
- 📝 Formulário público de solicitação de atendimento.
- 👤 Login com separação entre administrador e cliente.
- 💼 Área do cliente com painel, serviços, pendências, perfil, configurações e mensagens.
- ⚙️ Painel administrativo com clientes, solicitações, serviços, pendências, agenda, mensagens, busca e relatórios.
- 📧 Aprovação de solicitações com envio de link para definição de senha.
- 🔐 Redefinição de senha de cliente por link enviado por e-mail.
- 💬 Conversas internas entre cliente e administração, com edição e exclusão lógica de mensagens.
- 🛠️ Configurações administrativas de conta, empresa, atendimento, personalização, segurança e backups.
- 💾 Backups JSON gerados pelo painel administrativo.
- 🗺️ Sitemap e robots.txt gerados para as páginas públicas.
- 🛡️ Proteção CSRF em formulários.
- 🚦 Limitação de tentativas de login com Flask-Limiter.
- 🔑 Senhas e senhas temporárias armazenadas como hash.
- 🌒 Tema claro/escuro e layout responsivo.

## 🛠 Tecnologias

### Backend

- Python
- Flask
- Jinja2

### Banco de Dados

- MySQL
- SQLAlchemy ORM
- Flask-SQLAlchemy
- PyMySQL

### Autenticação e Segurança

- Flask-Login
- Flask-WTF / CSRFProtect
- Flask-Limiter
- Werkzeug Security para hash e validação de senhas
- itsdangerous para tokens de ativação e redefinição
- python-dotenv para variáveis de ambiente
- Conexão MySQL com suporte a SSL

### Frontend

- HTML5
- CSS3
- JavaScript

### E-mail

- SMTP com `smtplib` e `email.message`
- Templates HTML de e-mail com Jinja2

## 📁 Estrutura do Projeto

- `app.py`: cria a aplicação Flask e mantém o registro das rotas atuais.
- `config.py`: carrega variáveis do `.env` e configura banco, e-mail, tokens, CSRF e rate limit.
- `models.py`: define os modelos SQLAlchemy do sistema.
- `extensions.py`: centraliza extensões Flask como `login_manager`, `csrf` e `limiter`.
- `validators.py`: concentra validações de e-mail, documento, CEP e estado.
- `seo.py`: concentra sitemap, robots e helpers de SEO.
- `backups.py`: concentra geração e caminho dos backups JSON.
- `email_service.py`: envia e-mails de ativação e redefinição de senha.
- `templates/`: telas públicas, administrativas, área do cliente, e-mails e parciais.
- `static/`: CSS, JavaScript e assets do site.
- `tests/`: testes automatizados principais do fluxo de configurações, CSRF, login e segurança.
- `.env.example`: exemplo de configuração local.
- `requirements.txt`: dependências Python.
