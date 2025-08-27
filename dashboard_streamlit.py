"""
DASHBOARD STREAMLIT - LUIS IMÓVEIS
Sistema expandido de análise de leads
Deploy: Streamlit Cloud
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import gspread
from google.oauth2.service_account import Credentials
import json
import os
from datetime import datetime, timedelta
import pytz

# Configuração da página
st.set_page_config(
    page_title="Dashboard Luis Imóveis",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configurações
PLANILHA_ID = "1xtn9-jreUtGPRh_ZQUaeNHq253iztZwXJ8uSmDc2_gc"
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

@st.cache_data(ttl=300)  # Cache por 5 minutos
def get_data_from_sheets():
    """Carrega dados da planilha Google"""
    try:
        # Configurar credenciais
        if 'GOOGLE_CREDENTIALS' in st.secrets:
            creds_json = dict(st.secrets['GOOGLE_CREDENTIALS'])
            creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
        else:
            # Para desenvolvimento local
            creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        
        client = gspread.authorize(creds)
        sheet = client.open_by_key(PLANILHA_ID)
        
        # Busca por abas existentes
        worksheet_names = ['Leads_Todos_Imoveis', 'Leads_Lancamentos', 'Sheet1']
        worksheet = None
        
        for name in worksheet_names:
            try:
                worksheet = sheet.worksheet(name)
                break
            except:
                continue
        
        if not worksheet:
            st.error("Nenhuma aba encontrada na planilha")
            return pd.DataFrame()
        
        # Carrega dados
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            return df
        
        # Processamento dos dados
        df['Data/Hora'] = pd.to_datetime(df['Data/Hora'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        df['Interesse_Bool'] = df['Interesse Visita'].str.lower().isin(['true', 'sim', 'yes'])
        
        # Identifica tipo do imóvel se não existe a coluna
        if 'Tipo Imóvel' not in df.columns or df['Tipo Imóvel'].isna().all():
            df['Tipo Imóvel'] = df['Imóvel/Referência'].apply(identify_property_type)
        
        return df
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def identify_property_type(reference):
    """Identifica tipo do imóvel pela referência"""
    if pd.isna(reference):
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

def create_metrics_cards(df):
    """Cria cards de métricas principais"""
    if df.empty:
        st.warning("Nenhum dado encontrado")
        return
    
    total_leads = len(df)
    interesse_leads = df['Interesse_Bool'].sum()
    taxa_interesse = (interesse_leads / total_leads * 100) if total_leads > 0 else 0
    
    # Contadores por tipo
    tipos_count = df['Tipo Imóvel'].value_counts().to_dict()
    
    # Lançamentos específicos para compatibilidade
    wind_count = len(df[df['Imóvel/Referência'] == 'Wind Oceanica'])
    tresor_count = len(df[df['Imóvel/Referência'] == 'Tresor Camboinhas'])
    
    # Exibir métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Leads", total_leads)
        st.metric("Taxa de Interesse", f"{taxa_interesse:.1f}%")
    
    with col2:
        st.metric("Interesse em Visita", interesse_leads)
        st.metric("Sem Interesse", total_leads - interesse_leads)
    
    with col3:
        st.metric("Lançamentos", tipos_count.get('Lançamento', 0))
        st.metric("Wind Oceanica", wind_count)
    
    with col4:
        st.metric("Tresor Camboinhas", tresor_count)
        st.metric("Imóveis Gerais", total_leads - wind_count - tresor_count)

def create_property_type_chart(df):
    """Gráfico de distribuição por tipo de imóvel"""
    if df.empty:
        return
    
    tipos_count = df['Tipo Imóvel'].value_counts()
    
    fig = px.pie(
        values=tipos_count.values,
        names=tipos_count.index,
        title="Distribuição por Tipo de Imóvel",
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

def create_interest_analysis(df):
    """Análise de interesse por tipo"""
    if df.empty:
        return
    
    interesse_por_tipo = df.groupby('Tipo Imóvel').agg({
        'Interesse_Bool': ['count', 'sum']
    }).round(2)
    
    interesse_por_tipo.columns = ['Total', 'Com_Interesse']
    interesse_por_tipo['Taxa_Interesse'] = (
        interesse_por_tipo['Com_Interesse'] / interesse_por_tipo['Total'] * 100
    ).round(1)
    interesse_por_tipo = interesse_por_tipo.reset_index()
    
    # Gráfico de barras
    fig = px.bar(
        interesse_por_tipo,
        x='Tipo Imóvel',
        y=['Total', 'Com_Interesse'],
        title="Interesse por Tipo de Imóvel",
        barmode='group',
        color_discrete_sequence=['#3498db', '#2ecc71']
    )
    
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabela de detalhes
    st.subheader("Detalhes por Tipo")
    st.dataframe(interesse_por_tipo, use_container_width=True)

def create_timeline_chart(df):
    """Gráfico de evolução temporal"""
    if df.empty:
        return
    
    # Agrupa por dia
    df_daily = df.set_index('Data/Hora').resample('D').agg({
        'Nome': 'count',
        'Interesse_Bool': 'sum'
    }).reset_index()
    
    df_daily.columns = ['Data', 'Total_Leads', 'Com_Interesse']
    df_daily = df_daily[df_daily['Total_Leads'] > 0]  # Remove dias sem leads
    
    if df_daily.empty:
        st.warning("Dados insuficientes para análise temporal")
        return
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Leads totais
    fig.add_trace(
        go.Scatter(
            x=df_daily['Data'],
            y=df_daily['Total_Leads'],
            mode='lines+markers',
            name='Total Leads',
            line=dict(color='#3498db')
        ),
        secondary_y=False,
    )
    
    # Leads com interesse
    fig.add_trace(
        go.Scatter(
            x=df_daily['Data'],
            y=df_daily['Com_Interesse'],
            mode='lines+markers',
            name='Com Interesse',
            line=dict(color='#2ecc71')
        ),
        secondary_y=False,
    )
    
    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text="Número de Leads", secondary_y=False)
    fig.update_layout(title_text="Evolução de Leads ao Longo do Tempo", height=400)
    
    st.plotly_chart(fig, use_container_width=True)

def create_referencia_analysis(df):
    """Análise das referências mais populares"""
    if df.empty:
        return
    
    ref_count = df['Imóvel/Referência'].value_counts().head(10)
    
    if ref_count.empty:
        st.warning("Nenhuma referência encontrada")
        return
    
    fig = px.bar(
        x=ref_count.values,
        y=ref_count.index,
        orientation='h',
        title="Top 10 Referências Mais Procuradas",
        color=ref_count.values,
        color_continuous_scale='viridis'
    )
    
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

def create_hourly_analysis(df):
    """Análise por horário"""
    if df.empty or df['Data/Hora'].isna().all():
        return
    
    df_hourly = df.copy()
    df_hourly['Hora'] = df_hourly['Data/Hora'].dt.hour
    
    hourly_stats = df_hourly.groupby('Hora').agg({
        'Nome': 'count',
        'Interesse_Bool': 'sum'
    }).reset_index()
    
    hourly_stats.columns = ['Hora', 'Total', 'Com_Interesse']
    hourly_stats['Taxa_Interesse'] = (
        hourly_stats['Com_Interesse'] / hourly_stats['Total'] * 100
    ).round(1)
    
    fig = px.line(
        hourly_stats,
        x='Hora',
        y=['Total', 'Com_Interesse'],
        title="Distribuição de Leads por Horário",
        markers=True
    )
    
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

def main():
    """Função principal do dashboard"""
    
    # Header
    st.title("Dashboard Luis Imóveis")
    st.subheader("Sistema Expandido de Gestão de Leads")
    
    # Sidebar com filtros
    st.sidebar.title("Filtros")
    
    # Carrega dados
    with st.spinner("Carregando dados da planilha..."):
        df = get_data_from_sheets()
    
    if df.empty:
        st.error("Não foi possível carregar os dados da planilha")
        st.stop()
    
    # Filtros na sidebar
    tipos_disponiveis = ['Todos'] + list(df['Tipo Imóvel'].unique())
    tipo_selecionado = st.sidebar.selectbox("Filtrar por Tipo:", tipos_disponiveis)
    
    # Filtro de período
    if not df['Data/Hora'].isna().all():
        data_min = df['Data/Hora'].min().date()
        data_max = df['Data/Hora'].max().date()
        
        periodo = st.sidebar.date_input(
            "Período:",
            value=(data_max - timedelta(days=30), data_max),
            min_value=data_min,
            max_value=data_max
        )
        
        # Aplicar filtro de período
        if len(periodo) == 2:
            mask = (df['Data/Hora'].dt.date >= periodo[0]) & (df['Data/Hora'].dt.date <= periodo[1])
            df = df[mask]
    
    # Aplicar filtro de tipo
    if tipo_selecionado != 'Todos':
        df = df[df['Tipo Imóvel'] == tipo_selecionado]
    
    # Status do sistema
    st.success(f"Sistema funcionando - {len(df)} leads encontrados")
    
    # Cards de métricas
    create_metrics_cards(df)
    
    # Layout em colunas
    col1, col2 = st.columns(2)
    
    with col1:
        create_property_type_chart(df)
        create_timeline_chart(df)
    
    with col2:
        create_interest_analysis(df)
        create_referencia_analysis(df)
    
    # Análise horária
    st.subheader("Análise por Horário")
    create_hourly_analysis(df)
    
    # Tabela de dados
    st.subheader("Dados Detalhados")
    
    if not df.empty:
        # Preparar dados para exibição
        df_display = df[[
            'Data/Hora', 'Nome', 'Telefone', 'Imóvel/Referência',
            'Interesse Visita', 'Tipo Imóvel', 'Status'
        ]].copy()
        
        # Formatar data
        if not df_display['Data/Hora'].isna().all():
            df_display['Data/Hora'] = df_display['Data/Hora'].dt.strftime('%d/%m/%Y %H:%M')
        
        st.dataframe(df_display, use_container_width=True)
        
        # Botão de download
        csv = df_display.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f'leads_luis_imoveis_{datetime.now().strftime("%Y%m%d")}.csv',
            mime='text/csv'
        )
    
    # Footer com informações
    st.markdown("---")
    st.markdown(
        f"**Sistema Expandido v2.0** | "
        f"Última atualização: {datetime.now(pytz.timezone('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M:%S')} | "
        f"Dados em tempo real da planilha Google"
    )

if __name__ == "__main__":
    main()
