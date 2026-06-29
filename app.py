from functools import wraps
from getpass import getpass
import secrets

import click
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from models import (
    STATUS_PENDENCIA,
    STATUS_SERVICO,
    STATUS_SOLICITACAO,
    SERVICOS_ATENDIMENTO,
    TIPOS_CLIENTE,
    Cliente,
    Pendencia,
    ServicoCliente,
    SolicitacaoAtendimento,
    Usuario,
    db,
)


# Edite esta lista para alterar, adicionar ou remover perguntas do FAQ da home.
# Cada item precisa apenas dos campos "pergunta" e "resposta".
FAQ_ITEMS = (
    {
        "pergunta": "Quanto custa abrir uma empresa?",
        "resposta": (
            "O valor depende do tipo de empresa, da atividade e das taxas dos órgãos responsáveis. "
            "Solicite um atendimento para receber uma análise e um orçamento adequado ao seu caso."
        ),
    },
    {
        "pergunta": "Preciso trocar de contador?",
        "resposta": (
            "Não necessariamente. Primeiro avaliamos sua situação e orientamos sobre a melhor solução. "
            "Se a troca for indicada, acompanhamos todo o processo de transição."
        ),
    },
    {
        "pergunta": "Quanto tempo demora?",
        "resposta": (
            "O prazo varia conforme o serviço e a análise dos órgãos envolvidos. Após receber seus dados, "
            "informamos uma estimativa e acompanhamos cada etapa."
        ),
    },
    {
        "pergunta": "Vocês atendem online?",
        "resposta": (
            "Sim. O atendimento e o envio de documentos podem ser realizados online, com segurança e "
            "acompanhamento durante todo o processo."
        ),
    },
    {
        "pergunta": "Quais documentos preciso?",
        "resposta": (
            "Os documentos variam de acordo com o serviço solicitado. Durante o primeiro atendimento, "
            "enviamos uma lista personalizada para evitar documentos desnecessários."
        ),
    },
)


login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Faça login para acessar esta página."
login_manager.login_message_category = "erro"


@login_manager.user_loader
def load_user(usuario_id):
    return db.session.get(Usuario, int(usuario_id))


def admin_required(func):
    # Garante que somente usuario admin entre nas rotas administrativas.
    @wraps(func)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.tipo != "admin":
            flash("Acesso permitido apenas para administradores.", "erro")
            return redirect(url_for("cliente_dashboard"))
        return func(*args, **kwargs)

    return wrapper


def cliente_required(func):
    # Garante que somente usuario cliente entre nas rotas da area do cliente.
    @wraps(func)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.tipo != "cliente":
            flash("Acesso permitido apenas para clientes.", "erro")
            return redirect(url_for("admin_dashboard"))
        if current_user.precisa_definir_senha and request.endpoint != "cliente_definir_senha":
            flash("Defina uma nova senha para continuar.", "erro")
            return redirect(url_for("cliente_definir_senha"))
        return func(*args, **kwargs)

    return wrapper


def get_cliente_atual():
    return Cliente.query.filter_by(usuario_id=current_user.id).first_or_404()


