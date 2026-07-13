from datetime import datetime
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

from flask import current_app


SITEMAP_BASE_URL = "https://lucianogarcescontabilidade.com.br"
ROBOTS_TXT = """User-agent: *
Allow: /

Sitemap: https://lucianogarcescontabilidade.com.br/sitemap.xml
"""

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
