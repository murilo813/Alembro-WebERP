from flask import Blueprint, request, session, jsonify
from functions import criar_conexao, liberar_conexao, login_required
from datetime import date

base_bp = Blueprint('base', __name__)

@base_bp.route('/minhascobrancas', methods=['GET'])
@login_required
def minhascobrancas():
    try:
        conexao = criar_conexao()
        cursor = conexao.cursor()
        data_hoje = date.today()
        usuario_logado = session['usuario']

        query_atendimentos = """
            SELECT nome_cliente, observacao
            FROM atendimentos 
            WHERE data_atendimento = %s
            AND usuario = %s
            ORDER BY data_atendimento ASC
        """
        
        cursor.execute(query_atendimentos, (data_hoje, usuario_logado))
        atendimentos = cursor.fetchall()

        return jsonify({"atendimentos": atendimentos})
    
    except Exception as e:
        print(f"Erro ao carregar atendimentos: {e}")
        return jsonify({"atendimentos": []})
    finally:
        if cursor:
            cursor.close()
        if conexao:
            liberar_conexao(conexao)

@base_bp.route('/remover_notificacao', methods=['POST'])
@login_required
def remover_notificacao():
    data = request.json

    if 'usuario' not in session:
        return jsonify({"success": False, "error": "Usuário não autenticado."}), 403
            
    usuario_logado = session['usuario']

    if "id_not" in data:
        id_not = data["id_not"]

        try:
            conexao = criar_conexao()
            cursor = conexao.cursor()

            query = """
                UPDATE not_gerencia
                SET estado = 'inativa'
                WHERE id_not = %s
            """
            cursor.execute(query, (id_not,))
            conexao.commit()

            if cursor.rowcount == 0:
                return jsonify({"success": False, "error": "Notificação não encontrada."}), 404

            return jsonify({"success": True})

        except ValueError:
            return jsonify({"success": False, "error": "ID inválido."}), 400

        except Exception as e:
            print(f"Erro ao remover notificação: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

        finally:
            if 'conexao' in locals():
                liberar_conexao(conexao)

    return jsonify({"success": False, "error": "Dados inválidos."}), 400