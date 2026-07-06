import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


load_dotenv()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    DATABASE_URL = os.getenv("DATABASE_URL")

    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "lgcont_db")

    MYSQL_DATABASE_URI = (
        "mysql+pymysql://"
        f"{quote_plus(MYSQL_USER)}:{quote_plus(MYSQL_PASSWORD)}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
    )
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or MYSQL_DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # SMTP usado nos e-mails automáticos do sistema.
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER") or MAIL_USERNAME
    MAIL_SUPPORT_EMAIL = os.getenv("MAIL_SUPPORT_EMAIL") or MAIL_DEFAULT_SENDER
    COMPANY_NAME = os.getenv("COMPANY_NAME", "LG Contabilidade")
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_TIMEOUT = int(os.getenv("MAIL_TIMEOUT", "15"))
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    ACTIVATION_TOKEN_HOURS = int(os.getenv("ACTIVATION_TOKEN_HOURS", "24"))
