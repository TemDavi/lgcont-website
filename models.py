from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()

TIPOS_USUARIO = ("admin", "cliente")
TIPOS_CLIENTE = ("Pessoa Física", "MEI", "Empresa", "Autônomo")
SERVICOS_ATENDIMENTO = (
    "Declaração de IRPF",
    "Abertura de empresa",
    "Regularização de MEI",
    "Simples Nacional",
    "Perícia contábil",
    "DECORE",
    "Certificado digital",
    "Assessoria contábil",
    "Assessoria trabalhista",
    "Outro",
)
STATUS_SOLICITACAO = (
    "pendente",
    "em_contato",
    "aprovada",
    "rejeitada",
    "convertida_cliente",
)
STATUS_SERVICO = (
    "solicitado",
    "em análise",
    "aguardando documentos",
    "finalizado",
    "cancelado",
)
STATUS_PENDENCIA = ("pendente", "resolvida")
STATUS_AGENDAMENTO = ("agendado", "realizado", "cancelado")
TIPOS_ATIVIDADE = ("solicitacao", "cliente", "servico", "pendencia", "mensagem", "sistema")
STATUS_CONVERSA = ("aberta", "fechada")
PRIORIDADES_ATENDIMENTO = ("baixa", "normal", "alta", "urgente")
STATUS_BACKUP = ("pendente", "concluido", "falhou")
STATUS_PRIVACIDADE = ("aberta", "em_analise", "negada", "concluida")


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    telefone = db.Column(db.String(30), nullable=True)
    cargo = db.Column(db.String(80), nullable=True)
    ultimo_acesso = db.Column(db.DateTime, nullable=True)
    tema_preferido = db.Column(db.String(20), nullable=False, default="claro")
    precisa_definir_senha = db.Column(db.Boolean, nullable=False, default=False)
    senha_temporaria = db.Column(db.String(255), nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    cliente = db.relationship("Cliente", back_populates="usuario", uselist=False)
    mensagens = db.relationship("Mensagem", back_populates="usuario")


class SolicitacaoAtendimento(db.Model):
    __tablename__ = "solicitacoes_atendimento"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    telefone = db.Column(db.String(30), nullable=False)
    cpf_cnpj = db.Column(db.String(30), nullable=False)
    tipo_cliente = db.Column(db.String(30), nullable=False)
    servico_desejado = db.Column(db.String(120), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="pendente", index=True)
    observacao_admin = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, unique=True)
    telefone = db.Column(db.String(30), nullable=True)
    whatsapp = db.Column(db.String(30), nullable=True)
    cpf_cnpj = db.Column(db.String(30), nullable=True)
    data_nascimento = db.Column(db.Date, nullable=True)
    razao_social = db.Column(db.String(160), nullable=True)
    nome_fantasia = db.Column(db.String(160), nullable=True)
    inscricao_estadual = db.Column(db.String(50), nullable=True)
    responsavel = db.Column(db.String(120), nullable=True)
    email_comercial = db.Column(db.String(120), nullable=True)
    cep = db.Column(db.String(12), nullable=True)
    cidade = db.Column(db.String(80), nullable=True)
    estado = db.Column(db.String(2), nullable=True)
    regime_tributario = db.Column(db.String(80), nullable=True)
    endereco = db.Column(db.String(255), nullable=True)
    tipo_cliente = db.Column(db.String(30), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    usuario = db.relationship("Usuario", back_populates="cliente")
    servicos = db.relationship(
        "ServicoCliente",
        back_populates="cliente",
        cascade="all, delete-orphan",
        order_by="ServicoCliente.criado_em.desc()",
    )
    pendencias = db.relationship(
        "Pendencia",
        back_populates="cliente",
        cascade="all, delete-orphan",
        order_by="Pendencia.criado_em.desc()",
    )
    conversas = db.relationship(
        "Conversa", back_populates="cliente", cascade="all, delete-orphan"
    )
    preferencias_notificacao = db.relationship(
        "PreferenciaNotificacao",
        back_populates="cliente",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ServicoCliente(db.Model):
    __tablename__ = "servicos_cliente"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True)
    titulo = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(40), nullable=False, default="solicitado")
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    cliente = db.relationship("Cliente", back_populates="servicos")
    conversas = db.relationship("Conversa", back_populates="servico")