def atualizar_schema_simples():
    # Mantem o projeto sem migrations nesta etapa inicial.
    inspector = inspect(db.engine)
    if "usuarios" not in inspector.get_table_names():
        return

    colunas_usuario = {coluna["name"] for coluna in inspector.get_columns("usuarios")}
    comandos = []

    if "precisa_definir_senha" not in colunas_usuario:
        comandos.append("ALTER TABLE usuarios ADD COLUMN precisa_definir_senha BOOLEAN NOT NULL DEFAULT 0")
    if "senha_temporaria" not in colunas_usuario:
        comandos.append("ALTER TABLE usuarios ADD COLUMN senha_temporaria VARCHAR(80) NULL")

    for comando in comandos:
        db.session.execute(text(comando))
    if comandos:
        db.session.commit()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        # Nesta etapa inicial, o create_all facilita criar as novas tabelas.
        db.create_all()
        atualizar_schema_simples()

    # Rotas publicas do site institucional.
    @app.get("/")
    def index():
        return render_template("index.html", faq_items=FAQ_ITEMS)

    @app.route("/solicitar-atendimento", methods=["GET", "POST"])
    def solicitar_atendimento():
        if request.method == "POST":
            nome = (request.form.get("nome") or "").strip()
            email = (request.form.get("email") or "").strip().lower()
            telefone = (request.form.get("telefone") or "").strip()
            cpf_cnpj = (request.form.get("cpf_cnpj") or "").strip()
            tipo_cliente = (request.form.get("tipo_cliente") or "").strip()
            servico_desejado = (request.form.get("servico_desejado") or "").strip()
            mensagem = (request.form.get("mensagem") or "").strip()

            campos_obrigatorios = {
                "nome": nome,
                "email": email,
                "telefone": telefone,
                "cpf_cnpj": cpf_cnpj,
                "tipo_cliente": tipo_cliente,
                "servico_desejado": servico_desejado,
                "mensagem": mensagem,
            }
            faltando = [campo for campo, valor in campos_obrigatorios.items() if not valor]

            if faltando:
                flash("Preencha todos os campos para enviar a solicitação.", "erro")
                return redirect(url_for("solicitar_atendimento"))

            if tipo_cliente not in TIPOS_CLIENTE:
                flash("Tipo de cliente inválido.", "erro")
                return redirect(url_for("solicitar_atendimento"))

            if servico_desejado not in SERVICOS_ATENDIMENTO:
                flash("Serviço desejado inválido.", "erro")
                return redirect(url_for("solicitar_atendimento"))

            solicitacao = SolicitacaoAtendimento(
                nome=nome,
                email=email,
                telefone=telefone,
                cpf_cnpj=cpf_cnpj,
                tipo_cliente=tipo_cliente,
                servico_desejado=servico_desejado,
                mensagem=mensagem,
            )
            db.session.add(solicitacao)
            db.session.commit()

            flash(
                "Recebemos sua solicitação de atendimento. Nossa equipe irá analisar seus dados e entrará em contato em breve.",
                "sucesso",
            )
            return redirect(url_for("solicitar_atendimento"))

        return render_template(
            "solicitar_atendimento.html",
            tipos_cliente=TIPOS_CLIENTE,
            servicos_atendimento=SERVICOS_ATENDIMENTO,
        )

    # Rotas de autenticacao.
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            destino = "admin_dashboard" if current_user.tipo == "admin" else "cliente_dashboard"
            return redirect(url_for(destino))

        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            senha = request.form.get("senha") or ""
            usuario = Usuario.query.filter_by(email=email).first()

            if not usuario or not check_password_hash(usuario.senha_hash, senha):
                flash("E-mail ou senha inválidos.", "erro")
                return redirect(url_for("login"))

            login_user(usuario)
            flash("Login realizado com sucesso.", "sucesso")
            if usuario.tipo == "cliente" and usuario.precisa_definir_senha:
                destino = "cliente_definir_senha"
            else:
                destino = "admin_dashboard" if usuario.tipo == "admin" else "cliente_dashboard"
            return redirect(url_for(destino))

        return render_template("login.html")

    @app.get("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Você saiu da sua conta.", "sucesso")
        return redirect(url_for("login"))

    # Rotas do painel administrativo.
    @app.get("/admin")
    @admin_required
    def admin_dashboard():
        servicos_em_andamento = ServicoCliente.query.filter(
            ServicoCliente.status.in_(["solicitado", "em análise", "aguardando documentos"])
        ).count()
        resumo = {
            "solicitacoes": SolicitacaoAtendimento.query.filter_by(status="pendente").count(),
            "clientes": Cliente.query.count(),
            "servicos": servicos_em_andamento,
            "pendencias": Pendencia.query.filter_by(status="pendente").count(),
        }
        return render_template("admin/dashboard.html", resumo=resumo)

    @app.get("/admin/solicitacoes")
    @admin_required
    def admin_solicitacoes():
        status = (request.args.get("status") or "").strip()
        consulta = SolicitacaoAtendimento.query

        if status:
            if status not in STATUS_SOLICITACAO:
                flash("Status de solicitação inválido.", "erro")
                return redirect(url_for("admin_solicitacoes"))
            consulta = consulta.filter_by(status=status)

        solicitacoes = consulta.order_by(SolicitacaoAtendimento.criado_em.desc()).all()
        return render_template(
            "admin/solicitacoes.html",
            solicitacoes=solicitacoes,
            status_atual=status,
            status_solicitacao=STATUS_SOLICITACAO,
        )

    @app.get("/admin/solicitacoes/<int:id>")
    @admin_required
    def admin_solicitacao_detalhe(id):
        solicitacao = SolicitacaoAtendimento.query.get_or_404(id)
        return render_template(
            "admin/solicitacao_detalhe.html",
            solicitacao=solicitacao,
            status_solicitacao=STATUS_SOLICITACAO,
        )

    @app.post("/admin/solicitacoes/<int:id>/status")
    @admin_required
    def admin_solicitacao_status(id):
        solicitacao = SolicitacaoAtendimento.query.get_or_404(id)
        status = (request.form.get("status") or "").strip()
        observacao_admin = (request.form.get("observacao_admin") or "").strip()

        if status not in STATUS_SOLICITACAO:
            flash("Status de solicitação inválido.", "erro")
            return redirect(url_for("admin_solicitacao_detalhe", id=solicitacao.id))

        if status in ("aprovada", "convertida_cliente"):
            flash("Use a ação Aprovar para converter uma solicitação em cliente.", "erro")
            return redirect(url_for("admin_solicitacao_detalhe", id=solicitacao.id))

        solicitacao.status = status
        solicitacao.observacao_admin = observacao_admin or None
        db.session.commit()
        flash("Solicitação atualizada.", "sucesso")
        return redirect(url_for("admin_solicitacao_detalhe", id=solicitacao.id))

    @app.post("/admin/solicitacoes/<int:id>/aprovar")
    @admin_required
    def admin_solicitacao_aprovar(id):
        solicitacao = SolicitacaoAtendimento.query.get_or_404(id)
        observacao_admin = (request.form.get("observacao_admin") or "").strip()

        if solicitacao.status == "convertida_cliente":
            flash("Esta solicitação já foi convertida em cliente.", "erro")
            return redirect(url_for("admin_solicitacao_detalhe", id=solicitacao.id))

        if Usuario.query.filter_by(email=solicitacao.email).first():
            flash("Já existe um usuário com este e-mail. Revise o cadastro antes de aprovar.", "erro")
            return redirect(url_for("admin_solicitacao_detalhe", id=solicitacao.id))

        # Futuramente, substituir a senha temporaria por link de ativacao enviado por e-mail.
        senha_temporaria = secrets.token_urlsafe(8)
        usuario = Usuario(
            nome=solicitacao.nome,
            email=solicitacao.email,
            senha_hash=generate_password_hash(senha_temporaria),
            tipo="cliente",
            precisa_definir_senha=True,
            senha_temporaria=senha_temporaria,
        )
        cliente = Cliente(
            usuario=usuario,
            telefone=solicitacao.telefone,
            cpf_cnpj=solicitacao.cpf_cnpj,
            tipo_cliente=solicitacao.tipo_cliente,
        )

        solicitacao.status = "convertida_cliente"
        solicitacao.observacao_admin = observacao_admin or solicitacao.observacao_admin
        db.session.add(cliente)
        db.session.commit()

        flash(
            f"Solicitação aprovada e cliente criado. Senha temporária: {senha_temporaria}",
            "sucesso",
        )
        return redirect(url_for("admin_cliente_detalhe", id=cliente.id))

    @app.post("/admin/solicitacoes/<int:id>/rejeitar")
    @admin_required
    def admin_solicitacao_rejeitar(id):
        solicitacao = SolicitacaoAtendimento.query.get_or_404(id)
        observacao_admin = (request.form.get("observacao_admin") or "").strip()

        solicitacao.status = "rejeitada"
        solicitacao.observacao_admin = observacao_admin or solicitacao.observacao_admin
        db.session.commit()
        flash("Solicitação rejeitada.", "sucesso")
        return redirect(url_for("admin_solicitacao_detalhe", id=solicitacao.id))

    @app.get("/admin/clientes")
    @admin_required
    def admin_clientes():
        clientes = Cliente.query.join(Usuario).order_by(Usuario.nome.asc()).all()
        return render_template("admin/clientes.html", clientes=clientes)

    @app.route("/admin/clientes/novo", methods=["GET", "POST"])
    @admin_required
    def admin_cliente_novo():
        if request.method == "POST":
            nome = (request.form.get("nome") or "").strip()
            email = (request.form.get("email") or "").strip().lower()
            senha = request.form.get("senha") or ""
            telefone = (request.form.get("telefone") or "").strip()
            cpf_cnpj = (request.form.get("cpf_cnpj") or "").strip()
            endereco = (request.form.get("endereco") or "").strip()
            tipo_cliente = (request.form.get("tipo_cliente") or "").strip()

            if not nome or not email or not senha or not tipo_cliente:
                flash("Preencha nome, e-mail, senha e tipo de cliente.", "erro")
                return redirect(url_for("admin_cliente_novo"))

            if tipo_cliente not in TIPOS_CLIENTE:
                flash("Tipo de cliente inválido.", "erro")
                return redirect(url_for("admin_cliente_novo"))

            if Usuario.query.filter_by(email=email).first():
                flash("Já existe um usuário com este e-mail.", "erro")
                return redirect(url_for("admin_cliente_novo"))

            usuario = Usuario(
                nome=nome,
                email=email,
                senha_hash=generate_password_hash(senha),
                tipo="cliente",
            )
            cliente = Cliente(
                usuario=usuario,
                telefone=telefone or None,
                cpf_cnpj=cpf_cnpj or None,
                endereco=endereco or None,
                tipo_cliente=tipo_cliente,
            )

            db.session.add(cliente)
            db.session.commit()
            flash("Cliente cadastrado com sucesso.", "sucesso")
            return redirect(url_for("admin_cliente_detalhe", id=cliente.id))

        return render_template("admin/cliente_novo.html", tipos_cliente=TIPOS_CLIENTE)

    @app.get("/admin/clientes/<int:id>")
    @admin_required
    def admin_cliente_detalhe(id):
        cliente = Cliente.query.get_or_404(id)
        return render_template(
            "admin/cliente_detalhe.html",
            cliente=cliente,
            status_servico=STATUS_SERVICO,
            status_pendencia=STATUS_PENDENCIA,
        )

    @app.post("/admin/clientes/<int:id>/servicos/novo")
    @admin_required
    def admin_servico_novo(id):
        cliente = Cliente.query.get_or_404(id)
        titulo = (request.form.get("titulo") or "").strip()
        descricao = (request.form.get("descricao") or "").strip()

        if not titulo:
            flash("Informe o título do serviço.", "erro")
            return redirect(url_for("admin_cliente_detalhe", id=cliente.id))

        servico = ServicoCliente(cliente=cliente, titulo=titulo, descricao=descricao or None)
        db.session.add(servico)
        db.session.commit()
        flash("Serviço adicionado ao cliente.", "sucesso")
        return redirect(url_for("admin_cliente_detalhe", id=cliente.id))

    @app.post("/admin/clientes/<int:id>/pendencias/novo")
    @admin_required
    def admin_pendencia_nova(id):
        cliente = Cliente.query.get_or_404(id)
        titulo = (request.form.get("titulo") or "").strip()
        descricao = (request.form.get("descricao") or "").strip()

        if not titulo:
            flash("Informe o título da pendência.", "erro")
            return redirect(url_for("admin_cliente_detalhe", id=cliente.id))

        pendencia = Pendencia(cliente=cliente, titulo=titulo, descricao=descricao or None)
        db.session.add(pendencia)
        db.session.commit()
        flash("Pendência adicionada ao cliente.", "sucesso")
        return redirect(url_for("admin_cliente_detalhe", id=cliente.id))

    @app.post("/admin/servicos/<int:id>/status")
    @admin_required
    def admin_servico_status(id):
        servico = ServicoCliente.query.get_or_404(id)
        status = (request.form.get("status") or "").strip()

        if status not in STATUS_SERVICO:
            flash("Status de serviço inválido.", "erro")
            return redirect(url_for("admin_cliente_detalhe", id=servico.cliente_id))

        servico.status = status
        db.session.commit()
        flash("Status do serviço atualizado.", "sucesso")
        return redirect(url_for("admin_cliente_detalhe", id=servico.cliente_id))

    @app.post("/admin/pendencias/<int:id>/status")
    @admin_required
    def admin_pendencia_status(id):
        pendencia = Pendencia.query.get_or_404(id)
        status = (request.form.get("status") or "").strip()

        if status not in STATUS_PENDENCIA:
            flash("Status de pendência inválido.", "erro")
            return redirect(url_for("admin_cliente_detalhe", id=pendencia.cliente_id))

        pendencia.status = status
        db.session.commit()
        flash("Pendência atualizada.", "sucesso")
        return redirect(url_for("admin_cliente_detalhe", id=pendencia.cliente_id))

    # Rotas da area do cliente.
    @app.route("/cliente/definir-senha", methods=["GET", "POST"])
    @login_required
    def cliente_definir_senha():
        if current_user.tipo != "cliente":
            flash("Acesso permitido apenas para clientes.", "erro")
            return redirect(url_for("admin_dashboard"))

        if not current_user.precisa_definir_senha:
            return redirect(url_for("cliente_dashboard"))

        if request.method == "POST":
            senha = request.form.get("senha") or ""
            confirmar_senha = request.form.get("confirmar_senha") or ""

            if len(senha) < 8:
                flash("A nova senha deve ter pelo menos 8 caracteres.", "erro")
                return redirect(url_for("cliente_definir_senha"))

            if senha != confirmar_senha:
                flash("As senhas não conferem.", "erro")
                return redirect(url_for("cliente_definir_senha"))

            current_user.senha_hash = generate_password_hash(senha)
            current_user.precisa_definir_senha = False
            current_user.senha_temporaria = None
            db.session.commit()
            flash("Senha definida com sucesso.", "sucesso")
            return redirect(url_for("cliente_dashboard"))

        return render_template("cliente/definir_senha.html")

    @app.get("/cliente")
    @cliente_required
    def cliente_dashboard():
        cliente = get_cliente_atual()
        resumo = {
            "servicos": ServicoCliente.query.filter_by(cliente_id=cliente.id).count(),
            "pendencias": Pendencia.query.filter_by(cliente_id=cliente.id, status="pendente").count(),
            "finalizados": ServicoCliente.query.filter_by(cliente_id=cliente.id, status="finalizado").count(),
        }
        return render_template("cliente/dashboard.html", cliente=cliente, resumo=resumo)

    @app.get("/cliente/servicos")
    @cliente_required
    def cliente_servicos():
        cliente = get_cliente_atual()
        servicos = ServicoCliente.query.filter_by(cliente_id=cliente.id).order_by(
            ServicoCliente.criado_em.desc()
        )
        return render_template("cliente/servicos.html", cliente=cliente, servicos=servicos)

    @app.get("/cliente/pendencias")
    @cliente_required
    def cliente_pendencias():
        cliente = get_cliente_atual()
        pendencias = Pendencia.query.filter_by(cliente_id=cliente.id).order_by(Pendencia.criado_em.desc())
        return render_template("cliente/pendencias.html", cliente=cliente, pendencias=pendencias)

    @app.route("/cliente/perfil", methods=["GET", "POST"])
    @cliente_required
    def cliente_perfil():
        cliente = get_cliente_atual()

        if request.method == "POST":
            cliente.telefone = (request.form.get("telefone") or "").strip() or None
            cliente.endereco = (request.form.get("endereco") or "").strip() or None
            db.session.commit()
            flash("Perfil atualizado com sucesso.", "sucesso")
            return redirect(url_for("cliente_perfil"))

        return render_template("cliente/perfil.html", cliente=cliente)

    # Comando de terminal para criar o primeiro usuario administrador.
    @app.cli.command("criar-admin")
    @click.option("--nome", prompt=True, help="Nome do administrador.")
    @click.option("--email", prompt=True, help="E-mail de login do administrador.")
    @click.option("--senha", default=None, help="Senha do administrador.")
    def criar_admin(nome, email, senha):
        email = email.strip().lower()

        if Usuario.query.filter_by(email=email).first():
            click.echo("Ja existe um usuario com este e-mail.")
            return

        if not senha:
            senha = getpass("Senha do administrador: ")
            confirmar = getpass("Confirme a senha: ")
            if senha != confirmar:
                click.echo("As senhas nao conferem.")
                return

        usuario = Usuario(
            nome=nome.strip(),
            email=email,
            senha_hash=generate_password_hash(senha),
            tipo="admin",
        )
        db.session.add(usuario)
        db.session.commit()
        click.echo("Administrador criado com sucesso.")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
