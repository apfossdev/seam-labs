from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
  __tablename__ = 'users'
  
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(80), unique=True, nullable=False)
  password_hash = db.Column(db.String(128), nullable=False)
  role = db.Column(db.Enum('user', 'admin', name='user_roles'),
                   nullable=False, default='user')

  def __repr__(self):
    return f"<User {self.username} ({self.role})>"
