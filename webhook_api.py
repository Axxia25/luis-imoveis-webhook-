"""
WEBHOOK API PARA CHATVOLT - PYTHON FLASK
Sistema para receber dados da Chatvolt e registrar na planilha Google
Deploy: Render.com / Railway / Vercel
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import json
import os
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

# Configurações
PLANILHA_ID = "1xtn9-jreUtGPRh_ZQUaeNHq253iztZwXJ8uSmDc2_gc"
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_google_client():
    """Configura cliente Google Sheets"""
    try:
        # Para deploy: usar variável de ambiente
        if os.getenv('GOOGLE_CREDENTIALS'):
            creds_json = json.loads(os.getenv('GOOGLE_CREDENTIALS'))
            creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
        else:
            # Para desenvolvimento local
            creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print(f"Erro ao configurar Google client: {e}")
        return None

def get_worksheet():
    """Obtém a planilha de trabalho"""
    try:
        client = get_google_client()
        if not client:
            return None
            
        sheet = client.open_by_key(PLANILHA_ID)
        
        # Tenta encontrar aba existente ou cria nova
        worksheet_names = ['Leads_Todos_Imoveis', 'Leads_Lancamentos', 'Sheet1']
        worksheet = None
        
        for name in worksheet_names:
            try:
                worksheet = sheet.worksheet(name)
                print(f"Aba encontrada: {name}")
                break
            except:
                continue
        
        if not worksheet:
            worksheet = sheet.add_worksheet(title="Leads_Todos_Imoveis", rows="1000", cols="10")
            setup_headers(worksheet)
            
        return worksheet
    except Exception as e:
        print(f"Erro ao acessar planilha: {e}")
        return None

def setup_headers(worksheet):
    """Configura cabeçalhos da planilha"""
    headers = [
        'Data/Hora', 'Nome', 'Telefone', 'Imóvel/Referência', 
        'Interesse Visita', 'Resumo Conversa', 'Origem', 'ID', 'Status', 'Tipo Imóvel'
    ]
    worksheet.update('A1:J1', [headers])
    print("Cabeçalhos configurados")

def identify_property_type(reference):
    """Identifica tipo do imóvel pela referência"""
    if not reference:
        return 'Indefinido'
    
    ref = str(reference).upper().strip()
    
    if ref.startswith('CA'):
        return 'Casa'
    elif ref.startswith('AP'):
        return 'Apartamento'
    elif ref.startswith('TR'):
        return 'Terreno'
    elif ref.startswith('CO'):
        return 'Comercial'
    elif ref in ['WIND OCEANICA', 'TRESOR CAMBOINHAS']:
        return 'Lançamento'
    
    # Busca por palavras-chave
    if 'CASA' in ref:
        return 'Casa'
    elif any(word in ref for word in ['APARTAMENTO', 'APT']):
        return 'Apartamento'
    elif 'TERRENO' in ref:
        return 'Terreno'
    elif any(word in ref for word in ['COMERCIAL', 'LOJA', 'SALA']):
        return 'Comercial'
    elif any(word in ref for word in ['LANÇAMENTO', 'LANCAMENTO']):
        return 'Lançamento'
    
    return 'Outros'

def generate_id():
    """Gera ID único para o lead"""
    timestamp = datetime.now(pytz.timezone('America/Sao_Paulo')).strftime("%Y%m%d%H%M%S")
    import random
    random_part = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))
    return f'IMV_{timestamp}_{random_part}'

def format_timestamp():
    """Formata timestamp no padrão brasileiro"""
    tz = pytz.timezone('America/Sao_Paulo')
    now = datetime.now(tz)
    return now.strftime("%d/%m/%Y %H:%M:%S")

@app.route('/', methods=['GET'])
def health_check():
    """Endpoint de saúde"""
    return jsonify({
        'status': 'API funcionando',
        'timestamp': datetime.now().isoformat(),
        'endpoints': ['/captura-lancamento', '/captura-imovel-geral']
    })

@app.route('/captura-lancamento', methods=['POST'])
def captura_lancamento():
    """Endpoint para capturar lançamentos específicos (Wind Oceanica/Tresor Camboinhas)"""
    try:
        data = request.get_json()
        
        # Validação
        required_fields = ['user_name', 'user_phone', 'lancamento', 'visit_interest', 'summary']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'status': 400,
                    'error': f'Campo obrigatório ausente: {field}'
                }), 400
        
        # Validação específica para lançamentos
        valid_launches = ['Wind Oceanica', 'Tresor Camboinhas']
        if data['lancamento'] not in valid_launches:
            return jsonify({
                'status': 400,
                'error': f'Lançamento deve ser: {" ou ".join(valid_launches)}'
            }), 400
        
        worksheet = get_worksheet()
        if not worksheet:
            return jsonify({
                'status': 500,
                'error': 'Erro ao acessar planilha'
            }), 500
        
        # Prepara dados
        row_data = [
            format_timestamp(),
            data['user_name'],
            data['user_phone'],
            data['lancamento'],
            data['visit_interest'],
            data['summary'],
            'IA Gabriela - Lançamento',
            generate_id(),
            'Novo',
            'Lançamento'
        ]
        
        # Insere na planilha
        worksheet.append_row(row_data)
        
        return jsonify({
            'status': 200,
            'message': 'Lançamento capturado com sucesso',
            'lead_id': row_data[7],
            'lancamento': data['lancamento'],
            'timestamp': row_data[0]
        })
        
    except Exception as e:
        print(f"Erro em captura-lancamento: {e}")
        return jsonify({
            'status': 500,
            'error': str(e)
        }), 500

@app.route('/captura-imovel-geral', methods=['POST'])
def captura_imovel_geral():
    """Endpoint para capturar interesse em imóveis gerais"""
    try:
        data = request.get_json()
        
        # Validação
        required_fields = ['user_name', 'user_phone', 'imovel_referencia', 'visit_interest', 'summary']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'status': 400,
                    'error': f'Campo obrigatório ausente: {field}'
                }), 400
        
        worksheet = get_worksheet()
        if not worksheet:
            return jsonify({
                'status': 500,
                'error': 'Erro ao acessar planilha'
            }), 500
        
        # Identifica tipo do imóvel
        property_type = identify_property_type(data['imovel_referencia'])
        
        # Prepara dados
        row_data = [
            format_timestamp(),
            data['user_name'],
            data['user_phone'],
            data['imovel_referencia'],
            data['visit_interest'],
            data['summary'],
            'IA Gabriela - Imóvel',
            generate_id(),
            'Novo',
            property_type
        ]
        
        # Insere na planilha
        worksheet.append_row(row_data)
        
        return jsonify({
            'status': 200,
            'message': 'Imóvel capturado com sucesso',
            'lead_id': row_data[7],
            'imovel_referencia': data['imovel_referencia'],
            'tipo_imovel': property_type,
            'timestamp': row_data[0]
        })
        
    except Exception as e:
        print(f"Erro em captura-imovel-geral: {e}")
        return jsonify({
            'status': 500,
            'error': str(e)
        }), 500

@app.route('/dados-dashboard', methods=['GET'])
def dados_dashboard():
    """Endpoint para fornecer dados para o dashboard Streamlit"""
    try:
        worksheet = get_worksheet()
        if not worksheet:
            return jsonify({
                'status': 500,
                'error': 'Erro ao acessar planilha'
            }), 500
        
        # Obtém todos os dados
        data = worksheet.get_all_records()
        
        if not data:
            return jsonify({
                'status': 200,
                'total_leads': 0,
                'dados': []
            })
        
        # Análise dos dados
        total_leads = len(data)
        interesse_visita = sum(1 for row in data if str(row.get('Interesse Visita', '')).lower() in ['true', 'sim', 'yes'])
        
        # Contadores por tipo
        tipos_count = {}
        for row in data:
            tipo = row.get('Tipo Imóvel', 'Outros')
            tipos_count[tipo] = tipos_count.get(tipo, 0) + 1
        
        # Contadores específicos para compatibilidade
        wind_oceanica = sum(1 for row in data if row.get('Imóvel/Referência') == 'Wind Oceanica')
        tresor_camboinhas = sum(1 for row in data if row.get('Imóvel/Referência') == 'Tresor Camboinhas')
        
        return jsonify({
            'status': 200,
            'total_leads': total_leads,
            'interesse_visita': interesse_visita,
            'taxa_interesse': round((interesse_visita / total_leads) * 100) if total_leads > 0 else 0,
            'wind_oceanica': wind_oceanica,
            'tresor_camboinhas': tresor_camboinhas,
            'tipos_imovel': tipos_count,
            'dados': data,
            'ultima_atualizacao': format_timestamp()
        })
        
    except Exception as e:
        print(f"Erro em dados-dashboard: {e}")
        return jsonify({
            'status': 500,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Para desenvolvimento
    app.run(debug=True, host='0.0.0.0', port=5000)
    
    # Para deploy:
    # app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
