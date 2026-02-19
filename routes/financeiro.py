from flask import Blueprint, render_template, request, redirect, session, flash, jsonify
from datetime import date
from functions import carregar_atendimentos, criar_conexao, obter_notificacoes, login_required, liberar_conexao

financeiro_bp = Blueprint('financeiro', __name__)

@financeiro_bp.route('/financeiro', methods=['GET', 'POST'])
@login_required
def financeiro():
    usuario_logado = session['usuario']
    session['notificacoes'] = obter_notificacoes(usuario_logado)
    id_empresa = session.get('id_empresa')

    try:
        conexao = criar_conexao()
        cursor = conexao.cursor()

        cursor.execute("SELECT id FROM usuarios WHERE nome = %s", (usuario_logado,))
        usuario_id = cursor.fetchone()

        if not usuario_id:
            flash("Usuário não encontrado.")
            return redirect('/login')

        usuario_id = usuario_id[0] 

        cursor.execute("""
            SELECT 1 FROM acessos
            WHERE usuario_id = %s AND (setor_id = 2 OR setor_id = 6)
        """, (usuario_id,))

        if not cursor.fetchone():  
            return render_template('home.html', erro_financeiro=True)  

        cpf_url = request.args.get('cpf_cnpj', '').strip() if request.method == 'GET' else None

    except Exception as e:
        print(f"Erro ao verificar acesso: {e}")
        flash("Erro ao verificar acesso. Tente novamente.")
        return redirect('/home')
    
    finally:
        if cursor:
            cursor.close()
        if conexao:
            liberar_conexao(conexao)

    if cpf_url:
        cpf_selecionado = cpf_url  
        nome = ""  
        request.method = 'POST'  
 
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()  
        cpf_selecionado = request.form.get('cpf_selecionado', '').strip() or request.args.get('cpf_cnpj', '').strip()
        data_hoje = date.today().strftime('%Y-%m-%d')

        try:
            conexao = criar_conexao()
            cursor = conexao.cursor()
            atendimentos = []

            if not cpf_selecionado:
                query = """
                    SELECT cpf_cnpj, nome_cliente, responsavel
                    FROM clientes 
                    WHERE (nome_cliente ILIKE %s OR responsavel ILIKE %s) AND ativo = 'S'
                """
                cursor.execute(query, (f"%{nome}%", f"%{nome}%"))
                clientes = cursor.fetchall()
                return render_template('financeiro.html', notificacoes=session['notificacoes'], data_hoje=data_hoje, clientes=clientes)

            else:
                if len(cpf_selecionado) >= 11 and cpf_selecionado.isdigit():
                    query_cliente = """
                        SELECT responsavel
                        FROM clientes
                        WHERE cpf_cnpj = %s AND ativo = 'S'
                    """
                    cursor.execute(query_cliente, (cpf_selecionado,))
                    cliente = cursor.fetchone()
                else:
                    query_cliente = """
                        SELECT responsavel
                        FROM clientes
                        WHERE id_cliente = %s AND ativo = 'S'
                    """
                    cursor.execute(query_cliente, (cpf_selecionado,))                    
                    cliente = cursor.fetchone()

            if cliente:
                query_clientes = """
                    SELECT cpf_cnpj, nome_cliente, responsavel, limite, saldo_limite, limite_calculado, saldo_limite_calculado, maior_dias_atraso, pct_atraso_90, media_dias_atraso
                    FROM clientes
                    WHERE responsavel = %s AND ativo = 'S'
                """
                cursor.execute(query_clientes, (cliente,))
                clientes = cursor.fetchall()

                lista_clientes_detalhes = []
                data_hoje = date.today()

                cpfs = [c[0] for c in clientes]
                atendimentos_combinados = carregar_atendimentos(cpfs)

                for cliente in clientes:
                    cpf_cliente = cliente[0]
                    nome_cliente = cliente[1]
                    responsavel = cliente[2]

                    query_notas = """
                        SELECT
                            id_empresa,
                            nota,
                            parcela,
                            data_venda,
                            data_vencimento,
                            valor_original,
                            saldo_devedor
                        FROM contas_a_receber 
                        WHERE cpf_cnpj = %s
                        ORDER BY data_vencimento
                    """

                    query_contratos = """
                        SELECT 
                            id_empresa,
                            documento,
                            data_geracao,
                            data_vencimento,
                            valor_original,
                            saldo_devedor,
                            tipo_contrato
                        FROM contratos
                        WHERE cpf_cnpj = %s AND saldo_devedor <> 0.00 
                        ORDER BY data_vencimento
                    """

                    query_cheques = """
                        SELECT
                            id_empresa,
                            documento,
                            correntista,
                            recebimento,
                            bom_para,
                            valor_original,
                            saldo_devedor
                        FROM cheques
                        WHERE cpf_cnpj = %s
                        ORDER BY bom_para
                    """

                    query_obs = """
                        SELECT obs, id, tipo
                        FROM contas_obs
                    """

                    cursor.execute(query_notas, (cpf_cliente,))
                    notas = cursor.fetchall()

                    cursor.execute(query_contratos, (cpf_cliente,))
                    contratos = cursor.fetchall()

                    cursor.execute(query_cheques, (cpf_cliente,))
                    cheques = cursor.fetchall()

                    cursor.execute(query_obs)
                    observacoes = cursor.fetchall()

                    obs_dict = {}
                    for obs, id_ref, tipo in observacoes:
                        obs_dict[(tipo, id_ref)] = obs

                    atendimentos_cliente = [
                        a for a in atendimentos_combinados if a['cpf_cnpj'] == cpf_cliente
                    ]

                    cliente_detalhes = {
                        "cpf": cpf_cliente,
                        "nome": nome_cliente,
                        "responsavel": responsavel,
                        "notas": [
                            {
                                "empresa": nota[0],
                                "nota": nota[1],
                                "parcela": nota[2],
                                "data_venda": nota[3].strftime('%d/%m/%Y'),  
                                "data_vencimento": nota[4],  
                                "valor_original": float(nota[5]) if nota[5] else 0.0,
                                "saldo_devedor": float(nota[6]) if nota[6] else 0.0,
                                "obs": obs_dict.get(("nota", nota[1]), "")
                            }
                            for nota in notas
                        ],
                        "contratos": [
                            {
                                "empresa": contrato[0],
                                "documento": contrato[1],
                                "data_geracao": contrato[2].strftime('%d/%m/%Y'),
                                "data_vencimento": contrato[3],
                                "valor_original": float(contrato[4]) if contrato[4] else 0.0,
                                "saldo_devedor": float(contrato[5]) if contrato[5] else 0.0,
                                "tipo_contrato": contrato[6],
                                "obs": obs_dict.get(("contrato", contrato[1]), "")
                            }
                            for contrato in contratos
                        ],
                        "cheques": [
                            {
                                "empresa": cheque[0],
                                "documento": cheque[1],
                                "correntista": cheque[2],
                                "recebimento": cheque[3].strftime('%d/%m/%Y'),
                                "bom_para": cheque[4],
                                "valor_original": float(cheque[5]) if cheque[5] else 0.0,
                                "saldo_devedor": float(cheque[6]) if cheque[6] else 0.0,
                                "obs": obs_dict.get(("cheque", cheque[1]), "")
                            }
                            for cheque in cheques
                        ],
                        "atendimentos": atendimentos_cliente
                    }

                    lista_clientes_detalhes.append(cliente_detalhes)
                    
                    total_a_receber = 0.0
                    total_notas = 0.0
                    total_contratos = 0.0
                    total_cheques = 0.0

                    for cliente in lista_clientes_detalhes:
                        for nota in cliente["notas"]:
                            total_a_receber += nota["saldo_devedor"]
                            total_notas += nota ["saldo_devedor"]
                        for contrato in cliente["contratos"]:
                            total_a_receber += contrato["saldo_devedor"]
                            total_contratos += contrato['saldo_devedor']
                        for cheque in cliente["cheques"]:
                            total_a_receber += cheque["saldo_devedor"]
                            total_cheques += cheque["saldo_devedor"]

                return render_template(
                    'financeiro.html',
                    clientes=clientes,
                    lista_clientes_detalhes=lista_clientes_detalhes,
                    data_hoje=data_hoje,
                    total_a_receber=total_a_receber,
                    total_notas=total_notas,
                    total_contratos=total_contratos,
                    total_cheques=total_cheques,
                    notficacoes=session['notificacoes']
                )
        except Exception as e:
            print(f"Erro na consulta: {e}")
            flash("Ocorreu um erro na consulta.")
            return render_template('financeiro.html')

        finally:
            if 'conexao' in locals():
                liberar_conexao(conexao)

    return render_template('financeiro.html', notificacoes=session['notificacoes'])

