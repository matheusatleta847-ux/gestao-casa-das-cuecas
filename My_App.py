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
    .stButton>button:hover { transform: scale(1.02); filter: brightness(1.1); }
    </style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS ---
def executar(query, params=()):
    with sqlite3.connect('vendas_v30.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

def inicializar():
    executar('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, ordem INTEGER)''')
    executar('''CREATE TABLE IF NOT EXISTS historico 
                 (id INTEGER PRIMARY KEY, vendedor TEXT, valor REAL, data_hora DATETIME)''')

inicializar()

# --- CONTROLE DE ACESSO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False
    st.session_state.is_admin = False
    st.session_state.usuario_nome = ""

if not st.session_state.logado:
    st.markdown("<h2 style='text-align: center;'>🔐 Login de Acesso</h2>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
    
    with col_l2:
        with st.form("form_login"):
            u_input = st.text_input("Usuário ou Login:")
            p_input = st.text_input("Senha (se Admin):", type="password")
            btn_login = st.form_submit_button("Entrar no Sistema", use_container_width=True)
            
            if btn_login:
                # REGRA 1: Verificação Admin
                if u_input == "admin" and p_input == "admin@123":
                    st.session_state.logado = True
                    st.session_state.is_admin = True
                    st.session_state.usuario_nome = "Administrador"
                    st.rerun()
                
                # REGRA 2: Verificação Vendedor (sem senha)
                else:
                    with sqlite3.connect('vendas_v30.db') as conn:
                        user = pd.read_sql("SELECT * FROM usuarios WHERE login = ? OR nome = ?", 
                                           conn, params=(u_input.lower(), u_input.title()))
                    if not user.empty:
                        st.session_state.logado = True
                        st.session_state.is_admin = False
                        st.session_state.usuario_nome = user.iloc[0]['nome']
                        st.rerun()
                    else:
                        st.error("Acesso negado ou usuário inexistente.")
    st.stop()

# --- LIMPEZA AUTOMÁTICA (30 DIAS) ---
corte = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
executar("DELETE FROM historico WHERE data_hora < ?", (corte,))

# --- INTERFACE PRINCIPAL ---
st.header(f"👋 {st.session_state.usuario_nome}")

# Restrição de Abas: Somente admin vê a aba de Gestão de Equipe
abas = ["🚀 Fila da Vez", "🏆 Ranking & Performance"]
if st.session_state.is_admin:
    abas.append("👤 Gestão de Equipe (Admin)")

tabs = st.tabs(abas)

# --- ABA 1: OPERACIONAL ---
with tabs[0]:
    with sqlite3.connect('vendas_v30.db') as conn:
        vendedores = pd.read_sql("SELECT * FROM usuarios ORDER BY ordem ASC", conn)
    
    if vendedores.empty:
        st.info("Aguardando cadastro de vendedores pelo administrador.")
    else:
        for idx, v in vendedores.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.subheader(v['nome'])
                c2.write(f"Status: **{v['status']}**")
                
                # Só o próprio vendedor ou admin pode mexer no card (Opcional, removi para facilitar)
                if v['status'] != 'Atendendo':
                    if c3.button("Assumir Vez", key=f"at_{v['id']}", use_container_width=True):
                        executar("UPDATE usuarios SET status = 'Atendendo' WHERE id = ?", (v['id'],))
                        st.rerun()
                else:
                    vlr = c2.number_input("Valor Venda", min_value=0.0, key=f"v_{v['id']}")
                    if c3.button("Finalizar", key=f"f_{v['id']}", type="primary", use_container_width=True):
                        if vlr > 0:
                            executar("INSERT INTO historico (vendedor, valor, data_hora) VALUES (?,?,?)",
                                    (v['nome'], vlr, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        
                        with sqlite3.connect('vendas_v30.db') as conn:
                            res = conn.execute("SELECT MAX(ordem) FROM usuarios").fetchone()[0]
                            max_o = res if res is not None else 0
                        
                        executar("UPDATE usuarios SET status = 'Esperando', ordem = ? WHERE id = ?", (max_o + 1, v['id']))
                        st.success("Fila atualizada!")
                        st.rerun()

# --- ABA 2: RANKING ---
with tabs[1]:
    st.subheader("📊 Performance - Últimos 30 Dias")
    with sqlite3.connect('vendas_v30.db') as conn:
        dados = pd.read_sql("SELECT vendedor, SUM(valor) as total FROM historico GROUP BY vendedor ORDER BY total DESC", conn)
    
    if not dados.empty:
        m1, m2, m3 = st.columns(3)
        if len(dados) >= 1: m1.metric("🥇 Líder", dados.iloc[0]['vendedor'], f"R$ {dados.iloc[0]['total']:,.2f}")
        if len(dados) >= 2: m2.metric("🥈 Vice", dados.iloc[1]['vendedor'], f"R$ {dados.iloc[1]['total']:,.2f}")
        
        st.bar_chart(dados.set_index('vendedor')['total'])
    else:
        st.info("Nenhuma venda no período.")

# --- ABA 3: GESTÃO (SÓ ADMIN) ---
if st.session_state.is_admin:
    with tabs[2]:
        st.subheader("👤 Cadastro de Vendedores")
        nome_nv = st.text_input("Nome do Vendedor:")
        if st.button("Salvar e Gerar Login"):
            if nome_nv:
                login_gerado = nome_nv.lower().replace(" ", ".")
                try:
                    executar("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", 
                             (nome_nv.title(), login_gerado, 'Esperando', 0))
                    st.success(f"Vendedor cadastrado! Login: {login_gerado}")
                except:
                    st.error("Erro: Vendedor já existe.")
        
        st.divider()
        st.subheader("🗑️ Limpeza de Sistema")
        if st.button("Resetar Fila e Histórico"):
            executar("DELETE FROM historico")
            executar("DELETE FROM usuarios")
            st.warning("Sistema reiniciado.")

with st.sidebar:
    if st.button("Sair do Sistema"):
        st.session_state.logado = False
        st.rerun()
