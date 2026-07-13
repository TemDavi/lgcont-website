import json
import secrets
from datetime import date, datetime
from pathlib import Path

from flask import current_app

from models import (
    BackupRegistro,
    CategoriaAtendimento,
    Cliente,
    ConfiguracaoAtendimento,
    ConfiguracaoEmpresa,
    ConfiguracaoPaginaInicial,
    ConfiguracaoSistema,
    ItemPaginaInicial,
    Pendencia,
    ServicoCliente,
    SolicitacaoAtendimento,
    Usuario,
)


def caminho_backups():
    caminho = Path(current_app.instance_path) / "backups"
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


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
