import os
import re
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from werkzeug.security import generate_password_hash

from app import create_app
from models import (
    BackupRegistro,
    CategoriaAtendimento,
    Cliente,
    HistoricoAcesso,
    LogAuditoria,
    PreferenciaNotificacao,
    SolicitacaoPrivacidade,
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
        return self.post_with_csrf("/login", "/login", {"email": email, "senha": senha})

    def csrf_token_from(self, path):
        resposta = self.client.get(path)
        match = re.search(
            r'name="csrf_token"\s+value="([^"]+)"',
            resposta.get_data(as_text=True),
        )
        self.assertIsNotNone(match, f"csrf_token nao encontrado em {path}")
        return match.group(1)

    def post_with_csrf(self, path, token_path, data=None):
        dados = dict(data or {})
        dados["csrf_token"] = self.csrf_token_from(token_path)
        return self.client.post(path, data=dados)

    def test_admin_acessa_configuracoes_e_cliente_nao(self):
        self.login("admin@example.com", "admin12345")
        self.assertEqual(self.client.get("/admin/configuracoes/conta").status_code, 200)
        self.client.get("/logout")
        self.login("cliente@example.com", "cliente12345")
        resposta = self.client.get("/admin/configuracoes/conta")
        self.assertEqual(resposta.status_code, 302)

    def test_cliente_edita_apenas_propria_conta(self):
        self.login("cliente@example.com", "cliente12345")
        resposta = self.post_with_csrf(
            "/cliente/configuracoes/conta",
            "/cliente/configuracoes/conta",
            data={"acao": "perfil", "nome": "Cliente Novo", "email": "cliente@example.com", "telefone": "92999999999"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(db.session.get(Cliente, self.cliente.id).telefone, "92999999999")
        self.assertIsNone(db.session.get(Cliente, self.outro_cliente.id).telefone)

    def test_email_duplicado_e_senha_incorreta_sao_rejeitados(self):
        self.login("cliente@example.com", "cliente12345")
        self.post_with_csrf(
            "/cliente/configuracoes/conta",
            "/cliente/configuracoes/conta",
            data={"acao": "perfil", "nome": "Cliente", "email": "admin@example.com"},
        )
        self.assertEqual(db.session.get(Usuario, self.cliente_usuario.id).email, "cliente@example.com")
        self.post_with_csrf(
            "/cliente/configuracoes/seguranca",
            "/cliente/configuracoes/seguranca",
            data={"senha_atual": "errada", "nova_senha": "nova12345", "confirmar_senha": "nova12345"},
        )
        self.assertEqual(LogAuditoria.query.filter_by(acao="alterar_senha").count(), 0)

    def test_categoria_duplicada_e_rejeitada(self):
        self.login("admin@example.com", "admin12345")
        self.post_with_csrf(
            "/admin/configuracoes/atendimento/categorias",
            "/admin/configuracoes/atendimento",
            {"nome": "Impostos"},
        )
        self.post_with_csrf(
            "/admin/configuracoes/atendimento/categorias",
            "/admin/configuracoes/atendimento",
            {"nome": "Impostos"},
        )
        self.assertEqual(CategoriaAtendimento.query.filter_by(nome="Impostos").count(), 1)

    def test_preferencias_e_backup(self):
        self.login("cliente@example.com", "cliente12345")
        self.post_with_csrf(
            "/cliente/configuracoes/notificacoes",
            "/cliente/configuracoes/notificacoes",
            data={"avisos_email": "on", "novas_mensagens": "on"},
        )
        preferencias = PreferenciaNotificacao.query.filter_by(cliente_id=self.cliente.id).first()
        self.assertTrue(preferencias.avisos_email)
        self.assertFalse(preferencias.mensagens_promocionais)

        self.client.get("/logout")
        self.login("admin@example.com", "admin12345")
        self.post_with_csrf("/admin/configuracoes/backup/gerar", "/admin/configuracoes/backup")
        backup = BackupRegistro.query.first()
        self.assertIsNotNone(backup)
        self.assertNotIn("/static/", backup.caminho.replace("\\", "/"))

    def test_admin_remove_cliente_com_registros_de_configuracao(self):
        preferencia = PreferenciaNotificacao(cliente_id=self.cliente.id)
        privacidade = SolicitacaoPrivacidade(cliente_id=self.cliente.id, tipo="exclusao")
        acesso = HistoricoAcesso(
            usuario_id=self.cliente_usuario.id,
            email_informado="cliente@example.com",
            sucesso=True,
        )
        auditoria = LogAuditoria(
            usuario_id=self.cliente_usuario.id,
            acao="editar_perfil_cliente",
            descricao="Cliente atualizou dados.",
        )
        backup = BackupRegistro(
            nome_arquivo="backup-cliente.json",
            caminho="backups/backup-cliente.json",
            tamanho_bytes=10,
            status="concluido",
            criado_por_id=self.cliente_usuario.id,
        )
        db.session.add_all([preferencia, privacidade, acesso, auditoria, backup])
        db.session.commit()

        self.login("admin@example.com", "admin12345")
        resposta = self.post_with_csrf(
            f"/admin/clientes/{self.cliente.id}/remover",
            f"/admin/clientes/{self.cliente.id}/remover",
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta.headers["Location"].endswith("/admin/clientes"))
        self.assertIsNone(db.session.get(Cliente, self.cliente.id))
        self.assertIsNone(db.session.get(Usuario, self.cliente_usuario.id))
        self.assertEqual(PreferenciaNotificacao.query.filter_by(cliente_id=self.cliente.id).count(), 0)
        self.assertEqual(SolicitacaoPrivacidade.query.filter_by(cliente_id=self.cliente.id).count(), 0)
        self.assertEqual(HistoricoAcesso.query.filter_by(email_informado="cliente@example.com").count(), 0)
        self.assertIsNone(db.session.get(LogAuditoria, auditoria.id).usuario_id)
        self.assertIsNone(db.session.get(BackupRegistro, backup.id).criado_por_id)


if __name__ == "__main__":
    unittest.main()
