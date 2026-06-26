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