@financeiro_bp.route('/salvar_obs_notas', methods=['POST'])
@login_required
def salvar_obs_notas():
    data = request.get_json()
    obs_nota = data.get('observacao')
    id = data.get('id')
    tipo = data.get('tipo')

    try:
        conexao = criar_conexao()
        cursor = conexao.cursor()

        query = """
            INSERT INTO contas_obs (tipo, obs, id)
            VALUES (%s, %s, %s)
        """
        cursor.execute(query, (tipo, obs_nota, id))

        conexao.commit()
        return jsonify({"status": "ok"})

    except Exception as e:
        print("Erro ao salvar observações via sendBeacon:", e)
        return jsonify({"status": "erro"}), 500

    finally:
        if conexao:
            liberar_conexao(conexao)

@financeiro_bp.route('/add_observation', methods=['POST'])
@login_required
def adicionar_observacao():
    try:
        cliente_valor = request.form.get('cliente')
        if '|' in cliente_valor:
            cpf_cnpj, nome_cliente = cliente_valor.split('|')  
        else:
            return jsonify({"error": "Formato inválido para cliente"}), 400
            
        observacao = request.form.get('observation')
        data_atendimento = request.form.get('date')
        data_agendamento = request.form.get('agendamento')
        estado = "ativa"

        if not observacao or not data_atendimento or not nome_cliente or not cpf_cnpj:
            print("Erro: Dados incompletos")
            return jsonify({"error": "Dados incompletos"}), 400

        usuario_logado = session.get('usuario') 
        if not usuario_logado:
            return jsonify({"error": "Usuário não logado"}), 400  

        conexao = criar_conexao()

        with conexao.cursor() as cursor:
            # Inserir atendimento
            query_atendimento = """
            INSERT INTO atendimentos (nome_cliente, cpf_cnpj, data_atendimento, observacao, usuario)
            VALUES (%s, %s, %s, %s, %s)
            """
            valores_atendimento = (nome_cliente.strip(), cpf_cnpj.strip(), data_atendimento.strip(), observacao.strip(), usuario_logado.strip())
            cursor.execute(query_atendimento, valores_atendimento)
            conexao.commit()

            # Buscar CPFs relacionados
            cpfs_relacionados = [cpf_cnpj.strip()]
            clientes_relacionados = []

            query_cliente = """
                SELECT cpf_cnpj, nome_cliente, bairro, responsavel
                FROM clientes
                WHERE cpf_cnpj = %s AND ativo = 'S'
            """
            cursor.execute(query_cliente, (cpf_cnpj.strip(),))
            cliente = cursor.fetchone()

            if cliente:
                cpfs_relacionados = [cliente[0]]

                query_dublos = """
                    SELECT cpf_cnpj, nome_cliente, bairro
                    FROM clientes
                    WHERE nome_cliente = %s AND ativo = 'S'
                """
                cursor.execute(query_dublos, (cliente[1],))
                clientes_duplicados = cursor.fetchall()

                if len(clientes_duplicados) > 1:
                    bairro_selecionado = cliente[2]

                    clientes_com_duplicata = []
                    for rel_cliente in clientes_duplicados:
                        if rel_cliente[0] != cliente[0]:  
                            query_relacionados = """
                                SELECT cpf_cnpj, nome_cliente, bairro
                                FROM clientes
                                WHERE responsavel = %s AND ativo = 'S'
                            """
                            cursor.execute(query_relacionados, (rel_cliente[0],))
                            relacionados = cursor.fetchall()

                            for relacionado in relacionados:
                                if relacionado[1] in [cliente[1] for cliente in clientes_duplicados if cliente[0] != cliente[0]]:
                                    clientes_com_duplicata.append(relacionado)

                    if clientes_com_duplicata:
                        clientes_relacionados = clientes_com_duplicata
                    else:
                        query_relacionados = """
                            SELECT cpf_cnpj, nome_cliente, bairro
                            FROM clientes
                            WHERE responsavel = %s AND ativo = 'S'
                        """
                        cursor.execute(query_relacionados, (cliente[3],))
                        clientes_relacionados = cursor.fetchall()

                else:
                    query_relacionados = """
                        SELECT cpf_cnpj, nome_cliente, bairro
                        FROM clientes
                        WHERE responsavel = %s AND ativo = 'S'
                    """
                    cursor.execute(query_relacionados, (cliente[3],))
                    clientes_relacionados = cursor.fetchall()

                for relacionado in clientes_relacionados:
                    if relacionado[0] not in cpfs_relacionados:
                        cpfs_relacionados.append(relacionado[0])

            # Se houver um agendamento, verificar notificações ativas e inserir a nova
            if data_agendamento:
                query_verifica = """
                SELECT id_not FROM not_gerencia
                WHERE cpf_cnpj = ANY(%s) AND estado = 'ativa'
                """
                cursor.execute(query_verifica, (cpfs_relacionados,))
                notificacoes_ativas = cursor.fetchall()

                # Se existir, atualizar para "inativa"
                if notificacoes_ativas:
                    ids_notificacoes = tuple(noti[0] for noti in notificacoes_ativas)
                    query_inativar = """
                    UPDATE not_gerencia SET estado = 'inativa'
                    WHERE id_not IN %s
                    """
                    cursor.execute(query_inativar, (ids_notificacoes,))
                    conexao.commit()

                # Inserir nova notificação
                query_gerencia = """
                INSERT INTO not_gerencia (nome_cliente, cpf_cnpj, data, anotacao, criador, data_agendamento, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                valores_gerencia = (nome_cliente.strip(), cpf_cnpj.strip(), data_atendimento.strip(), observacao.strip(), usuario_logado.strip(), data_agendamento.strip(), estado)
                cursor.execute(query_gerencia, valores_gerencia)
                conexao.commit()

        return jsonify({"success": "Observação adicionada com sucesso!"}), 200

    except Exception as e:
        print(f"Erro ao adicionar observação: {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        if 'conexao' in locals() and conexao:
            liberar_conexao(conexao)