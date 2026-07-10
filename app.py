from functools import wraps
from getpass import getpass
import json
import secrets
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

import os

import click
from flask import Flask, Response, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, inspect, or_, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import Config
from email_service import EmailDeliveryError, enviar_email_ativacao, enviar_email_reset_senha
from models import (
    STATUS_PENDENCIA,
    STATUS_SERVICO,
    STATUS_SOLICITACAO,
    SERVICOS_ATENDIMENTO,
    TIPOS_CLIENTE,
    PRIORIDADES_ATENDIMENTO,
    STATUS_AGENDAMENTO,
    Agendamento,
    Atividade,
    BackupRegistro,
    CategoriaAtendimento,
    Cliente,
    ConfiguracaoAtendimento,
    ConfiguracaoEmpresa,
    ConfiguracaoPaginaInicial,
    ConfiguracaoSistema,
    Conversa,
    HistoricoAcesso,
    ItemPaginaInicial,
    LogAuditoria,
    Mensagem,
    Pendencia,
    PreferenciaNotificacao,
    ServicoCliente,
    SolicitacaoAtendimento,
    SolicitacaoPrivacidade,
    Usuario,
    db,
)

STATUS_SERVICO_ATIVO = ("solicitado", "em análise", "aguardando documentos")
ADMIN_CONFIG_SECOES = ("conta", "empresa", "atendimento", "personalizacao", "seguranca", "backup")
CLIENTE_CONFIG_SECOES = ("conta", "dados", "notificacoes", "seguranca", "privacidade")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CEP_RE = re.compile(r"^\d{5}-?\d{3}$")
DOCUMENTO_RE = re.compile(r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$|^\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}$")
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "ico", "svg"}
DEFAULT_CATEGORIAS_ATENDIMENTO = (
    "Impostos",
    "Folha de pagamento",
    "Documentos",
    "Abertura de empresa",
    "Alteração cadastral",
    "Dúvidas gerais",
)
HOME_DEFAULT = {
    "hero_eyebrow": "Contabilidade, perícias e assessoria empresarial",
    "hero_titulo": "Soluções contábeis para empresas, MEIs e profissionais autônomos",
    "hero_texto": "Atuação com contabilidade, perícias, assessoria fiscal, trabalhista e empresarial, sempre com organização, segurança e atendimento próximo.",
    "hero_card_rotulo": "Atendimento direto",
    "hero_card_valor": "(92) 99199-2520",
    "servicos_eyebrow": "Serviços",
    "servicos_titulo": "Suporte contábil completo para cada fase do seu negócio",
    "servicos_texto": "Da abertura ao acompanhamento fiscal, trabalhista e documental, com processos claros e orientação técnica.",
    "sobre_eyebrow": "Sobre",
    "sobre_titulo": "Contabilidade com confiança, proximidade e responsabilidade técnica",
    "sobre_texto_1": "A Luciano Garcês Contabilidade e Perícias oferece atendimento profissional para quem precisa manter sua empresa regular, tomar decisões com mais segurança e resolver demandas contábeis com clareza.",
    "sobre_texto_2": "O trabalho é conduzido com atenção aos detalhes, organização documental e compromisso com prazos, buscando entregar um suporte prático para empresas, MEIs e profissionais autônomos.",
    "diferenciais_eyebrow": "Diferenciais",
    "diferenciais_titulo": "Uma assessoria feita para trazer tranquilidade",
    "faq_eyebrow": "Perguntas Frequentes",
    "faq_titulo": "Respostas rápidas para as dúvidas mais comuns",
    "faq_texto": "Abra uma pergunta para ver a resposta. Se ainda precisar de orientação, solicite um atendimento personalizado.",
    "footer_titulo": "Luciano Garcês Contabilidade e Perícias",
    "footer_texto": "Contabilidade, perícias, assessoria fiscal, trabalhista e empresarial.",
    "footer_servicos_titulo": "Serviços principais",
    "footer_servicos_texto": "Abertura de empresa, Simples Nacional, MEI, IRPF, DECORE e perícia contábil.",
}
HOME_DEFAULT_ITEMS = {
    "hero_stat": [
        ("12+", "serviços contábeis"),
        ("MEI", "empresas e autônomos"),
        ("IRPF", "declarações e suporte"),
    ],
    "servico": [
        ("Abertura, legalização e baixa de empresa", "Formalização, regularização e encerramento com acompanhamento documental."),
        ("Gestão tributária", "Organização de obrigações fiscais e orientação para melhor enquadramento."),
        ("Assessoria trabalhista", "Rotinas de folha, admissões, rescisões e suporte nas relações trabalhistas."),
        ("Assessoria contábil", "Escrituração, demonstrações e acompanhamento da saúde contábil da empresa."),
        ("Perícia contábil", "Análises técnicas, cálculos e relatórios para demandas judiciais e extrajudiciais."),
        ("Certificado digital", "Apoio na emissão e uso de certificado digital para empresas e profissionais."),
        ("Serviços para MEI", "Regularização, declaração anual, orientação e acompanhamento para microempreendedores."),
        ("Simples Nacional", "Apuração, obrigações e orientação para empresas optantes pelo regime simplificado."),
        ("Licenciamentos", "Suporte para licenças e exigências necessárias ao funcionamento do negócio."),
        ("Contratos", "Organização e apoio documental para relações comerciais e empresariais."),
        ("Declaração de IRPF", "Preenchimento e conferência da declaração de imposto de renda pessoa física."),
        ("DECORE", "Emissão de declaração comprobatória de rendimentos para profissionais autônomos."),
    ],
    "sobre_pilar": [
        ("01", "Atendimento personalizado e orientação objetiva."),
        ("02", "Rotinas organizadas para reduzir riscos e atrasos."),
        ("03", "Suporte técnico para decisões fiscais e empresariais."),
    ],
    "diferencial": [
        ("Atendimento personalizado", "Contato próximo para entender a realidade de cada cliente."),
        ("Segurança nas informações", "Cuidado com documentos, dados fiscais e informações estratégicas."),
        ("Agilidade nos processos", "Fluxos organizados para acompanhar prazos e demandas importantes."),
        ("Experiência técnica", "Conhecimento contábil aplicado a rotinas, perícias e obrigações legais."),
        ("Suporte para empresas e autônomos", "Serviços adaptados a diferentes portes, regimes e necessidades."),
    ],
    "faq": [
        ("Quanto custa abrir uma empresa?", "O valor depende do tipo de empresa, da atividade e das taxas dos órgãos responsáveis. Solicite um atendimento para receber uma análise e um orçamento adequado ao seu caso."),
        ("Preciso trocar de contador?", "Não necessariamente. Primeiro avaliamos sua situação e orientamos sobre a melhor solução. Se a troca for indicada, acompanhamos todo o processo de transição."),
        ("Quanto tempo demora?", "O prazo varia conforme o serviço e a análise dos órgãos envolvidos. Após receber seus dados, informamos uma estimativa e acompanhamos cada etapa."),
        ("Vocês atendem online?", "Sim. O atendimento e o envio de documentos podem ser realizados online, com segurança e acompanhamento durante todo o processo."),
        ("Quais documentos preciso?", "Os documentos variam de acordo com o serviço solicitado. Durante o primeiro atendimento, enviamos uma lista personalizada para evitar documentos desnecessários."),
    ],
}
SITEMAP_BASE_URL = "https://lucianogarcescontabilidade.com.br"
ROBOTS_TXT = """User-agent: *
Allow: /

Sitemap: https://lucianogarcescontabilidade.com.br/sitemap.xml
"""


