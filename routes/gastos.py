from flask import Blueprint, render_template, request, session, flash, redirect
from functions import criar_conexao, obter_notificacoes, liberar_conexao, login_required, obter_gastos
from datetime import datetime

gastos_bp = Blueprint('gastos', __name__)

@gastos_bp.route('/gastos')
@login_required
def gastos():
    usuario_logado = session['usuario']
    resultado, erro = obter_gastos(usuario_logado) 

    if erro:
        flash(erro)
        return redirect('/gastos')

    session['notificacoes'] = obter_notificacoes(usuario_logado)

    return render_template('gastos.html',
                           notificacoes=session['notificacoes'],
                           placas=resultado['placas'],
                           responsaveis=resultado['responsaveis'],
                           vinculos=resultado['vinculos'],
                           fornecedor=resultado['fornecedor'],
                           dados=resultado['dados'],
                           gastos=resultado['gastos'])

@gastos_bp.route('/registrargastos', methods=["POST"])
@login_required
def registrargastos():

    usuario_logado = session['usuario']

    try:
        placa = request.form['placa']
        responsavel = request.form['responsavel']
        tipo_gasto = request.form['gasto'].upper()
        fornecedor = request.form['onde']
        doc = request.form['documento']
        data = request.form['dia']
        valor_total = request.form['valor'].replace('R$', '').replace('.', '').replace(',', '.').strip()
        valor_bruto = request.form.get('valor_bruto', '').replace('R$', '').replace('.', '').replace(',', '.').strip()
        desconto = request.form['desconto'].replace('R$', '').replace('.', '').replace(',', '.').strip()
        if desconto == '':
            desconto = 0.0
        km = request.form['km'].replace('.', '').strip()

        ids_produto = request.form.getlist('id_pro[]')
        produtos = request.form.getlist('produto[]')
        valores_unit = request.form.getlist('valor_unit[]')
        quantidades = request.form.getlist('quantidade[]')
        totais_produto = request.form.getlist('total[]')
        empresa = request.form.get('empresa')

        if empresa == 'Bela Vista':
            id_empresa = 1
        elif empresa == 'Imbuia':
            id_empresa = 2
        elif empresa == 'Vila Nova':
            id_empresa = 3
        elif empresa == 'Aurora': 
            id_empresa = 4
        else:
            empresa = 5

        conexao = criar_conexao()
        with conexao.cursor() as cursor:
            for i in range(len(produtos)):
                if not produtos[i].strip():
                    continue

                valor_prod = valores_unit[i].replace('R$', '').replace('.', '').replace(',', '.').strip()
                total_prod = totais_produto[i].replace('R$', '').replace('.', '').replace(',', '.').strip()
                qtd = quantidades[i].strip() or '0'

                cursor.execute("""
                    INSERT INTO gastos (
                        placa, responsavel, tipo_gasto, fornecedor, doc, data, valor_total, km,
                        id_produto, produto, valor_produto, quantidade, total_produto, desconto, usuario, empresa, valor_total_bruto
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    placa,
                    responsavel,
                    tipo_gasto,
                    fornecedor,
                    doc,
                    datetime.strptime(data, '%Y-%m-%d').date(),
                    valor_total,
                    int(km) if km else None,
                    ids_produto[i],
                    produtos[i],
                    valor_prod,
                    qtd,
                    total_prod,
                    desconto,
                    usuario_logado,
                    id_empresa,
                    valor_bruto
                ))

            conexao.commit()

        return redirect('/gastos')

    except Exception as e:
        print(f"Erro ao registrar gastos: {e}")
        return "Erro ao registrar dados", 500

    finally:
        if conexao:
            liberar_conexao(conexao)
