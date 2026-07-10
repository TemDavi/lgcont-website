from functools import wraps
from getpass import getpass
import secrets
from datetime import date, datetime
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

import os

import click
from flask import Flask, Response, current_app, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, inspect, or_, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from email_service import EmailDeliveryError, enviar_email_ativacao, enviar_email_reset_senha
from models import (
    STATUS_PENDENCIA,
    STATUS_SERVICO,
    STATUS_SOLICITACAO,
    SERVICOS_ATENDIMENTO,
    TIPOS_CLIENTE,
    STATUS_AGENDAMENTO,
    Agendamento,
    Atividade,
    Cliente,
    Conversa,
    Mensagem,
    Pendencia,
    ServicoCliente,
    SolicitacaoAtendimento,
    Usuario,
    db,
)

STATUS_SERVICO_ATIVO = ("solicitado", "em análise", "aguardando documentos")
SITEMAP_BASE_URL = "https://lucianogarcescontabilidade.com.br"
ROBOTS_TXT = """User-agent: *
Allow: /

Sitemap: https://lucianogarcescontabilidade.com.br/sitemap.xml
"""


def registrar_atividade(tipo, descricao, usuario_id=None, cliente_id=None):
    db.session.add(Atividade(tipo=tipo, descricao=descricao, usuario_id=usuario_id, cliente_id=cliente_id))


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


