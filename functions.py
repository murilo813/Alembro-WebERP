from flask import session, redirect, url_for, flash, render_template
from psycopg2.extras import RealDictCursor
import os
from datetime import date
from psycopg2 import pool
from functools import wraps

os.environ['PYTHONUTF8'] = '1'
for key in ['PGPASSFILE', 'PGSERVICEFILE', 'PGHOSTADDR', 'PGUSER', 'PGDATABASE', 'PGPASSWORD', 'PGHOST']:
    os.environ.pop(key, None)

db_host = os.getenv('DB_HOST').strip()
db_port = os.getenv('DB_PORT').strip()
db_name = os.getenv('DB_NAME').strip()
db_user = os.getenv('DB_USER').strip()
db_pass = os.getenv('DB_PASSWORD').strip()

try:
    connection_pool = pool.SimpleConnectionPool(
        1, 20,
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_pass,
        client_encoding='utf8'
    )
    print("✅ POOL DE CONEXÕES INICIALIZADO")
except Exception as e:
    print(f"❌ ERRO AO CRIAR POOL: {e}")

def criar_conexao():
    return connection_pool.getconn()

def liberar_conexao(conexao):
    connection_pool.putconn(conexao)

def carregar_usuario_por_nome(nome):
    try:
        conexao = criar_conexao()
        cursor = conexao.cursor()
        
        cursor.execute("SELECT id, id_empresa, senha FROM usuarios WHERE nome = %s", (nome,))
        usuario = cursor.fetchone()

        return usuario  
    except Exception as e:
        print(f"Erro ao carregar usuário: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conexao:
            liberar_conexao(conexao)
    
def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if 'usuario' not in session:
            flash("Você precisa estar logado para acessar essa página.")
            return redirect(url_for('login.login'))
        return view_func(*args, **kwargs)
    return wrapped_view

def carregar_atendimentos(cpfs):
    try:
        conexao = criar_conexao()
        cursor = conexao.cursor()

        placeholders = ','.join(['%s'] * len(cpfs))

        query_atendimentos = f"""
            SELECT a.nome_cliente, a.cpf_cnpj, a.data_atendimento, a.observacao, 
                u.nomeclatura  
            FROM atendimentos a
            LEFT JOIN usuarios u ON a.usuario = u.nome 
            WHERE a.cpf_cnpj in ({placeholders})
            ORDER BY a.data_atendimento DESC
        """
        cursor.execute(query_atendimentos, cpfs)
        atendimentos = cursor.fetchall()

        atendimentos_dict = [
            {
                'nome_cliente': atendimento[0],
                'cpf_cnpj': atendimento[1],
                'data_atendimento': atendimento[2].strftime('%d/%m/%Y'), 
                'observacao': atendimento[3],
                'usuario': atendimento[4],  
            }
            for atendimento in atendimentos
        ]

        return atendimentos_dict
    except Exception as e:
        print(f"Erro ao carregar atendimentos: {e}")
        return []
    finally:
        liberar_conexao(conexao)

def obter_notificacoes(usuario):
    notificacoes = []
    data_hoje = date.today()

    try:
        conexao = criar_conexao()
        cursor = conexao.cursor(cursor_factory=RealDictCursor)

        # atendimentos
        cursor.execute("""
            SELECT nome_cliente, anotacao, data_agendamento, data, criador, id_not, cpf_cnpj
            FROM not_gerencia
            WHERE criador = %s AND data_agendamento <= %s AND estado = 'ativa'
            ORDER BY data DESC
        """, (usuario, data_hoje))
        atendimentos = cursor.fetchall()

        for atendimento in atendimentos:
            data_atendimento = atendimento['data']
            data_agendamento = atendimento['data_agendamento']

            notificacao = [
                atendimento['nome_cliente'],
                atendimento['anotacao'],
                data_atendimento.strftime('%d/%m/%Y'),
                atendimento['cpf_cnpj']
            ]

            notificacao.append(atendimento['id_not'])  
            notificacoes.append(notificacao)

        # not gerencia
        cursor.execute("""
            SELECT criador, anotacao, id_not
            FROM not_gerencia
            WHERE usuario = %s AND estado = 'ativa'
        """, (usuario,))
        novas_notificacoes = cursor.fetchall()

        for noti in novas_notificacoes:
            notificacoes.append([
                F"De: {noti['criador']}",  
                noti['anotacao'],
                "",
                noti['id_not']
            ])

    except Exception as e:
        print(f"Erro ao buscar notificações: {e}")
    finally:
        if 'conexao' in locals():
            liberar_conexao(conexao)

    return notificacoes

def obter_gastos(usuario_logado):
    try:
        conexao = criar_conexao()
        cursor = conexao.cursor()

        cursor.execute("SELECT id FROM usuarios WHERE nome = %s", (usuario_logado,))
        usuario_id = cursor.fetchone()

        if not usuario_id:
            flash("Usuário não encontrado.")
            return redirect('/login')

        usuario_id = usuario_id[0]  

        cursor.execute("SELECT 1 FROM acessos WHERE usuario_id = %s AND setor_id = 5", (usuario_id,))
        tem_acesso = cursor.fetchone()

        if not tem_acesso:
            return render_template('home.html', erro_gastos=True)  

        cursor.execute("SELECT placa, responsavel FROM frota ORDER BY placa")
        frota = cursor.fetchall()  

        placas = sorted(list(set([f[0] for f in frota])))
        responsaveis = sorted(list(set([f[1] for f in frota])))

        vinculos = {placa: resp for placa, resp in frota}

        cursor.execute("""
            SELECT nome_cliente, cpf_cnpj
            FROM clientes
            WHERE tipo_pessoa = 'J'
            AND perfil_for = true
        """)        
        fornecedor_tuplas = cursor.fetchall()
        fornecedor = [{'nome': f[0], 'cnpj': f[1]} for f in fornecedor_tuplas]

        cursor.execute("""
            SELECT
                placa,
                responsavel,
                tipo_gasto AS gasto,
                fornecedor AS onde,
                doc AS documento,
                TO_CHAR(data, 'DD/MM/YYYY') AS dia,
                valor_total AS valor,
                valor_total_bruto,
                desconto,
                km,
                id_produto AS id_pro,
                produto,
                valor_produto AS valor_unit,
                quantidade,
                total_produto AS total
            FROM gastos
            ORDER BY data
        """)
        registros = cursor.fetchall()
        colunas = [desc[0] for desc in cursor.description]
        dados = []
        doc_anterior = None
        tipo_gasto_anterior = None
        responsavel_anterior = None

        for linha in registros:
            linha_dict = dict(zip(colunas, linha))
            linha_dict = {k: (v if v is not None else None) for k, v in linha_dict.items()}
            doc_atual = linha_dict['documento']
            tipo_gasto_atual = linha_dict['gasto']  
            responsavel_atual = linha_dict['responsavel']  

            valor_bruto = linha_dict.get('valor_total_bruto')
            desconto = linha_dict.get('desconto')

            # CALCULO VALOR TOTAL BRUTO COM DESCONTO
            try:
                bruto = float(valor_bruto) if valor_bruto not in (None, '', 0, '0') else None
                desc = float(desconto or 0)

                if bruto is not None and bruto > 0:
                    valor_exibir_calc = bruto - desc
                else:
                    valor_exibir_calc = float(linha_dict['valor'] or 0)
            except Exception:
                valor_exibir_calc = linha_dict['valor'] or 0

            try:
                linha_dict['valor_exibir'] = f"R$ {float(valor_exibir_calc):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                linha_dict['valor_exibir'] = linha_dict['valor']

            if doc_atual == doc_anterior and tipo_gasto_atual == tipo_gasto_anterior and responsavel_atual == responsavel_anterior:
                linha_dict['placa_exibir'] = ''
                linha_dict['responsavel_exibir'] = ''
                linha_dict['gasto_exibir'] = ''
                linha_dict['onde_exibir'] = ''
                linha_dict['documento_exibir'] = ''
                linha_dict['dia_exibir'] = ''
                linha_dict['valor_exibir'] = ''
                linha_dict['km_exibir'] = ''
            else:
                linha_dict['placa_exibir'] = linha_dict['placa']
                linha_dict['responsavel_exibir'] = linha_dict['responsavel']
                linha_dict['gasto_exibir'] = linha_dict['gasto']
                linha_dict['onde_exibir'] = linha_dict['onde']
                linha_dict['documento_exibir'] = linha_dict['documento']
                linha_dict['dia_exibir'] = linha_dict['dia']
                linha_dict['valor_exibir'] = linha_dict['valor']
                linha_dict['km_exibir'] = linha_dict['km']
                doc_anterior = doc_atual
                tipo_gasto_anterior = tipo_gasto_atual
                responsavel_anterior = responsavel_atual

            dados.append(linha_dict)
        
        gastos_unicos = sorted(set([linha['gasto'] for linha in dados if linha['gasto']]))

        return {
            'placas': placas,
            'responsaveis': responsaveis,
            'vinculos': vinculos,
            'fornecedor': fornecedor,
            'dados': dados,
            'gastos': gastos_unicos
        }, None

    except Exception as e:
        return None, str(e)
    finally:
        liberar_conexao(conexao)