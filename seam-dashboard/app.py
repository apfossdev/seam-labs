from flask import Flask
import os
from models import db

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'postgresql://postgres:super_duper_secret_postgres_password@localhost:5432/podtracker'
)

db.init_app(app)

with app.app_context():
  db.create_all()
