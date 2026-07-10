import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from werkzeug.security import generate_password_hash

from app import create_app
from models import (
    BackupRegistro,
    CategoriaAtendimento,
    Cliente,
    LogAuditoria,
    PreferenciaNotificacao,
    Usuario,
    db,
)


class ConfiguracoesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()

        self.admin = Usuario(
            nome="Admin",
            email="admin@example.com",
            senha_hash=generate_password_hash("admin12345"),
            tipo="admin",
        )
        self.cliente_usuario = Usuario(
            nome="Cliente",
            email="cliente@example.com",
            senha_hash=generate_password_hash("cliente12345"),
            tipo="cliente",
        )
        self.outro_usuario = Usuario(
            nome="Outro",
            email="outro@example.com",
            senha_hash=generate_password_hash("outro12345"),
            tipo="cliente",
        )
        self.cliente = Cliente(usuario=self.cliente_usuario, tipo_cliente="MEI", cpf_cnpj="12.345.678/0001-99")
        self.outro_cliente = Cliente(usuario=self.outro_usuario, tipo_cliente="Pessoa Física", cpf_cnpj="123.456.789-00")
        db.session.add_all([self.admin, self.cliente, self.outro_cliente])
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self, email, senha):
        return self.client.post("/login", data={"email": email, "senha": senha})

    def test_admin_acessa_configuracoes_e_cliente_nao(self):
        self.login("admin@example.com", "admin12345")
        self.assertEqual(self.client.get("/admin/configuracoes/conta").status_code, 200)
        self.client.get("/logout")
        self.login("cliente@example.com", "cliente12345")
        resposta = self.client.get("/admin/configuracoes/conta")
        self.assertEqual(resposta.status_code, 302)

    def test_cliente_edita_apenas_propria_conta(self):
        self.login("cliente@example.com", "cliente12345")
        resposta = self.client.post(
            "/cliente/configuracoes/conta",
            data={"acao": "perfil", "nome": "Cliente Novo", "email": "cliente@example.com", "telefone": "92999999999"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(db.session.get(Cliente, self.cliente.id).telefone, "92999999999")
        self.assertIsNone(db.session.get(Cliente, self.outro_cliente.id).telefone)

    def test_email_duplicado_e_senha_incorreta_sao_rejeitados(self):
        self.login("cliente@example.com", "cliente12345")
        self.client.post(
            "/cliente/configuracoes/conta",
            data={"acao": "perfil", "nome": "Cliente", "email": "admin@example.com"},
        )
        self.assertEqual(db.session.get(Usuario, self.cliente_usuario.id).email, "cliente@example.com")
        self.client.post(
            "/cliente/configuracoes/seguranca",
            data={"senha_atual": "errada", "nova_senha": "nova12345", "confirmar_senha": "nova12345"},
        )
        self.assertEqual(LogAuditoria.query.filter_by(acao="alterar_senha").count(), 0)

    def test_categoria_duplicada_e_rejeitada(self):
        self.login("admin@example.com", "admin12345")
        self.client.post("/admin/configuracoes/atendimento/categorias", data={"nome": "Impostos"})
        self.client.post("/admin/configuracoes/atendimento/categorias", data={"nome": "Impostos"})
        self.assertEqual(CategoriaAtendimento.query.filter_by(nome="Impostos").count(), 1)

    def test_preferencias_e_backup(self):
        self.login("cliente@example.com", "cliente12345")
        self.client.post(
            "/cliente/configuracoes/notificacoes",
            data={"avisos_email": "on", "novas_mensagens": "on"},
        )
        preferencias = PreferenciaNotificacao.query.filter_by(cliente_id=self.cliente.id).first()
        self.assertTrue(preferencias.avisos_email)
        self.assertFalse(preferencias.mensagens_promocionais)

        self.client.get("/logout")
        self.login("admin@example.com", "admin12345")
        self.client.post("/admin/configuracoes/backup/gerar")
        backup = BackupRegistro.query.first()
        self.assertIsNotNone(backup)
        self.assertNotIn("/static/", backup.caminho.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