def registrar_atividade(tipo, descricao, usuario_id=None, cliente_id=None):
    db.session.add(Atividade(tipo=tipo, descricao=descricao, usuario_id=usuario_id, cliente_id=cliente_id))


def registrar_auditoria(acao, descricao, usuario_id=None, entidade=None, entidade_id=None):
    usuario_logado = usuario_id
    if usuario_logado is None and current_user.is_authenticated:
        usuario_logado = current_user.id
    db.session.add(
        LogAuditoria(
            usuario_id=usuario_logado,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            descricao=descricao[:255],
            ip=request.remote_addr if request else None,
        )
    )


def registrar_historico_acesso(usuario, email_informado, sucesso):
    db.session.add(
        HistoricoAcesso(
            usuario_id=usuario.id if usuario else None,
            email_informado=(email_informado or "").strip().lower()[:120] or None,
            ip=request.remote_addr,
            user_agent=(request.headers.get("User-Agent") or "")[:255] or None,
            sucesso=sucesso,
        )
    )


def validar_email(valor):
    email = (valor or "").strip().lower()
    return email if EMAIL_RE.match(email) else None


def validar_documento(valor, obrigatorio=False):
    documento = (valor or "").strip()
    if not documento:
        return None if not obrigatorio else False
    return documento if DOCUMENTO_RE.match(documento) else False


def validar_cep(valor):
    cep = (valor or "").strip()
    if not cep:
        return None
    return cep if CEP_RE.match(cep) else False


def validar_estado(valor):
    estado = (valor or "").strip().upper()
    if not estado:
        return None
    return estado if len(estado) == 2 and estado.isalpha() else False


def obter_registro_unico(modelo):
    registro = modelo.query.order_by(modelo.id.asc()).first()
    if not registro:
        registro = modelo()
        db.session.add(registro)
        db.session.flush()
    return registro


def obter_preferencias_notificacao(cliente):
    if cliente.preferencias_notificacao:
        return cliente.preferencias_notificacao
    preferencias = PreferenciaNotificacao(cliente=cliente)
    db.session.add(preferencias)
    db.session.flush()
    return preferencias


def restaurar_atendimento_padrao(atendimento):
    atendimento.prioridade_padrao = "normal"
    atendimento.prazo_resposta_horas = 24
    atendimento.mensagem_abertura = None
    atendimento.mensagem_conclusao = None
    atendimento.permitir_anexos = False
    atendimento.tamanho_maximo_anexo_mb = 10
    atendimento.formatos_permitidos = None
    atendimento.whatsapp_redirecionamento = None
    for nome in DEFAULT_CATEGORIAS_ATENDIMENTO:
        categoria = CategoriaAtendimento.query.filter(func.lower(CategoriaAtendimento.nome) == nome.lower()).first()
        if categoria:
            categoria.ativa = True
        else:
            db.session.add(CategoriaAtendimento(nome=nome))


def restaurar_personalizacao_padrao(sistema):
    sistema.nome_sistema = "LG Contabilidade CRM"


def obter_config_home():
    home = ConfiguracaoPaginaInicial.query.order_by(ConfiguracaoPaginaInicial.id.asc()).first()
    if not home:
        home = ConfiguracaoPaginaInicial(**HOME_DEFAULT)
        db.session.add(home)
        db.session.flush()
    return home


def garantir_itens_home_padrao():
    for tipo, itens in HOME_DEFAULT_ITEMS.items():
        if ItemPaginaInicial.query.filter_by(tipo=tipo).first():
            continue
        for ordem, item in enumerate(itens, start=1):
            if tipo in {"hero_stat", "sobre_pilar"}:
                marcador, descricao = item
                titulo = marcador
            else:
                titulo, descricao = item
                marcador = f"{ordem:02d}" if tipo == "servico" else None
            db.session.add(
                ItemPaginaInicial(
                    tipo=tipo,
                    titulo=titulo,
                    descricao=descricao,
                    marcador=marcador,
                    ordem=ordem,
                )
            )


def restaurar_home_padrao(home):
    for campo, valor in HOME_DEFAULT.items():
        setattr(home, campo, valor)
    ItemPaginaInicial.query.delete(synchronize_session=False)
    for tipo, itens in HOME_DEFAULT_ITEMS.items():
        for ordem, item in enumerate(itens, start=1):
            if tipo in {"hero_stat", "sobre_pilar"}:
                marcador, descricao = item
                titulo = marcador
            else:
                titulo, descricao = item
                marcador = f"{ordem:02d}" if tipo == "servico" else None
            db.session.add(
                ItemPaginaInicial(
                    tipo=tipo,
                    titulo=titulo,
                    descricao=descricao,
                    marcador=marcador,
                    ordem=ordem,
                )
            )


def itens_home(tipo):
    return ItemPaginaInicial.query.filter_by(tipo=tipo, ativo=True).order_by(ItemPaginaInicial.ordem.asc(), ItemPaginaInicial.id.asc()).all()