SITEMAP_PUBLIC_PAGES = (
    {
        "endpoint": "index",
        "path": "/",
        "template": "templates/index.html",
        "changefreq": "weekly",
        "priority": "1.0",
    },
    {
        "endpoint": "index",
        "path": "/#servicos",
        "template": "templates/index.html",
        "changefreq": "monthly",
        "priority": "0.9",
    },
    {
        "endpoint": "index",
        "path": "/#sobre",
        "template": "templates/index.html",
        "changefreq": "yearly",
        "priority": "0.8",
    },
    {
        "endpoint": "solicitar_atendimento",
        "path": "/solicitar-atendimento",
        "template": "templates/solicitar_atendimento.html",
        "changefreq": "monthly",
        "priority": "0.8",
    },
    {
        "endpoint": "index",
        "path": "/#diferenciais",
        "template": "templates/index.html",
        "changefreq": "yearly",
        "priority": "0.7",
    },
    {
        "endpoint": "index",
        "path": "/#faq",
        "template": "templates/index.html",
        "changefreq": "yearly",
        "priority": "0.7",
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


def contar_mensagens_nao_lidas(cliente_id=None):
    consulta = Mensagem.query.join(Conversa).filter(
        Mensagem.lida.is_(False), Mensagem.usuario_id != current_user.id
    )
    if cliente_id is not None:
        consulta = consulta.filter(Conversa.cliente_id == cliente_id)
    return consulta.count()


def marcar_mensagens_como_lidas(conversa):
    alteradas = Mensagem.query.filter(
        Mensagem.conversa_id == conversa.id,
        Mensagem.usuario_id != current_user.id,
        Mensagem.lida.is_(False),
    ).update({Mensagem.lida: True}, synchronize_session=False)
    if alteradas:
        db.session.commit()


def validar_texto_mensagem():
    texto_mensagem = (request.form.get("texto") or "").strip()
    if not texto_mensagem:
        return None, "A mensagem não pode estar vazia."
    if len(texto_mensagem) > 2000:
        return None, "A mensagem deve ter no máximo 2000 caracteres."
    return texto_mensagem, None


def enviar_mensagem(conversa, texto_mensagem):
    mensagem = Mensagem(conversa=conversa, usuario=current_user, texto=texto_mensagem)
    conversa.atualizado_em = datetime.utcnow()
    db.session.add(mensagem)
    registrar_atividade(
        "mensagem",
        f"Mensagem enviada na conversa {conversa.assunto}.",
        current_user.id,
        conversa.cliente_id,
    )
    db.session.commit()


def gerar_token_ativacao(usuario):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps(
        {"usuario_id": usuario.id, "email": usuario.email},
        salt="ativacao-cliente",
    )


def validar_token_ativacao(token):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    validade = current_app.config["ACTIVATION_TOKEN_HOURS"] * 3600
    return serializer.loads(token, salt="ativacao-cliente", max_age=validade)


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


def obter_lastmod(*caminhos_relativos):
    # Usa a data do arquivo mais recente como lastmod quando ha template/local conhecido.
    datas = []
    raiz = Path(current_app.root_path)
    for caminho_relativo in caminhos_relativos:
        if not caminho_relativo:
            continue
        caminho = raiz / caminho_relativo
        if caminho.exists():
            datas.append(datetime.fromtimestamp(caminho.stat().st_mtime).date())
    return max(datas).isoformat() if datas else None


def montar_url_absoluta(caminho):
    caminho_normalizado = caminho if caminho.startswith("/") else f"/{caminho}"
    return f"{SITEMAP_BASE_URL}{caminho_normalizado}"


def rota_publica_para_sitemap(regra):
    # Mantem fora do sitemap areas privadas, auth, rotas tecnicas e URLs com parametros.
    if "GET" not in regra.methods or regra.arguments:
        return False
    if regra.endpoint in {"static", "login", "logout", "ativar_conta", "sitemap_xml", "robots_txt"}:
        return False
    if regra.endpoint.startswith(("admin_", "cliente_")):
        return False
    if regra.rule.startswith(("/admin", "/cliente", "/api")):
        return False
    if regra.rule in {"/sitemap.xml", "/robots.txt"}:
        return False
    return True


def registrar_paginas_publicas_sitemap(app):
    # As paginas conhecidas carregam metadados SEO especificos; novas rotas
    # publicas simples entram automaticamente com valores institucionais padrao.
    paginas = [dict(pagina) for pagina in SITEMAP_PUBLIC_PAGES]
    caminhos_registrados = {pagina["path"] for pagina in paginas}

    for regra in app.url_map.iter_rules():
        if not rota_publica_para_sitemap(regra) or regra.rule in caminhos_registrados:
            continue
        paginas.append(
            {
                "endpoint": regra.endpoint,
                "path": regra.rule,
                "template": "app.py",
                "changefreq": "yearly",
                "priority": "0.7",
            }
        )
        caminhos_registrados.add(regra.rule)
    return paginas


def gerar_sitemap_xml(paginas):
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for pagina in paginas:
        url = ET.SubElement(urlset, "url")
        ET.SubElement(url, "loc").text = montar_url_absoluta(pagina["path"])

        lastmod = obter_lastmod(pagina.get("template"))
        if lastmod:
            ET.SubElement(url, "lastmod").text = lastmod

        ET.SubElement(url, "changefreq").text = pagina["changefreq"]
        ET.SubElement(url, "priority").text = pagina["priority"]

    xml_bruto = ET.tostring(urlset, encoding="utf-8")
    return minidom.parseString(xml_bruto).toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        # Nesta etapa inicial, o create_all facilita criar as novas tabelas.
        db.create_all()
        atualizar_schema_simples()

    @app.context_processor
    def disponibilizar_contador_mensagens():
        if not current_user.is_authenticated:
            return {"mensagens_nao_lidas": 0}
        if current_user.tipo == "cliente":
            cliente = Cliente.query.filter_by(usuario_id=current_user.id).first()
            total = contar_mensagens_nao_lidas(cliente.id) if cliente else 0
        else:
            total = contar_mensagens_nao_lidas()
        return {"mensagens_nao_lidas": total}

    @app.get("/sitemap.xml")
    def sitemap_xml():
        paginas = registrar_paginas_publicas_sitemap(app)
        xml = gerar_sitemap_xml(paginas)
        return Response(xml, content_type="application/xml")

    @app.get("/robots.txt")
    def robots_txt():
        caminho_robots = Path(current_app.root_path) / "robots.txt"
        conteudo = caminho_robots.read_text(encoding="utf-8") if caminho_robots.exists() else ROBOTS_TXT
        return Response(conteudo, mimetype="text/plain")

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
            registrar_atividade("solicitacao", f"Nova solicitação criada por {nome}.")
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

    @app.route("/ativar-conta/<token>", methods=["GET", "POST"])
    def ativar_conta(token):
        try:
            dados_token = validar_token_ativacao(token)
        except SignatureExpired:
            flash("Este link de ativação expirou. Entre em contato para solicitar um novo.", "erro")
            return redirect(url_for("login"))
        except BadSignature:
            flash("Link de ativação inválido.", "erro")
            return redirect(url_for("login"))

        usuario = db.session.get(Usuario, dados_token.get("usuario_id"))
        if not usuario or usuario.email != dados_token.get("email") or usuario.tipo != "cliente":
            flash("Link de ativação inválido.", "erro")
            return redirect(url_for("login"))
        if not usuario.precisa_definir_senha:
            flash("Esta conta já foi ativada. Faça login para continuar.", "sucesso")
            return redirect(url_for("login"))

        if request.method == "POST":
            senha = request.form.get("senha") or ""
            confirmar_senha = request.form.get("confirmar_senha") or ""
            if len(senha) < 8:
                flash("A senha deve ter pelo menos 8 caracteres.", "erro")
                return redirect(url_for("ativar_conta", token=token))
            if senha != confirmar_senha:
                flash("As senhas não conferem.", "erro")
                return redirect(url_for("ativar_conta", token=token))

            usuario.senha_hash = generate_password_hash(senha)
            usuario.precisa_definir_senha = False
            usuario.senha_temporaria = None
            db.session.commit()
            flash("Senha cadastrada. Agora você já pode entrar na área do cliente.", "sucesso")
            return redirect(url_for("login"))

        return render_template("ativar_conta.html", token=token)

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
        inicio_mes = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        servicos_em_andamento = ServicoCliente.query.filter(ServicoCliente.status.in_(STATUS_SERVICO_ATIVO)).count()
        resumo = {
            "solicitacoes": SolicitacaoAtendimento.query.filter_by(status="pendente").count(),
            "clientes": Cliente.query.count(),
            "servicos": servicos_em_andamento,
            "pendencias": Pendencia.query.filter_by(status="pendente").count(),
            "finalizados": ServicoCliente.query.filter_by(status="finalizado").count(),
            "novos_clientes": Cliente.query.filter(Cliente.criado_em >= inicio_mes).count(),
            "mensagens": contar_mensagens_nao_lidas(),
        }
        return render_template("admin/dashboard.html", resumo=resumo,
            solicitacoes=SolicitacaoAtendimento.query.order_by(SolicitacaoAtendimento.criado_em.desc()).limit(5).all(),
            clientes=Cliente.query.order_by(Cliente.criado_em.desc()).limit(5).all(),
            servicos=ServicoCliente.query.filter(ServicoCliente.status.in_(STATUS_SERVICO_ATIVO)).order_by(ServicoCliente.atualizado_em.desc()).limit(5).all(),
            pendencias=Pendencia.query.filter_by(status="pendente").order_by(Pendencia.criado_em.desc()).limit(5).all(),
            atividades=Atividade.query.order_by(Atividade.criado_em.desc()).limit(8).all(),
            agenda=Agendamento.query.filter_by(data=date.today(), status="agendado").order_by(Agendamento.hora).limit(5).all())

    @app.get("/admin/perfil")
    @admin_required
    def admin_perfil():
        return render_template("admin/perfil.html")

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

        email_solicitacao = solicitacao.email.strip().lower()
        if Usuario.query.filter_by(email=email_solicitacao).first():
            flash("Já existe um usuário com este e-mail. Revise o cadastro antes de aprovar.", "erro")
            return redirect(url_for("admin_solicitacao_detalhe", id=solicitacao.id))

        # A senha aleatoria nunca e mostrada: o cliente criara a propria pelo link.
        senha_inutilizavel = secrets.token_urlsafe(32)
        usuario = Usuario(
            nome=solicitacao.nome,
            email=email_solicitacao,
            senha_hash=generate_password_hash(senha_inutilizavel),
            tipo="cliente",
            precisa_definir_senha=True,
            senha_temporaria=None,
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

        try:
            db.session.flush()
            registrar_atividade("solicitacao", f"Solicitação de {solicitacao.nome} aprovada.", current_user.id, cliente.id)
            registrar_atividade("cliente", f"Cliente {cliente.usuario.nome} cadastrado.", current_user.id, cliente.id)
            token = gerar_token_ativacao(usuario)
            link = current_app.config["PUBLIC_BASE_URL"] + url_for("ativar_conta", token=token)
            enviar_email_ativacao(usuario.email, usuario.nome, link)
            db.session.commit()
        except IntegrityError:
            # Evita erro 500 se duas aprovações do mesmo e-mail ocorrerem ao mesmo tempo.
            db.session.rollback()
            current_app.logger.warning(
                "Aprovação interrompida porque o e-mail já estava cadastrado."
            )
            usuario_existente = Usuario.query.filter_by(email=email_solicitacao).first()
            if usuario_existente and usuario_existente.cliente:
                flash("Esta solicitação já possui um cliente cadastrado.", "erro")
                return redirect(url_for("admin_cliente_detalhe", id=usuario_existente.cliente.id))
            flash("Já existe um usuário com este e-mail. Revise o cadastro antes de aprovar.", "erro")
            return redirect(url_for("admin_solicitacao_detalhe", id=solicitacao.id))
        except EmailDeliveryError as erro:
            db.session.rollback()
            current_app.logger.exception("Falha ao enviar o e-mail de ativação do cliente.")
            flash(f"A solicitação não foi aprovada: {erro}", "erro")
            return redirect(url_for("admin_solicitacao_detalhe", id=solicitacao.id))

        flash("Solicitação aprovada. O e-mail para criação da senha foi enviado.", "sucesso")
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
        filtro = (request.args.get("filtro") or "").strip()
        tipo_cliente = (request.args.get("tipo_cliente") or "").strip()
        consulta = Cliente.query.join(Usuario)

        if filtro == "com_servicos":
            consulta = consulta.filter(Cliente.servicos.any())
        elif filtro == "pendencias_abertas":
            consulta = consulta.filter(Cliente.pendencias.any(Pendencia.status == "pendente"))
        elif filtro == "tipo":
            if tipo_cliente and tipo_cliente not in TIPOS_CLIENTE:
                flash("Tipo de cliente inválido.", "erro")
                return redirect(url_for("admin_clientes"))
            if tipo_cliente:
                consulta = consulta.filter(Cliente.tipo_cliente == tipo_cliente)
        elif filtro:
            flash("Filtro de clientes inválido.", "erro")
            return redirect(url_for("admin_clientes"))

        clientes = consulta.order_by(Usuario.nome.asc()).all()
        return render_template(
            "admin/clientes.html",
            clientes=clientes,
            filtro_atual=filtro,
            tipo_atual=tipo_cliente,
            tipos_cliente=TIPOS_CLIENTE,
        )

    @app.get("/admin/servicos")
    @admin_required
    def admin_servicos():
        status = (request.args.get("status") or "").strip()
        consulta = ServicoCliente.query.join(Cliente).join(Usuario)
        if status:
            if status not in STATUS_SERVICO: return redirect(url_for("admin_servicos"))
            consulta = consulta.filter(ServicoCliente.status == status)
        servicos = consulta.order_by(ServicoCliente.atualizado_em.desc()).all()
        return render_template("admin/servicos.html", servicos=servicos, status_servico=STATUS_SERVICO, status_atual=status)

    @app.get("/admin/pendencias")
    @admin_required
    def admin_pendencias():
        status = (request.args.get("status") or "").strip()
        consulta = Pendencia.query.join(Cliente).join(Usuario)
        if status:
            if status not in STATUS_PENDENCIA: return redirect(url_for("admin_pendencias"))
            consulta = consulta.filter(Pendencia.status == status)
        pendencias = consulta.order_by(Pendencia.criado_em.desc()).all()
        return render_template(
            "admin/pendencias.html",
            pendencias=pendencias,
            status_pendencia=STATUS_PENDENCIA,
            status_atual=status,
        )

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
            db.session.flush()
            registrar_atividade("cliente", f"Cliente {usuario.nome} cadastrado.", current_user.id, cliente.id)
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

    @app.post("/admin/clientes/<int:id>/resetar-senha")
    @admin_required
    def admin_cliente_resetar_senha(id):
        cliente = Cliente.query.get_or_404(id)
        usuario = cliente.usuario

        if usuario.tipo != "cliente":
            flash("Apenas senhas de clientes podem ser redefinidas por esta tela.", "erro")
            return redirect(url_for("admin_cliente_detalhe", id=cliente.id))

        senha_inutilizavel = secrets.token_urlsafe(32)
        usuario.senha_hash = generate_password_hash(senha_inutilizavel)
        usuario.precisa_definir_senha = True
        usuario.senha_temporaria = None

        try:
            db.session.flush()
            registrar_atividade(
                "cliente",
                f"Redefinição de senha solicitada para {usuario.nome}.",
                current_user.id,
                cliente.id,
            )
            token = gerar_token_ativacao(usuario)
            link = current_app.config["PUBLIC_BASE_URL"] + url_for("ativar_conta", token=token)
            enviar_email_reset_senha(usuario.email, usuario.nome, link)
            db.session.commit()
        except EmailDeliveryError as erro:
            db.session.rollback()
            current_app.logger.exception("Falha ao enviar o e-mail de redefinição de senha.")
            flash(f"A senha não foi redefinida: {erro}", "erro")
            return redirect(url_for("admin_cliente_detalhe", id=cliente.id))
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Falha ao redefinir a senha do cliente.")
            flash("Não foi possível redefinir a senha agora. Tente novamente.", "erro")
            return redirect(url_for("admin_cliente_detalhe", id=cliente.id))

        flash("Senha antiga invalidada. O e-mail para criação da nova senha foi enviado.", "sucesso")
        return redirect(url_for("admin_cliente_detalhe", id=cliente.id))

    @app.get("/admin/clientes/<int:id>/remover")
    @admin_required
    def admin_cliente_confirmar_remocao(id):
        cliente = Cliente.query.get_or_404(id)
        return render_template("admin/cliente_remover.html", cliente=cliente)

    @app.post("/admin/clientes/<int:id>/remover")
    @admin_required
    def admin_cliente_remover(id):
        cliente = Cliente.query.get_or_404(id)
        usuario = cliente.usuario
        nome_cliente = usuario.nome
        email_cliente = usuario.email.strip().lower()

        try:
            conversa_ids = [
                conversa_id
                for (conversa_id,) in db.session.query(Conversa.id)
                .filter(Conversa.cliente_id == cliente.id)
                .all()
            ]

            # A ordem evita conflitos com as chaves estrangeiras do MySQL.
            filtro_mensagens = Mensagem.usuario_id == usuario.id
            if conversa_ids:
                filtro_mensagens = or_(
                    filtro_mensagens, Mensagem.conversa_id.in_(conversa_ids)
                )
            Mensagem.query.filter(filtro_mensagens).delete(synchronize_session=False)
            Conversa.query.filter_by(cliente_id=cliente.id).delete(synchronize_session=False)
            Agendamento.query.filter_by(cliente_id=cliente.id).delete(synchronize_session=False)
            Atividade.query.filter(
                or_(Atividade.cliente_id == cliente.id, Atividade.usuario_id == usuario.id)
            ).delete(synchronize_session=False)
            Pendencia.query.filter_by(cliente_id=cliente.id).delete(synchronize_session=False)
            ServicoCliente.query.filter_by(cliente_id=cliente.id).delete(synchronize_session=False)
            SolicitacaoAtendimento.query.filter(
                func.lower(func.trim(SolicitacaoAtendimento.email)) == email_cliente
            ).delete(synchronize_session=False)

            db.session.delete(cliente)
            db.session.delete(usuario)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Falha ao remover um cliente e seus registros.")
            flash("Não foi possível remover o cliente. Nenhum dado foi apagado.", "erro")
            return redirect(url_for("admin_cliente_detalhe", id=id))

        flash(f"Cliente {nome_cliente} e todos os seus registros foram removidos.", "sucesso")
        return redirect(url_for("admin_clientes"))

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
        registrar_atividade("servico", f"Serviço {titulo} criado para {cliente.usuario.nome}.", current_user.id, cliente.id)
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
        registrar_atividade("pendencia", f"Pendência {titulo} criada para {cliente.usuario.nome}.", current_user.id, cliente.id)
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

        status_anterior = servico.status
        servico.status = status
        if status != status_anterior:
            registrar_atividade("servico", f"Serviço {servico.titulo} atualizado para {status}.", current_user.id, servico.cliente_id)
        db.session.commit()
        flash("Status do serviço atualizado.", "sucesso")
        if request.form.get("origem") == "admin_servicos":
            return redirect(url_for("admin_servicos"))
        return redirect(url_for("admin_cliente_detalhe", id=servico.cliente_id))

    @app.post("/admin/pendencias/<int:id>/status")
    @admin_required
    def admin_pendencia_status(id):
        pendencia = Pendencia.query.get_or_404(id)
        status = (request.form.get("status") or "").strip()

        if status not in STATUS_PENDENCIA:
            flash("Status de pendência inválido.", "erro")
            return redirect(url_for("admin_cliente_detalhe", id=pendencia.cliente_id))

        status_anterior = pendencia.status
        pendencia.status = status
        if status != status_anterior:
            registrar_atividade("pendencia", f"Pendência {pendencia.titulo} {status}.", current_user.id, pendencia.cliente_id)
        db.session.commit()
        flash("Pendência atualizada.", "sucesso")
        if request.form.get("origem") == "admin_pendencias":
            return redirect(url_for("admin_pendencias"))
        return redirect(url_for("admin_cliente_detalhe", id=pendencia.cliente_id))

    @app.get("/admin/agenda")
    @admin_required
    def admin_agenda():
        status = (request.args.get("status") or "").strip()
        consulta = Agendamento.query
        if status in STATUS_AGENDAMENTO:
            consulta = consulta.filter_by(status=status)
        return render_template("admin/agenda.html", agendamentos=consulta.order_by(Agendamento.data, Agendamento.hora).all(), status_agendamento=STATUS_AGENDAMENTO, status_atual=status)

    @app.route("/admin/agenda/novo", methods=["GET", "POST"])
    @admin_required
    def admin_agenda_novo():
        if request.method == "POST":
            titulo = (request.form.get("titulo") or "").strip()
            cliente_id = request.form.get("cliente_id", type=int)
            try:
                data_agenda = datetime.strptime(request.form.get("data") or "", "%Y-%m-%d").date()
                hora_agenda = datetime.strptime(request.form.get("hora") or "", "%H:%M").time()
            except ValueError:
                flash("Informe data e hora válidas.", "erro"); return redirect(url_for("admin_agenda_novo"))
            cliente = db.session.get(Cliente, cliente_id)
            if not titulo or not cliente:
                flash("Informe título e cliente.", "erro"); return redirect(url_for("admin_agenda_novo"))
            db.session.add(Agendamento(titulo=titulo, descricao=(request.form.get("descricao") or "").strip() or None, cliente=cliente, data=data_agenda, hora=hora_agenda))
            registrar_atividade("sistema", f"Atendimento agendado para {cliente.usuario.nome}.", current_user.id, cliente.id)
            db.session.commit(); flash("Agendamento criado.", "sucesso")
            return redirect(url_for("admin_agenda"))
        return render_template("admin/agenda_novo.html", clientes=Cliente.query.join(Usuario).order_by(Usuario.nome).all())

    @app.get("/admin/mensagens")
    @admin_required
    def admin_mensagens():
        conversas = Conversa.query.order_by(Conversa.atualizado_em.desc()).all()
        nao_lidas = {
            conversa.id: Mensagem.query.filter(
                Mensagem.conversa_id == conversa.id,
                Mensagem.usuario_id != current_user.id,
                Mensagem.lida.is_(False),
            ).count()
            for conversa in conversas
        }
        return render_template("admin/mensagens.html", conversas=conversas, nao_lidas=nao_lidas)

    @app.get("/admin/mensagens/<int:conversa_id>")
    @admin_required
    def admin_conversa(conversa_id):
        conversa = Conversa.query.get_or_404(conversa_id)
        marcar_mensagens_como_lidas(conversa)
        return render_template("admin/conversa.html", conversa=conversa)

    @app.post("/admin/mensagens/<int:conversa_id>/enviar")
    @admin_required
    def admin_conversa_enviar(conversa_id):
        conversa = Conversa.query.get_or_404(conversa_id)
        if conversa.status == "fechada":
            flash("Esta conversa está fechada.", "erro")
            return redirect(url_for("admin_conversa", conversa_id=conversa.id))
        texto_mensagem, erro = validar_texto_mensagem()
        if erro:
            flash(erro, "erro")
        else:
            enviar_mensagem(conversa, texto_mensagem)
        return redirect(url_for("admin_conversa", conversa_id=conversa.id))

    @app.post("/admin/mensagens/<int:conversa_id>/fechar")
    @admin_required
    def admin_conversa_fechar(conversa_id):
        conversa = Conversa.query.get_or_404(conversa_id)
        if conversa.status != "fechada":
            conversa.status = "fechada"
            conversa.atualizado_em = datetime.utcnow()
            registrar_atividade("mensagem", f"Conversa {conversa.assunto} fechada.", current_user.id, conversa.cliente_id)
            db.session.commit()
            flash("Conversa fechada.", "sucesso")
        return redirect(url_for("admin_conversa", conversa_id=conversa.id))

    @app.route("/admin/clientes/<int:cliente_id>/conversas/nova", methods=["GET", "POST"])
    @admin_required
    def admin_conversa_nova(cliente_id):
        cliente = Cliente.query.get_or_404(cliente_id)
        if request.method == "POST":
            assunto = (request.form.get("assunto") or "").strip()
            servico_id = request.form.get("servico_id", type=int)
            servico = db.session.get(ServicoCliente, servico_id) if servico_id else None
            if not assunto or len(assunto) > 150:
                flash("Informe um assunto com até 150 caracteres.", "erro")
            elif servico_id and (not servico or servico.cliente_id != cliente.id):
                flash("Serviço inválido para este cliente.", "erro")
            else:
                conversa = Conversa(cliente=cliente, servico=servico, assunto=assunto)
                db.session.add(conversa)
                db.session.flush()
                registrar_atividade("mensagem", f"Conversa {assunto} criada.", current_user.id, cliente.id)
                db.session.commit()
                flash("Conversa criada.", "sucesso")
                return redirect(url_for("admin_conversa", conversa_id=conversa.id))
        return render_template("admin/conversa_nova.html", cliente=cliente)

    @app.get("/admin/configuracoes")
    @admin_required
    def admin_configuracoes(): return render_template("admin/configuracoes.html")

    @app.get("/admin/relatorios")
    @admin_required
    def admin_relatorios():
        metricas = {"clientes": Cliente.query.count(), "solicitacoes": SolicitacaoAtendimento.query.count(), "aprovadas": SolicitacaoAtendimento.query.filter(SolicitacaoAtendimento.status.in_(["aprovada", "convertida_cliente"])).count(), "rejeitadas": SolicitacaoAtendimento.query.filter_by(status="rejeitada").count(), "finalizados": ServicoCliente.query.filter_by(status="finalizado").count(), "andamento": ServicoCliente.query.filter(ServicoCliente.status.in_(STATUS_SERVICO_ATIVO)).count(), "pendentes": Pendencia.query.filter_by(status="pendente").count(), "resolvidas": Pendencia.query.filter_by(status="resolvida").count()}
        def contagens(modelo, campo, valores): return [modelo.query.filter(campo == valor).count() for valor in valores]
        graficos = {"tipos": list(TIPOS_CLIENTE), "clientes_tipo": contagens(Cliente, Cliente.tipo_cliente, TIPOS_CLIENTE), "status_servico": list(STATUS_SERVICO), "servicos_status": contagens(ServicoCliente, ServicoCliente.status, STATUS_SERVICO), "status_solicitacao": list(STATUS_SOLICITACAO), "solicitacoes_status": contagens(SolicitacaoAtendimento, SolicitacaoAtendimento.status, STATUS_SOLICITACAO)}
        return render_template("admin/relatorios.html", metricas=metricas, graficos=graficos)

    @app.get("/admin/busca")
    @admin_required
    def admin_busca():
        q = (request.args.get("q") or "").strip(); termo = f"%{q}%"
        clientes = solicitacoes = servicos = []
        if q:
            clientes = Cliente.query.join(Usuario).filter(or_(Usuario.nome.ilike(termo), Usuario.email.ilike(termo), Cliente.telefone.ilike(termo))).limit(20).all()
            solicitacoes = SolicitacaoAtendimento.query.filter(or_(SolicitacaoAtendimento.nome.ilike(termo), SolicitacaoAtendimento.email.ilike(termo), SolicitacaoAtendimento.servico_desejado.ilike(termo))).limit(20).all()
            servicos = ServicoCliente.query.join(Cliente).join(Usuario).filter(or_(ServicoCliente.titulo.ilike(termo), Usuario.nome.ilike(termo))).limit(20).all()
        return render_template("admin/busca.html", q=q, clientes=clientes, solicitacoes=solicitacoes, servicos=servicos)

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
            "mensagens": contar_mensagens_nao_lidas(cliente.id),
        }
        return render_template("cliente/dashboard.html", cliente=cliente, resumo=resumo, ultimos_servicos=ServicoCliente.query.filter_by(cliente_id=cliente.id).order_by(ServicoCliente.atualizado_em.desc()).limit(4).all(), agendamentos=Agendamento.query.filter(Agendamento.cliente_id == cliente.id, Agendamento.data >= date.today(), Agendamento.status == "agendado").order_by(Agendamento.data, Agendamento.hora).limit(4).all())

    @app.get("/cliente/mensagens")
    @cliente_required
    def cliente_mensagens():
        cliente = get_cliente_atual()
        conversas = Conversa.query.filter_by(cliente_id=cliente.id).order_by(Conversa.atualizado_em.desc()).all()
        nao_lidas = {
            conversa.id: Mensagem.query.filter(
                Mensagem.conversa_id == conversa.id,
                Mensagem.usuario_id != current_user.id,
                Mensagem.lida.is_(False),
            ).count()
            for conversa in conversas
        }
        return render_template("cliente/mensagens.html", cliente=cliente, conversas=conversas, nao_lidas=nao_lidas)

    @app.get("/cliente/mensagens/<int:conversa_id>")
    @cliente_required
    def cliente_conversa(conversa_id):
        cliente = get_cliente_atual()
        conversa = Conversa.query.filter_by(id=conversa_id, cliente_id=cliente.id).first_or_404()
        marcar_mensagens_como_lidas(conversa)
        return render_template("cliente/conversa.html", cliente=cliente, conversa=conversa)

    @app.post("/cliente/mensagens/<int:conversa_id>/enviar")
    @cliente_required
    def cliente_conversa_enviar(conversa_id):
        cliente = get_cliente_atual()
        conversa = Conversa.query.filter_by(id=conversa_id, cliente_id=cliente.id).first_or_404()
        if conversa.status == "fechada":
            flash("Esta conversa está fechada.", "erro")
            return redirect(url_for("cliente_conversa", conversa_id=conversa.id))
        texto_mensagem, erro = validar_texto_mensagem()
        if erro:
            flash(erro, "erro")
        else:
            enviar_mensagem(conversa, texto_mensagem)
        return redirect(url_for("cliente_conversa", conversa_id=conversa.id))

    @app.route("/cliente/mensagens/nova", methods=["GET", "POST"])
    @cliente_required
    def cliente_conversa_nova():
        cliente = get_cliente_atual()
        if request.method == "POST":
            assunto = (request.form.get("assunto") or "").strip()
            servico_id = request.form.get("servico_id", type=int)
            servico = db.session.get(ServicoCliente, servico_id) if servico_id else None
            if not assunto or len(assunto) > 150:
                flash("Informe um assunto com até 150 caracteres.", "erro")
            elif servico_id and (not servico or servico.cliente_id != cliente.id):
                flash("Serviço inválido.", "erro")
            else:
                conversa = Conversa(cliente=cliente, servico=servico, assunto=assunto)
                db.session.add(conversa)
                db.session.flush()
                registrar_atividade("mensagem", f"Conversa {assunto} criada pelo cliente.", current_user.id, cliente.id)
                db.session.commit()
                flash("Conversa iniciada.", "sucesso")
                return redirect(url_for("cliente_conversa", conversa_id=conversa.id))
        return render_template("cliente/conversa_nova.html", cliente=cliente)

    @app.get("/cliente/servicos")
    @cliente_required
    def cliente_servicos():
        cliente = get_cliente_atual()
        status = (request.args.get("status") or "").strip()
        consulta = ServicoCliente.query.filter_by(cliente_id=cliente.id)
        if status:
            if status not in STATUS_SERVICO:
                flash("Status de serviço inválido.", "erro")
                return redirect(url_for("cliente_servicos"))
            consulta = consulta.filter_by(status=status)
        servicos = consulta.order_by(ServicoCliente.criado_em.desc())
        return render_template(
            "cliente/servicos.html",
            cliente=cliente,
            servicos=servicos,
            status_atual=status,
        )

    @app.get("/cliente/pendencias")
    @cliente_required
    def cliente_pendencias():
        cliente = get_cliente_atual()
        status = (request.args.get("status") or "").strip()
        consulta = Pendencia.query.filter_by(cliente_id=cliente.id)
        if status:
            if status not in STATUS_PENDENCIA:
                flash("Status de pendência inválido.", "erro")
                return redirect(url_for("cliente_pendencias"))
            consulta = consulta.filter_by(status=status)
        pendencias = consulta.order_by(Pendencia.criado_em.desc())
        return render_template(
            "cliente/pendencias.html",
            cliente=cliente,
            pendencias=pendencias,
            status_atual=status,
        )

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
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
    )
