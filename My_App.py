import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO E ESTILO ---
st.set_page_config(page_title="Casa das Cuecas", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    .stApp { background-color: #f4f6f9; }
    div[data-testid="stExpander"] { background-color: white; border-radius: 10px; }
    .stButton>button { border-radius: 20px; text-transform: uppercase; font-size: 14px; transition: 0.3s; }
    .stButton>button:hover { transform: scale(1.05); }
    </style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS (CORRIGIDO) ---
def executar(query, params=()):
    with sqlite3.connect('vendas_v30.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

def inicializar():
    # Tabela de Vendedores
    executar('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, ordem INTEGER)''')
    # Tabela de Histórico (Corrigida a aspa tripla aqui)
    executar('''CREATE TABLE IF NOT EXISTS historico 
                 (id INTEGER PRIMARY KEY, vendedor TEXT, valor REAL, data_hora DATETIME)''')

inicializar()

# --- CONTROLE DE ACESSO ---
if 'usuario_ativo' not in st.session_state:
    st.session_state.usuario_ativo = None

if not st.session_state.usuario_ativo:
    st.markdown("<h2 style='text-align: center;'>🔐 Acesso Casa das Cuecas</h2>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
    with col_l2:
        login_tentativa = st.text_input("Digite seu Nome ou Login:").lower().strip()
        if st.button("Entrar no Painel", use_container_width=True):
            with sqlite3.connect('vendas_v30.db') as conn:
                user = pd.read_sql("SELECT * FROM usuarios WHERE login = ? OR nome = ?", 
                                   conn, params=(login_tentativa, login_tentativa.title()))
            if not user.empty:
                st.session_state.usuario_ativo = user.iloc[0]['nome']
                st.rerun()
            else:
                st.error("Vendedor não encontrado. Cadastre-se na aba de gerenciamento.")
    st.stop()

# --- LIMPEZA AUTOMÁTICA (30 DIAS) ---
corte = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
executar("DELETE FROM historico WHERE data_hora < ?", (corte,))

# --- INTERFACE PRINCIPAL ---
st.header(f"👋 Olá, {st.session_state.usuario_ativo}")

tab1, tab2, tab3 = st.tabs(["🚀 Fila da Vez", "🏆 Ranking & Performance", "👤 Gestão de Equipe"])

with tab1:
    with sqlite3.connect('vendas_v30.db') as conn:
        vendedores = pd.read_sql("SELECT * FROM usuarios ORDER BY ordem ASC", conn)
    
    if vendedores.empty:
        st.warning("Nenhum vendedor cadastrado. Vá em 'Gestão de Equipe'.")
    else:
        for idx, v in vendedores.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.subheader(v['nome'])
                c2.write(f"Status Atual: **{v['status']}**")
                
                if v['status'] != 'Em Atendimento':
                    if c3.button("Iniciar Vez", key=f"at_{v['id']}", use_container_width=True):
                        executar("UPDATE usuarios SET status = 'Em Atendimento' WHERE id = ?", (v['id'],))
                        st.rerun()
                else:
                    vlr = c2.number_input("Valor da Venda (R$)", min_value=0.0, key=f"v_{v['id']}")
                    if c3.button("Finalizar", key=f"f_{v['id']}", type="primary", use_container_width=True):
                        if vlr > 0:
                            executar("INSERT INTO historico (vendedor, valor, data_hora) VALUES (?,?,?)",
                                    (v['nome'], vlr, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        
                        # Lógica de Fila: Pega a maior ordem atual e coloca o vendedor depois dela
                        with sqlite3.connect('vendas_v30.db') as conn:
                            res = conn.execute("SELECT MAX(ordem) FROM usuarios").fetchone()[0]
                            max_o = res if res is not None else 0
                        
                        executar("UPDATE usuarios SET status = 'Esperando', ordem = ? WHERE id = ?", (max_o + 1, v['id']))
                        st.success("Atendimento finalizado!")
                        st.rerun()

with tab2:
    st.subheader("📊 Performance dos Últimos 30 Dias")
    with sqlite3.connect('vendas_v30.db') as conn:
        dados = pd.read_sql("""
            SELECT vendedor, SUM(valor) as total, COUNT(*) as vendas_qtd
            FROM historico 
            GROUP BY vendedor 
            ORDER BY total DESC
        """, conn)
    
    if not dados.empty:
        m1, m2, m3 = st.columns(3)
        if len(dados) >= 1:
            m1.metric("🥇 1º Lugar", dados.iloc[0]['vendedor'], f"R$ {dados.iloc[0]['total']:,.2f}")
        if len(dados) >= 2:
            m2.metric("🥈 2º Lugar", dados.iloc[1]['vendedor'], f"R$ {dados.iloc[1]['total']:,.2f}")
        if len(dados) >= 3:
            m3.metric("🥉 3º Lugar", dados.iloc[2]['vendedor'], f"R$ {dados.iloc[2]['total']:,.2f}")
        
        st.divider()
        st.bar_chart(dados.set_index('vendedor')['total'])
        st.dataframe(dados, use_container_width=True)
    else:
        st.info("Nenhuma venda registrada nos últimos 30 dias.")

with tab3:
    st.subheader("Adicionar Novo Vendedor")
    nome_novo = st.text_input("Nome Completo do Funcionário:")
    if st.button("Cadastrar Vendedor"):
        if nome_novo:
            login_auto = nome_novo.lower().replace(" ", ".")
            try:
                executar("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", 
                         (nome_novo.title(), login_auto, 'Esperando', 0))
                st.success(f"Vendedor {nome_novo} cadastrado! Login: {login_auto}")
            except:
                st.error("Este vendedor já existe.")
        else:
            st.warning("Digite um nome.")

with st.sidebar:
    st.divider()
    if st.button("Sair / Trocar de Conta"):
        st.session_state.usuario_ativo = None
        st.rerun()