def itens_para_textarea(tipo):
    linhas = []
    for item in itens_home(tipo):
        if tipo in {"hero_stat", "sobre_pilar"}:
            linhas.append(f"{item.marcador or item.titulo} | {item.descricao or ''}")
        else:
            linhas.append(f"{item.titulo} | {item.descricao or ''}")
    return "\n".join(linhas)


def salvar_itens_textarea(tipo, texto):
    ItemPaginaInicial.query.filter_by(tipo=tipo).delete(synchronize_session=False)
    linhas = [linha.strip() for linha in (texto or "").splitlines() if linha.strip()]
    for ordem, linha in enumerate(linhas, start=1):
        partes = [parte.strip() for parte in linha.split("|", 1)]
        titulo = partes[0]
        descricao = partes[1] if len(partes) > 1 else ""
        marcador = f"{ordem:02d}" if tipo == "servico" else None
        if tipo in {"hero_stat", "sobre_pilar"}:
            marcador = titulo
        db.session.add(
            ItemPaginaInicial(
                tipo=tipo,
                titulo=titulo,
                descricao=descricao,
                marcador=marcador,
                ordem=ordem,
            )
        )


def caminho_upload_config():
    caminho = Path(current_app.root_path) / "static" / "uploads" / "configuracoes"
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def salvar_imagem_config(campo, prefixo):
    arquivo = request.files.get(campo)
    if not arquivo or not arquivo.filename:
        return None
    nome_seguro = secure_filename(arquivo.filename)
    extensao = nome_seguro.rsplit(".", 1)[-1].lower() if "." in nome_seguro else ""
    if extensao not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Envie uma imagem válida.")
    nome_final = f"{prefixo}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}.{extensao}"
    destino = caminho_upload_config() / nome_final
    arquivo.save(destino)
    return f"uploads/configuracoes/{nome_final}"


def caminho_backups():
    caminho = Path(current_app.instance_path) / "backups"
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def validar_senha_atual(usuario, senha_atual):
    if not check_password_hash(usuario.senha_hash, senha_atual or ""):
        flash("Senha atual incorreta.", "erro")
        return False
    return True


def atualizar_senha_usuario(usuario, senha_atual, nova_senha, confirmar_senha):
    if not validar_senha_atual(usuario, senha_atual):
        return False
    if len(nova_senha or "") < 8:
        flash("A nova senha deve ter pelo menos 8 caracteres.", "erro")
        return False
    if nova_senha != confirmar_senha:
        flash("As senhas não conferem.", "erro")
        return False
    usuario.senha_hash = generate_password_hash(nova_senha)
    registrar_auditoria("alterar_senha", "Senha alterada.", usuario.id, "Usuario", usuario.id)
    return True


def atualizar_email_unico(usuario, novo_email):
    email = validar_email(novo_email)
    if not email:
        flash("Informe um e-mail válido.", "erro")
        return False
    existente = Usuario.query.filter(Usuario.email == email, Usuario.id != usuario.id).first()
    if existente:
        flash("Já existe um usuário com este e-mail.", "erro")
        return False
    usuario.email = email
    return True


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
    colunas_cliente = {coluna["name"] for coluna in inspector.get_columns("clientes")} if "clientes" in inspector.get_table_names() else set()
    comandos = []

    for nome, definicao in {
        "telefone": "VARCHAR(30) NULL",
        "cargo": "VARCHAR(80) NULL",
        "ultimo_acesso": "DATETIME NULL",
        "tema_preferido": "VARCHAR(20) NOT NULL DEFAULT 'claro'",
    }.items():
        if nome not in colunas_usuario:
            comandos.append(f"ALTER TABLE usuarios ADD COLUMN {nome} {definicao}")
    if "precisa_definir_senha" not in colunas_usuario:
        comandos.append("ALTER TABLE usuarios ADD COLUMN precisa_definir_senha BOOLEAN NOT NULL DEFAULT 0")
    if "senha_temporaria" not in colunas_usuario:
        comandos.append("ALTER TABLE usuarios ADD COLUMN senha_temporaria VARCHAR(80) NULL")
    for nome, definicao in {
        "whatsapp": "VARCHAR(30) NULL",
        "data_nascimento": "DATE NULL",
        "razao_social": "VARCHAR(160) NULL",
        "nome_fantasia": "VARCHAR(160) NULL",
        "inscricao_estadual": "VARCHAR(50) NULL",
        "responsavel": "VARCHAR(120) NULL",
        "email_comercial": "VARCHAR(120) NULL",
        "cep": "VARCHAR(12) NULL",
        "cidade": "VARCHAR(80) NULL",
        "estado": "VARCHAR(2) NULL",
        "regime_tributario": "VARCHAR(80) NULL",
    }.items():
        if nome not in colunas_cliente:
            comandos.append(f"ALTER TABLE clientes ADD COLUMN {nome} {definicao}")

    for comando in comandos:
        db.session.execute(text(comando))
    if comandos:
        db.session.commit()


def inicializar_configuracoes_padrao():
    obter_registro_unico(ConfiguracaoEmpresa)
    obter_registro_unico(ConfiguracaoSistema)
    obter_registro_unico(ConfiguracaoAtendimento)
    obter_config_home()
    for nome in DEFAULT_CATEGORIAS_ATENDIMENTO:
        if not CategoriaAtendimento.query.filter(func.lower(CategoriaAtendimento.nome) == nome.lower()).first():
            db.session.add(CategoriaAtendimento(nome=nome))
    garantir_itens_home_padrao()
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


def serializar_tabela(modelo, campos):
    itens = []
    for registro in modelo.query.all():
        item = {}
        for campo in campos:
            valor = getattr(registro, campo)
            if isinstance(valor, (datetime, date)):
                valor = valor.isoformat()
            item[campo] = valor
        itens.append(item)
    return itens


