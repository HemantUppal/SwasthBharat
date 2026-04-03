
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.urandom(24)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    db_url = os.getenv("DATABASE_URL")

    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = db_url