class Conversa(db.Model):
    __tablename__ = "conversas"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True)
    servico_id = db.Column(db.Integer, db.ForeignKey("servicos_cliente.id"), nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="aberta", index=True)
    assunto = db.Column(db.String(150), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    cliente = db.relationship("Cliente", back_populates="conversas")
    servico = db.relationship("ServicoCliente", back_populates="conversas")
    mensagens = db.relationship(
        "Mensagem",
        back_populates="conversa",
        cascade="all, delete-orphan",
        order_by="Mensagem.criado_em.asc()",
    )

    @property
    def ultima_mensagem(self):
        mensagens_visiveis = [mensagem for mensagem in self.mensagens if not mensagem.excluida_em]
        return mensagens_visiveis[-1] if mensagens_visiveis else None


class Mensagem(db.Model):
    __tablename__ = "mensagens"

    id = db.Column(db.Integer, primary_key=True)
    conversa_id = db.Column(db.Integer, db.ForeignKey("conversas.id"), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    texto = db.Column(db.Text, nullable=False)
    lida = db.Column(db.Boolean, nullable=False, default=False, index=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    editada_em = db.Column(db.DateTime, nullable=True)
    excluida_em = db.Column(db.DateTime, nullable=True, index=True)

    conversa = db.relationship("Conversa", back_populates="mensagens")
    usuario = db.relationship("Usuario", back_populates="mensagens")


class Pendencia(db.Model):
    __tablename__ = "pendencias"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True)
    titulo = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="pendente")
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    cliente = db.relationship("Cliente", back_populates="pendencias")


class Atividade(db.Model):
    __tablename__ = "atividades"
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(30), nullable=False, index=True)
    descricao = db.Column(db.String(255), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True, index=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True, index=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    usuario = db.relationship("Usuario")
    cliente = db.relationship("Cliente")


class Agendamento(db.Model):
    __tablename__ = "agendamentos"
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True)
    data = db.Column(db.Date, nullable=False, index=True)
    hora = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="agendado", index=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    cliente = db.relationship("Cliente")


