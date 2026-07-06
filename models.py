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


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    precisa_definir_senha = db.Column(db.Boolean, nullable=False, default=False)
    senha_temporaria = db.Column(db.String(80), nullable=True)
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
    cpf_cnpj = db.Column(db.String(30), nullable=True)
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
        return self.mensagens[-1] if self.mensagens else None


class Mensagem(db.Model):
    __tablename__ = "mensagens"

    id = db.Column(db.Integer, primary_key=True)
    conversa_id = db.Column(db.Integer, db.ForeignKey("conversas.id"), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    texto = db.Column(db.Text, nullable=False)
    lida = db.Column(db.Boolean, nullable=False, default=False, index=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

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
