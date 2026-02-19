from flask import Flask, flash, redirect, url_for
from config import Config
from datetime import timedelta
from dotenv import load_dotenv
from extensions import limiter
import os

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.permanent_session_lifetime = timedelta(days=7)

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

limiter.init_app(app)

def register_blueprints():
    from routes.login import login_bp
    from routes.home import home_bp
    from routes.gerencia import gerencia_bp
    from routes.financeiro import financeiro_bp
    from routes.estoque import estoque_bp
    from routes.gastos import gastos_bp
    from routes.addorcamento import addorcamento_bp
    from routes.base import base_bp
    from routes.contratos import contratos_bp
    from routes.compras import compras_bp

    app.register_blueprint(login_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(gerencia_bp)
    app.register_blueprint(financeiro_bp)
    app.register_blueprint(estoque_bp)
    app.register_blueprint(gastos_bp)
    app.register_blueprint(addorcamento_bp)
    app.register_blueprint(base_bp)
    app.register_blueprint(contratos_bp)
    app.register_blueprint(compras_bp)

register_blueprints()

@app.errorhandler(429)
def ratelimit_handler(e):
    flash("Você tentou muitas vezes em pouco tempo. Aguarde 1 minuto e tente novamente.", "error")
    return redirect(url_for('login.index'))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)