class ConfiguracaoEmpresa(db.Model):
    __tablename__ = "configuracoes_empresa"

    id = db.Column(db.Integer, primary_key=True)
    nome_empresa = db.Column(db.String(160), nullable=False, default="LG Contabilidade")
    razao_social = db.Column(db.String(160), nullable=True)
    nome_fantasia = db.Column(db.String(160), nullable=True)
    cnpj = db.Column(db.String(18), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    whatsapp = db.Column(db.String(30), nullable=True)
    email_comercial = db.Column(db.String(120), nullable=True)
    endereco = db.Column(db.String(180), nullable=True)
    numero = db.Column(db.String(20), nullable=True)
    complemento = db.Column(db.String(80), nullable=True)
    bairro = db.Column(db.String(80), nullable=True)
    cidade = db.Column(db.String(80), nullable=True)
    estado = db.Column(db.String(2), nullable=True)
    cep = db.Column(db.String(12), nullable=True)
    horario_atendimento = db.Column(db.String(120), nullable=True)
    site = db.Column(db.String(180), nullable=True)
    instagram = db.Column(db.String(120), nullable=True)
    logo_path = db.Column(db.String(180), nullable=True)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConfiguracaoSistema(db.Model):
    __tablename__ = "configuracoes_sistema"

    id = db.Column(db.Integer, primary_key=True)
    nome_sistema = db.Column(db.String(120), nullable=False, default="LG Contabilidade CRM")
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConfiguracaoPaginaInicial(db.Model):
    __tablename__ = "configuracoes_pagina_inicial"

    id = db.Column(db.Integer, primary_key=True)
    hero_eyebrow = db.Column(db.String(160), nullable=False)
    hero_titulo = db.Column(db.String(220), nullable=False)
    hero_texto = db.Column(db.Text, nullable=False)
    hero_card_rotulo = db.Column(db.String(80), nullable=True)
    hero_card_valor = db.Column(db.String(80), nullable=True)
    servicos_eyebrow = db.Column(db.String(80), nullable=False, default="Serviços")
    servicos_titulo = db.Column(db.String(180), nullable=False)
    servicos_texto = db.Column(db.Text, nullable=True)
    sobre_eyebrow = db.Column(db.String(80), nullable=False, default="Sobre")
    sobre_titulo = db.Column(db.String(180), nullable=False)
    sobre_texto_1 = db.Column(db.Text, nullable=True)
    sobre_texto_2 = db.Column(db.Text, nullable=True)
    diferenciais_eyebrow = db.Column(db.String(80), nullable=False, default="Diferenciais")
    diferenciais_titulo = db.Column(db.String(180), nullable=False)
    faq_eyebrow = db.Column(db.String(80), nullable=False, default="Perguntas Frequentes")
    faq_titulo = db.Column(db.String(180), nullable=False)
    faq_texto = db.Column(db.Text, nullable=True)
    footer_titulo = db.Column(db.String(160), nullable=True)
    footer_texto = db.Column(db.Text, nullable=True)
    footer_servicos_titulo = db.Column(db.String(120), nullable=True)
    footer_servicos_texto = db.Column(db.Text, nullable=True)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ItemPaginaInicial(db.Model):
    __tablename__ = "itens_pagina_inicial"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(30), nullable=False, index=True)
    titulo = db.Column(db.String(180), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    marcador = db.Column(db.String(20), nullable=True)
    ordem = db.Column(db.Integer, nullable=False, default=0, index=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)


class ConfiguracaoAtendimento(db.Model):
    __tablename__ = "configuracoes_atendimento"

    id = db.Column(db.Integer, primary_key=True)
    prioridade_padrao = db.Column(db.String(20), nullable=False, default="normal")
    prazo_resposta_horas = db.Column(db.Integer, nullable=False, default=24)
    mensagem_abertura = db.Column(db.Text, nullable=True)
    mensagem_conclusao = db.Column(db.Text, nullable=True)
    permitir_anexos = db.Column(db.Boolean, nullable=False, default=False)
    tamanho_maximo_anexo_mb = db.Column(db.Integer, nullable=False, default=10)
    formatos_permitidos = db.Column(db.String(160), nullable=True)
    whatsapp_redirecionamento = db.Column(db.String(80), nullable=True)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CategoriaAtendimento(db.Model):
    __tablename__ = "categorias_atendimento"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False, unique=True, index=True)
    ativa = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class PreferenciaNotificacao(db.Model):
    __tablename__ = "preferencias_notificacao"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False, unique=True)
    avisos_email = db.Column(db.Boolean, nullable=False, default=True)
    atualizacoes_solicitacoes = db.Column(db.Boolean, nullable=False, default=True)
    novas_mensagens = db.Column(db.Boolean, nullable=False, default=True)
    lembretes_documentos = db.Column(db.Boolean, nullable=False, default=True)
    comunicados_gerais = db.Column(db.Boolean, nullable=False, default=True)
    mensagens_promocionais = db.Column(db.Boolean, nullable=False, default=False)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente = db.relationship("Cliente", back_populates="preferencias_notificacao")


class HistoricoAcesso(db.Model):
    __tablename__ = "historico_acessos"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True, index=True)
    email_informado = db.Column(db.String(120), nullable=True, index=True)
    ip = db.Column(db.String(80), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    sucesso = db.Column(db.Boolean, nullable=False, default=False, index=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    usuario = db.relationship("Usuario")


class LogAuditoria(db.Model):
    __tablename__ = "logs_auditoria"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True, index=True)
    acao = db.Column(db.String(80), nullable=False, index=True)
    entidade = db.Column(db.String(80), nullable=True)
    entidade_id = db.Column(db.Integer, nullable=True)
    descricao = db.Column(db.String(255), nullable=False)
    ip = db.Column(db.String(80), nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    usuario = db.relationship("Usuario")


class BackupRegistro(db.Model):
    __tablename__ = "backups_registro"

    id = db.Column(db.Integer, primary_key=True)
    nome_arquivo = db.Column(db.String(180), nullable=False, unique=True)
    caminho = db.Column(db.String(255), nullable=False)
    tamanho_bytes = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="pendente")
    criado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    criado_por = db.relationship("Usuario")


class SolicitacaoPrivacidade(db.Model):
    __tablename__ = "solicitacoes_privacidade"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True)
    tipo = db.Column(db.String(40), nullable=False)
    mensagem = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="aberta", index=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente = db.relationship("Cliente")