def gerar_backup_json():
    dados = {
        "gerado_em": datetime.utcnow().isoformat(),
        "versao": "lg-crm-1",
        "usuarios": serializar_tabela(Usuario, ["id", "nome", "email", "tipo", "telefone", "cargo", "tema_preferido", "criado_em", "ultimo_acesso"]),
        "clientes": serializar_tabela(Cliente, ["id", "usuario_id", "telefone", "whatsapp", "cpf_cnpj", "endereco", "tipo_cliente", "cep", "cidade", "estado", "criado_em"]),
        "solicitacoes": serializar_tabela(SolicitacaoAtendimento, ["id", "nome", "email", "telefone", "cpf_cnpj", "tipo_cliente", "servico_desejado", "status", "criado_em"]),
        "servicos": serializar_tabela(ServicoCliente, ["id", "cliente_id", "titulo", "status", "criado_em", "atualizado_em"]),
        "pendencias": serializar_tabela(Pendencia, ["id", "cliente_id", "titulo", "status", "criado_em"]),
        "configuracao_empresa": serializar_tabela(ConfiguracaoEmpresa, ["id", "nome_empresa", "razao_social", "nome_fantasia", "cnpj", "telefone", "whatsapp", "email_comercial", "cidade", "estado", "cep", "logo_path"]),
        "configuracao_sistema": serializar_tabela(ConfiguracaoSistema, ["id", "nome_sistema"]),
        "configuracao_pagina_inicial": serializar_tabela(ConfiguracaoPaginaInicial, ["id", "hero_eyebrow", "hero_titulo", "hero_texto", "servicos_titulo", "sobre_titulo", "diferenciais_titulo", "faq_titulo"]),
        "itens_pagina_inicial": serializar_tabela(ItemPaginaInicial, ["id", "tipo", "titulo", "descricao", "marcador", "ordem", "ativo"]),
        "configuracao_atendimento": serializar_tabela(ConfiguracaoAtendimento, ["id", "prioridade_padrao", "prazo_resposta_horas", "permitir_anexos", "tamanho_maximo_anexo_mb", "formatos_permitidos"]),
        "categorias_atendimento": serializar_tabela(CategoriaAtendimento, ["id", "nome", "ativa", "criado_em"]),
    }
    nome = f"backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}.json"
    destino = caminho_backups() / nome
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return nome, destino


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        # Nesta etapa inicial, o create_all facilita criar as novas tabelas.
        db.create_all()
        atualizar_schema_simples()
        inicializar_configuracoes_padrao()

    @app.context_processor
    def disponibilizar_dados_globais():
        sistema = ConfiguracaoSistema.query.order_by(ConfiguracaoSistema.id.asc()).first()
        dados = {
            "mensagens_nao_lidas": 0,
            "config_sistema_global": sistema,
            "tema_usuario_atual": "claro",
        }
        if not current_user.is_authenticated:
            return dados
        tema_preferido = getattr(current_user, "tema_preferido", None)
        dados["tema_usuario_atual"] = tema_preferido if tema_preferido in {"claro", "escuro"} else "claro"
        if current_user.tipo == "cliente":
            cliente = Cliente.query.filter_by(usuario_id=current_user.id).first()
            total = contar_mensagens_nao_lidas(cliente.id) if cliente else 0
        else:
            total = contar_mensagens_nao_lidas()
        dados["mensagens_nao_lidas"] = total
        return dados

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
        home = obter_config_home()
        return render_template(
            "index.html",
            home=home,
            hero_stats=itens_home("hero_stat"),
            servicos_home=itens_home("servico"),
            sobre_pilares=itens_home("sobre_pilar"),
            diferenciais_home=itens_home("diferencial"),
            faq_items=itens_home("faq"),
            sistema=ConfiguracaoSistema.query.order_by(ConfiguracaoSistema.id.asc()).first(),
        )

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
                registrar_historico_acesso(usuario, email, False)
                db.session.commit()
                flash("E-mail ou senha inválidos.", "erro")
                return redirect(url_for("login"))

            registrar_historico_acesso(usuario, email, True)
            usuario.ultimo_acesso = datetime.utcnow()
            db.session.commit()
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
    def admin_configuracoes():
        return redirect(url_for("admin_configuracoes_secao", secao="conta"))

    @app.get("/admin/configuracoes/<secao>")
    @admin_required
    def admin_configuracoes_secao(secao):
        if secao not in ADMIN_CONFIG_SECOES:
            flash("Seção de configurações inválida.", "erro")
            return redirect(url_for("admin_configuracoes"))
        empresa = obter_registro_unico(ConfiguracaoEmpresa)
        sistema = obter_registro_unico(ConfiguracaoSistema)
        home = obter_config_home()
        atendimento = obter_registro_unico(ConfiguracaoAtendimento)
        categorias = CategoriaAtendimento.query.order_by(CategoriaAtendimento.ativa.desc(), CategoriaAtendimento.nome.asc()).all()
        historico_acessos = HistoricoAcesso.query.order_by(HistoricoAcesso.criado_em.desc()).limit(20).all()
        logs_auditoria = LogAuditoria.query.order_by(LogAuditoria.criado_em.desc()).limit(20).all()
        backups = BackupRegistro.query.order_by(BackupRegistro.criado_em.desc()).limit(20).all()
        solicitacoes_privacidade = SolicitacaoPrivacidade.query.order_by(SolicitacaoPrivacidade.criado_em.desc()).limit(20).all()
        ultimo_backup = backups[0] if backups else None
        return render_template(
            "admin/configuracoes.html",
            secao=secao,
            secoes=ADMIN_CONFIG_SECOES,
            empresa=empresa,
            sistema=sistema,
            home=home,
            home_textareas={
                "hero_stats": itens_para_textarea("hero_stat"),
                "servicos": itens_para_textarea("servico"),
                "sobre_pilares": itens_para_textarea("sobre_pilar"),
                "diferenciais": itens_para_textarea("diferencial"),
                "faq": itens_para_textarea("faq"),
            },
            atendimento=atendimento,
            categorias=categorias,
            prioridades=PRIORIDADES_ATENDIMENTO,
            status_solicitacao=STATUS_SOLICITACAO,
            historico_acessos=historico_acessos,
            logs_auditoria=logs_auditoria,
            backups=backups,
            ultimo_backup=ultimo_backup,
            solicitacoes_privacidade=solicitacoes_privacidade,
        )

    @app.post("/admin/configuracoes/conta")
    @admin_required
    def admin_configuracoes_conta_salvar():
        acao = request.form.get("acao")
        if acao == "perfil":
            nome = (request.form.get("nome") or "").strip()
            telefone = (request.form.get("telefone") or "").strip()
            cargo = (request.form.get("cargo") or "").strip()
            if not nome:
                flash("Informe o nome de exibição.", "erro")
                return redirect(url_for("admin_configuracoes_secao", secao="conta"))
            if not atualizar_email_unico(current_user, request.form.get("email")):
                return redirect(url_for("admin_configuracoes_secao", secao="conta"))
            current_user.nome = nome
            current_user.telefone = telefone or None
            current_user.cargo = cargo or None
            registrar_auditoria("editar_perfil_admin", "Administrador atualizou o próprio perfil.", current_user.id, "Usuario", current_user.id)
            db.session.commit()
            flash("Perfil atualizado com sucesso.", "sucesso")
        elif acao == "senha":
            if atualizar_senha_usuario(
                current_user,
                request.form.get("senha_atual"),
                request.form.get("nova_senha"),
                request.form.get("confirmar_senha"),
            ):
                db.session.commit()
                flash("Senha alterada com sucesso.", "sucesso")
            else:
                db.session.rollback()
        elif acao == "tema":
            tema = (request.form.get("tema") or "").strip()
            if tema not in {"claro", "escuro"}:
                flash("Tema invalido.", "erro")
                return redirect(url_for("admin_configuracoes_secao", secao="conta"))
            current_user.tema_preferido = tema
            registrar_auditoria("alterar_tema_usuario", "Administrador alterou o tema da propria conta.", current_user.id, "Usuario", current_user.id)
            db.session.commit()
            flash("Tema da sua conta atualizado.", "sucesso")
        return redirect(url_for("admin_configuracoes_secao", secao="conta"))

    @app.post("/admin/configuracoes/empresa")
    @admin_required
    def admin_configuracoes_empresa_salvar():
        empresa = obter_registro_unico(ConfiguracaoEmpresa)
        email = validar_email(request.form.get("email_comercial")) if request.form.get("email_comercial") else None
        cnpj = validar_documento(request.form.get("cnpj"))
        cep = validar_cep(request.form.get("cep"))
        estado = validar_estado(request.form.get("estado"))
        if request.form.get("email_comercial") and not email:
            flash("Informe um e-mail comercial válido.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="empresa"))
        if cnpj is False:
            flash("Informe um CNPJ válido.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="empresa"))
        if cep is False:
            flash("Informe um CEP válido.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="empresa"))
        if estado is False:
            flash("Informe o estado com duas letras.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="empresa"))
        try:
            logo_path = salvar_imagem_config("logo", "empresa-logo")
        except ValueError as erro:
            flash(str(erro), "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="empresa"))
        for campo in ("nome_empresa", "razao_social", "nome_fantasia", "telefone", "whatsapp", "endereco", "numero", "complemento", "bairro", "cidade", "horario_atendimento", "site", "instagram"):
            setattr(empresa, campo, (request.form.get(campo) or "").strip() or None)
        empresa.nome_empresa = empresa.nome_empresa or "LG Contabilidade"
        empresa.email_comercial = email
        empresa.cnpj = cnpj or None
        empresa.cep = cep or None
        empresa.estado = estado or None
        if logo_path:
            empresa.logo_path = logo_path
        registrar_auditoria("editar_empresa", "Dados da empresa atualizados.", current_user.id, "ConfiguracaoEmpresa", empresa.id)
        db.session.commit()
        flash("Dados da empresa atualizados.", "sucesso")
        return redirect(url_for("admin_configuracoes_secao", secao="empresa"))

    @app.post("/admin/configuracoes/atendimento")
    @admin_required
    def admin_configuracoes_atendimento_salvar():
        atendimento = obter_registro_unico(ConfiguracaoAtendimento)
        prioridade = (request.form.get("prioridade_padrao") or "").strip()
        if prioridade not in PRIORIDADES_ATENDIMENTO:
            flash("Prioridade padrão inválida.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="atendimento"))
        prazo = request.form.get("prazo_resposta_horas", type=int) or 24
        tamanho = request.form.get("tamanho_maximo_anexo_mb", type=int) or 10
        if prazo < 1 or tamanho < 1:
            flash("Prazo e tamanho máximo devem ser maiores que zero.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="atendimento"))
        atendimento.prioridade_padrao = prioridade
        atendimento.prazo_resposta_horas = prazo
        atendimento.mensagem_abertura = (request.form.get("mensagem_abertura") or "").strip() or None
        atendimento.mensagem_conclusao = (request.form.get("mensagem_conclusao") or "").strip() or None
        atendimento.permitir_anexos = request.form.get("permitir_anexos") == "on"
        atendimento.tamanho_maximo_anexo_mb = tamanho
        atendimento.formatos_permitidos = (request.form.get("formatos_permitidos") or "").strip() or None
        atendimento.whatsapp_redirecionamento = (request.form.get("whatsapp_redirecionamento") or "").strip() or None
        registrar_auditoria("editar_atendimento", "Configurações de atendimento atualizadas.", current_user.id, "ConfiguracaoAtendimento", atendimento.id)
        db.session.commit()
        flash("Configurações de atendimento salvas.", "sucesso")
        return redirect(url_for("admin_configuracoes_secao", secao="atendimento"))

    @app.post("/admin/configuracoes/atendimento/padrao")
    @admin_required
    def admin_configuracoes_atendimento_padrao():
        atendimento = obter_registro_unico(ConfiguracaoAtendimento)
        restaurar_atendimento_padrao(atendimento)
        registrar_auditoria("restaurar_atendimento_padrao", "Configurações de atendimento retornaram ao padrão.", current_user.id, "ConfiguracaoAtendimento", atendimento.id)
        db.session.commit()
        flash("Configurações de atendimento restauradas para o padrão.", "sucesso")
        return redirect(url_for("admin_configuracoes_secao", secao="atendimento"))

    @app.post("/admin/configuracoes/atendimento/categorias")
    @admin_required
    def admin_categoria_atendimento_salvar():
        nome = (request.form.get("nome") or "").strip()
        if not nome:
            flash("Informe o nome da categoria.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="atendimento"))
        if CategoriaAtendimento.query.filter(func.lower(CategoriaAtendimento.nome) == nome.lower()).first():
            flash("Já existe uma categoria com este nome.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="atendimento"))
        categoria = CategoriaAtendimento(nome=nome)
        db.session.add(categoria)
        registrar_auditoria("criar_categoria", f"Categoria de atendimento {nome} criada.", current_user.id, "CategoriaAtendimento")
        db.session.commit()
        flash("Categoria criada.", "sucesso")
        return redirect(url_for("admin_configuracoes_secao", secao="atendimento"))

    @app.post("/admin/configuracoes/atendimento/categorias/<int:id>/alternar")
    @admin_required
    def admin_categoria_atendimento_alternar(id):
        categoria = CategoriaAtendimento.query.get_or_404(id)
        categoria.ativa = not categoria.ativa
        registrar_auditoria("alternar_categoria", f"Categoria {categoria.nome} {'ativada' if categoria.ativa else 'desativada'}.", current_user.id, "CategoriaAtendimento", categoria.id)
        db.session.commit()
        flash("Categoria atualizada.", "sucesso")
        return redirect(url_for("admin_configuracoes_secao", secao="atendimento"))

    @app.post("/admin/configuracoes/atendimento/categorias/<int:id>/excluir")
    @admin_required
    def admin_categoria_atendimento_excluir(id):
        categoria = CategoriaAtendimento.query.get_or_404(id)
        confirmacao = (request.form.get("confirmacao") or "").strip().lower()
        if confirmacao != "excluir":
            flash("Digite EXCLUIR para confirmar.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="atendimento"))
        em_uso = SolicitacaoAtendimento.query.filter(SolicitacaoAtendimento.servico_desejado == categoria.nome).first()
        if em_uso:
            categoria.ativa = False
            registrar_auditoria("desativar_categoria_em_uso", f"Categoria {categoria.nome} desativada por estar em uso.", current_user.id, "CategoriaAtendimento", categoria.id)
            db.session.commit()
            flash("Categoria em uso. Ela foi desativada em vez de excluída.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="atendimento"))
        nome = categoria.nome
        db.session.delete(categoria)
        registrar_auditoria("excluir_categoria", f"Categoria {nome} excluída.", current_user.id, "CategoriaAtendimento", id)
        db.session.commit()
        flash("Categoria excluída.", "sucesso")
        return redirect(url_for("admin_configuracoes_secao", secao="atendimento"))

    @app.post("/admin/configuracoes/personalizacao")
    @admin_required
    def admin_configuracoes_personalizacao_salvar():
        sistema = obter_registro_unico(ConfiguracaoSistema)
        home = obter_config_home()
        sistema.nome_sistema = (request.form.get("nome_sistema") or "").strip() or "LG Contabilidade CRM"
        campos_home = (
            "hero_eyebrow",
            "hero_titulo",
            "hero_texto",
            "hero_card_rotulo",
            "hero_card_valor",
            "servicos_eyebrow",
            "servicos_titulo",
            "servicos_texto",
            "sobre_eyebrow",
            "sobre_titulo",
            "sobre_texto_1",
            "sobre_texto_2",
            "diferenciais_eyebrow",
            "diferenciais_titulo",
            "faq_eyebrow",
            "faq_titulo",
            "faq_texto",
            "footer_titulo",
            "footer_texto",
            "footer_servicos_titulo",
            "footer_servicos_texto",
        )
        for campo in campos_home:
            valor = (request.form.get(campo) or "").strip()
            setattr(home, campo, valor or HOME_DEFAULT.get(campo, ""))
        salvar_itens_textarea("hero_stat", request.form.get("hero_stats"))
        salvar_itens_textarea("servico", request.form.get("servicos"))
        salvar_itens_textarea("sobre_pilar", request.form.get("sobre_pilares"))
        salvar_itens_textarea("diferencial", request.form.get("diferenciais"))
        salvar_itens_textarea("faq", request.form.get("faq"))
        registrar_auditoria("editar_personalizacao", "Nome e conteudo da pagina inicial atualizados.", current_user.id, "ConfiguracaoSistema", sistema.id)
        db.session.commit()
        flash("Personalização salva.", "sucesso")
        return redirect(url_for("admin_configuracoes_secao", secao="personalizacao"))

    @app.post("/admin/configuracoes/personalizacao/padrao")
    @admin_required
    def admin_configuracoes_personalizacao_padrao():
        sistema = obter_registro_unico(ConfiguracaoSistema)
        home = obter_config_home()
        restaurar_personalizacao_padrao(sistema)
        restaurar_home_padrao(home)
        registrar_auditoria("restaurar_personalizacao_padrao", "Nome e conteudo da pagina inicial retornaram ao padrao.", current_user.id, "ConfiguracaoSistema", sistema.id)
        db.session.commit()
        flash("Personalização restaurada para o padrão.", "sucesso")
        return redirect(url_for("admin_configuracoes_secao", secao="personalizacao"))

    @app.post("/admin/configuracoes/seguranca")
    @admin_required
    def admin_configuracoes_seguranca_salvar():
        if atualizar_senha_usuario(
            current_user,
            request.form.get("senha_atual"),
            request.form.get("nova_senha"),
            request.form.get("confirmar_senha"),
        ):
            db.session.commit()
            flash("Senha alterada com sucesso.", "sucesso")
        else:
            db.session.rollback()
        return redirect(url_for("admin_configuracoes_secao", secao="seguranca"))

    @app.post("/admin/configuracoes/privacidade/<int:id>/status")
    @admin_required
    def admin_privacidade_status(id):
        solicitacao = SolicitacaoPrivacidade.query.get_or_404(id)
        status = (request.form.get("status") or "").strip()
        if status not in {"aberta", "em_analise", "negada", "concluida"}:
            flash("Status de privacidade inválido.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="seguranca"))
        solicitacao.status = status
        registrar_auditoria("atualizar_privacidade", f"Solicitação de privacidade atualizada para {status}.", current_user.id, "SolicitacaoPrivacidade", solicitacao.id)
        db.session.commit()
        flash("Solicitação de privacidade atualizada.", "sucesso")
        return redirect(url_for("admin_configuracoes_secao", secao="seguranca"))

    @app.post("/admin/configuracoes/backup/gerar")
    @admin_required
    def admin_backup_gerar():
        try:
            nome, destino = gerar_backup_json()
            registro = BackupRegistro(
                nome_arquivo=nome,
                caminho=str(destino),
                tamanho_bytes=destino.stat().st_size,
                status="concluido",
                criado_por_id=current_user.id,
            )
            db.session.add(registro)
            registrar_auditoria("gerar_backup", f"Backup {nome} gerado.", current_user.id, "BackupRegistro")
            db.session.commit()
            flash("Backup gerado com sucesso.", "sucesso")
        except OSError:
            db.session.rollback()
            current_app.logger.exception("Falha ao gerar backup.")
            flash("Não foi possível gerar o backup.", "erro")
        return redirect(url_for("admin_configuracoes_secao", secao="backup"))

    @app.get("/admin/configuracoes/backup/<int:id>/baixar")
    @admin_required
    def admin_backup_baixar(id):
        backup = BackupRegistro.query.get_or_404(id)
        caminho = Path(backup.caminho).resolve()
        raiz = caminho_backups().resolve()
        if raiz not in caminho.parents or not caminho.exists():
            flash("Arquivo de backup não encontrado.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="backup"))
        registrar_auditoria("baixar_backup", f"Backup {backup.nome_arquivo} baixado.", current_user.id, "BackupRegistro", backup.id)
        db.session.commit()
        return send_file(caminho, as_attachment=True, download_name=backup.nome_arquivo)

    @app.post("/admin/configuracoes/backup/<int:id>/excluir")
    @admin_required
    def admin_backup_excluir(id):
        backup = BackupRegistro.query.get_or_404(id)
        if not validar_senha_atual(current_user, request.form.get("senha_atual")):
            return redirect(url_for("admin_configuracoes_secao", secao="backup"))
        caminho = Path(backup.caminho).resolve()
        raiz = caminho_backups().resolve()
        if raiz in caminho.parents and caminho.exists():
            caminho.unlink()
        nome = backup.nome_arquivo
        db.session.delete(backup)
        registrar_auditoria("excluir_backup", f"Backup {nome} excluído.", current_user.id, "BackupRegistro", id)
        db.session.commit()
        flash("Backup excluído.", "sucesso")
        return redirect(url_for("admin_configuracoes_secao", secao="backup"))

    @app.post("/admin/configuracoes/backup/<int:id>/restaurar")
    @admin_required
    def admin_backup_restaurar(id):
        backup = BackupRegistro.query.get_or_404(id)
        if not validar_senha_atual(current_user, request.form.get("senha_atual")):
            return redirect(url_for("admin_configuracoes_secao", secao="backup"))
        if (request.form.get("confirmacao") or "").strip().upper() != "RESTAURAR":
            flash("Digite RESTAURAR para confirmar a validação da restauração.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="backup"))
        caminho = Path(backup.caminho).resolve()
        raiz = caminho_backups().resolve()
        if raiz not in caminho.parents or not caminho.exists():
            flash("Arquivo de backup não encontrado.", "erro")
            return redirect(url_for("admin_configuracoes_secao", secao="backup"))
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            if dados.get("versao") != "lg-crm-1":
                raise ValueError
            nome_seguro, destino_seguro = gerar_backup_json()
            db.session.add(
                BackupRegistro(
                    nome_arquivo=nome_seguro,
                    caminho=str(destino_seguro),
                    tamanho_bytes=destino_seguro.stat().st_size,
                    status="concluido",
                    criado_por_id=current_user.id,
                )
            )
            registrar_auditoria("validar_restauracao_backup", f"Backup {backup.nome_arquivo} validado para restauração; backup de segurança {nome_seguro} criado.", current_user.id, "BackupRegistro", backup.id)
            db.session.commit()
            flash("Backup validado e backup de segurança criado. A aplicação automática dos dados deve ser feita em janela de manutenção.", "sucesso")
        except (OSError, ValueError, json.JSONDecodeError):
            db.session.rollback()
            flash("O arquivo de backup não possui o formato esperado.", "erro")
        return redirect(url_for("admin_configuracoes_secao", secao="backup"))

    @app.post("/admin/configuracoes/backup/limpar-temporarios")
    @admin_required
    def admin_backup_limpar_temporarios():
        if not validar_senha_atual(current_user, request.form.get("senha_atual")):
            return redirect(url_for("admin_configuracoes_secao", secao="backup"))
        tmp = Path(current_app.instance_path) / "tmp"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True, exist_ok=True)
        registrar_auditoria("limpar_temporarios", "Arquivos temporários limpos.", current_user.id)
        db.session.commit()
        flash("Arquivos temporários limpos.", "sucesso")
        return redirect(url_for("admin_configuracoes_secao", secao="backup"))

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

    @app.get("/cliente/configuracoes")
    @cliente_required
    def cliente_configuracoes():
        return redirect(url_for("cliente_configuracoes_secao", secao="conta"))

    @app.get("/cliente/configuracoes/<secao>")
    @cliente_required
    def cliente_configuracoes_secao(secao):
        if secao not in CLIENTE_CONFIG_SECOES:
            flash("Seção de configurações inválida.", "erro")
            return redirect(url_for("cliente_configuracoes"))
        cliente = get_cliente_atual()
        preferencias = obter_preferencias_notificacao(cliente)
        acessos = HistoricoAcesso.query.filter_by(usuario_id=current_user.id).order_by(HistoricoAcesso.criado_em.desc()).limit(8).all()
        privacidade = SolicitacaoPrivacidade.query.filter_by(cliente_id=cliente.id).order_by(SolicitacaoPrivacidade.criado_em.desc()).limit(8).all()
        return render_template(
            "cliente/configuracoes.html",
            secao=secao,
            secoes=CLIENTE_CONFIG_SECOES,
            cliente=cliente,
            preferencias=preferencias,
            acessos=acessos,
            privacidade=privacidade,
        )

    @app.post("/cliente/configuracoes/conta")
    @cliente_required
    def cliente_configuracoes_conta_salvar():
        cliente = get_cliente_atual()
        acao = request.form.get("acao")
        if acao == "perfil":
            nome = (request.form.get("nome") or "").strip()
            telefone = (request.form.get("telefone") or "").strip()
            if not nome:
                flash("Informe seu nome.", "erro")
                return redirect(url_for("cliente_configuracoes_secao", secao="conta"))
            if not atualizar_email_unico(current_user, request.form.get("email")):
                return redirect(url_for("cliente_configuracoes_secao", secao="conta"))
            current_user.nome = nome
            current_user.telefone = telefone or None
            cliente.telefone = telefone or None
            registrar_auditoria("editar_perfil_cliente", "Cliente atualizou a própria conta.", current_user.id, "Cliente", cliente.id)
            db.session.commit()
            flash("Conta atualizada com sucesso.", "sucesso")
        elif acao == "senha":
            if atualizar_senha_usuario(
                current_user,
                request.form.get("senha_atual"),
                request.form.get("nova_senha"),
                request.form.get("confirmar_senha"),
            ):
                db.session.commit()
                flash("Senha alterada com sucesso.", "sucesso")
            else:
                db.session.rollback()
        elif acao == "tema":
            tema = (request.form.get("tema") or "").strip()
            if tema not in {"claro", "escuro"}:
                flash("Tema invalido.", "erro")
                return redirect(url_for("cliente_configuracoes_secao", secao="conta"))
            current_user.tema_preferido = tema
            registrar_auditoria("alterar_tema_usuario", "Cliente alterou o tema da propria conta.", current_user.id, "Usuario", current_user.id)
            db.session.commit()
            flash("Tema da sua conta atualizado.", "sucesso")
        return redirect(url_for("cliente_configuracoes_secao", secao="conta"))

    @app.post("/cliente/configuracoes/dados")
    @cliente_required
    def cliente_configuracoes_dados_salvar():
        cliente = get_cliente_atual()
        cep = validar_cep(request.form.get("cep"))
        estado = validar_estado(request.form.get("estado"))
        email_comercial = validar_email(request.form.get("email_comercial")) if request.form.get("email_comercial") else None
        if cep is False:
            flash("Informe um CEP válido.", "erro")
            return redirect(url_for("cliente_configuracoes_secao", secao="dados"))
        if estado is False:
            flash("Informe o estado com duas letras.", "erro")
            return redirect(url_for("cliente_configuracoes_secao", secao="dados"))
        if request.form.get("email_comercial") and not email_comercial:
            flash("Informe um e-mail comercial válido.", "erro")
            return redirect(url_for("cliente_configuracoes_secao", secao="dados"))
        cliente.telefone = (request.form.get("telefone") or "").strip() or None
        cliente.whatsapp = (request.form.get("whatsapp") or "").strip() or None
        cliente.endereco = (request.form.get("endereco") or "").strip() or None
        cliente.cep = cep or None
        cliente.cidade = (request.form.get("cidade") or "").strip() or None
        cliente.estado = estado or None
        cliente.razao_social = (request.form.get("razao_social") or "").strip() or None
        cliente.nome_fantasia = (request.form.get("nome_fantasia") or "").strip() or None
        cliente.inscricao_estadual = (request.form.get("inscricao_estadual") or "").strip() or None
        cliente.responsavel = (request.form.get("responsavel") or "").strip() or None
        cliente.email_comercial = email_comercial
        cliente.regime_tributario = (request.form.get("regime_tributario") or "").strip() or None
        registrar_auditoria("editar_dados_cliente", "Cliente atualizou dados cadastrais próprios.", current_user.id, "Cliente", cliente.id)
        db.session.commit()
        flash("Dados atualizados com sucesso.", "sucesso")
        return redirect(url_for("cliente_configuracoes_secao", secao="dados"))

    @app.post("/cliente/configuracoes/notificacoes")
    @cliente_required
    def cliente_configuracoes_notificacoes_salvar():
        cliente = get_cliente_atual()
        preferencias = obter_preferencias_notificacao(cliente)
        preferencias.avisos_email = request.form.get("avisos_email") == "on"
        preferencias.atualizacoes_solicitacoes = request.form.get("atualizacoes_solicitacoes") == "on"
        preferencias.novas_mensagens = request.form.get("novas_mensagens") == "on"
        preferencias.lembretes_documentos = request.form.get("lembretes_documentos") == "on"
        preferencias.comunicados_gerais = request.form.get("comunicados_gerais") == "on"
        preferencias.mensagens_promocionais = request.form.get("mensagens_promocionais") == "on"
        registrar_auditoria("editar_notificacoes", "Cliente atualizou preferências de notificação.", current_user.id, "Cliente", cliente.id)
        db.session.commit()
        flash("Preferências salvas.", "sucesso")
        return redirect(url_for("cliente_configuracoes_secao", secao="notificacoes"))

    @app.post("/cliente/configuracoes/seguranca")
    @cliente_required
    def cliente_configuracoes_seguranca_salvar():
        if atualizar_senha_usuario(
            current_user,
            request.form.get("senha_atual"),
            request.form.get("nova_senha"),
            request.form.get("confirmar_senha"),
        ):
            db.session.commit()
            flash("Senha alterada com sucesso.", "sucesso")
        else:
            db.session.rollback()
        return redirect(url_for("cliente_configuracoes_secao", secao="seguranca"))

    @app.post("/cliente/configuracoes/privacidade/solicitar")
    @cliente_required
    def cliente_privacidade_solicitar():
        cliente = get_cliente_atual()
        tipo = (request.form.get("tipo") or "").strip()
        if tipo not in {"correcao", "exclusao", "anonimizacao", "copia_dados"}:
            flash("Tipo de solicitação inválido.", "erro")
            return redirect(url_for("cliente_configuracoes_secao", secao="privacidade"))
        solicitacao = SolicitacaoPrivacidade(
            cliente=cliente,
            tipo=tipo,
            mensagem=(request.form.get("mensagem") or "").strip() or None,
        )
        db.session.add(solicitacao)
        registrar_auditoria("solicitar_privacidade", f"Solicitação de privacidade criada: {tipo}.", current_user.id, "Cliente", cliente.id)
        db.session.commit()
        flash("Solicitação registrada. A equipe vai analisar o pedido.", "sucesso")
        return redirect(url_for("cliente_configuracoes_secao", secao="privacidade"))

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
