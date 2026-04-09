import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO E ESTILO ---
st.set_page_config(page_title="Casa das Cuecas", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f6f9; }
    div[data-testid="stExpander"] { background-color: white; border-radius: 10px; }
    .stButton>button { border-radius: 20px; text-transform: uppercase; font-size: 14px; }
    </style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS ---
def executar(query, params=()):
    with sqlite3.connect('vendas_simples.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

def inicializar():
    executar('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, ordem INTEGER)''')
    executar('''CREATE TABLE IF NOT EXISTS historico 
                 (id INTEGER PRIMARY KEY, vendedor TEXT, valor REAL, data_hora DATETIME)''")

inicializar()

# --- CONTROLE DE ACESSO ---
if 'usuario_ativo' not in st.session_state:
    st.session_state.usuario_ativo = None

if not st.session_state.usuario_ativo:
    st.title("🔒 Acesso")
    login_tentativa = st.text_input("Digite seu nome ou login para entrar:").lower().strip()
    if st.button("Acessar Painel"):
        user = pd.read_sql("SELECT * FROM usuarios WHERE login = ? OR nome = ?", 
                           sqlite3.connect('vendas_simples.db'), params=(login_tentativa, login_tentativa))
        if not user.empty:
            st.session_state.usuario_ativo = user.iloc[0]['nome']
            st.rerun()
        else:
            st.error("Vendedor não encontrado.")
    st.stop()

# --- LIMPEZA AUTOMÁTICA (30 DIAS) ---
corte = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
executar("DELETE FROM historico WHERE data_hora < ?", (corte,))

# --- INTERFACE PRINCIPAL ---
st.header(f"👋 Olá, {st.session_state.usuario_ativo}")

tab1, tab2, tab3 = st.tabs(["🚀 Fila da Vez", "📊 Relatório 30d", "➕ Adicionar Vendedor"])

with tab1:
    vendedores = pd.read_sql("SELECT * FROM usuarios ORDER BY ordem ASC", sqlite3.connect('vendas_simples.db'))
    
    if vendedores.empty:
        st.warning("Nenhum vendedor cadastrado.")
    else:
        for idx, v in vendedores.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.subheader(v['nome'])
                c2.write(f"Status: **{v['status']}**")
                
                if v['status'] == 'Esperando':
                    if c3.button("Atender", key=f"at_{v['id']}", use_container_width=True):
                        executar("UPDATE usuarios SET status = 'Em Atendimento' WHERE id = ?", (v['id'],))
                        st.rerun()
                else:
                    vlr = c2.number_input("Valor da Venda", min_value=0.0, key=f"v_{v['id']}")
                    if c3.button("Finalizar", key=f"f_{v['id']}", type="primary", use_container_width=True):
                        if vlr > 0:
                            executar("INSERT INTO historico (vendedor, valor, data_hora) VALUES (?,?,?)",
                                    (v['nome'], vlr, datetime.now()))
                        # Move para o fim da fila
                        max_o = pd.read_sql("SELECT MAX(ordem) as m FROM usuarios", sqlite3.connect('vendas_simples.db')).iloc[0]['m'] or 0
                        executar("UPDATE usuarios SET status = 'Esperando', ordem = ? WHERE id = ?", (max_o + 1, v['id']))
                        st.rerun()

with tab2:
    st.subheader("Vendas dos Últimos 30 Dias")
    dados = pd.read_sql("SELECT * FROM historico", sqlite3.connect('vendas_simples.db'))
    if not dados.empty:
        st.metric("Total Acumulado", f"R$ {dados['valor'].sum():,.2f}")
        st.bar_chart(dados.groupby('vendedor')['valor'].sum())
    else:
        st.info("Sem dados no período.")

with tab3:
    st.subheader("Novo Vendedor")
    # Apenas o nome é solicitado
    nome_novo = st.text_input("Nome Completo:")
    if st.button("Salvar Vendedor"):
        if nome_novo:
            # Gera login automático removendo espaços e pondo ponto (ex: Matheus Silva -> matheus.silva)
            login_auto = nome_novo.lower().replace(" ", ".")
            try:
                executar("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", 
                         (nome_novo.title(), login_auto, 'Esperando', 0))
                st.success(f"{nome_novo} adicionado! Login de acesso: {login_auto}")
            except:
                st.error("Este nome/login já existe.")

with st.sidebar:
    if st.button("Sair do Sistema"):
        st.session_state.usuario_ativo = None
        st.rerun()
