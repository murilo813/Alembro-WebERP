from flask import Blueprint, session, render_template
from functions import criar_conexao, obter_notificacoes, liberar_conexao, login_required

home_bp = Blueprint('home', __name__)

@home_bp.route('/home')
@login_required
def home():

    usuario_logado = session['usuario']

    try:
        conexao = criar_conexao()
        cursor = conexao.cursor()

        query = """
            SELECT nomeclatura
            FROM usuarios
            WHERE nome = %s
        """
        cursor.execute(query, (usuario_logado,))
        resultado = cursor.fetchone()
        nomeclatura = resultado[0] if resultado else 'Usuário'
        session['nomeclatura'] = nomeclatura

    except Exception as e:
        print(f"Erro ao buscar nomeclatura: {e}")
        nomeclatura = 'Usuário'
    finally:
        if conexao:
            liberar_conexao(conexao)

    session['notificacoes'] = obter_notificacoes(usuario_logado)

    return render_template('home.html', nomeclatura=nomeclatura, notificacoes=session['notificacoes'])