import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import io
from PIL import Image

# --- 1. CONFIGURAÇÃO E CSS (ESTILO MONDAY REFINADO) ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;700;800&display=swap');
    
    .stApp { background-color: #F5F6F8 !important; }
    header { visibility: hidden !important; height: 0px !important; }
    .block-container { padding-top: 1rem !important; }

    h1, h2, h3, p, span, label, .stMarkdown { 
        font-family: 'Figtree', sans-serif !important;
        color: #1E1F23 !important; 
        font-weight: 600;
    }

    .monday-card-pro {
        background-color: #FFFFFF !important;
        padding: 30px;
        border-radius: 8px;
        border: 1px solid #D0D4E4;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    .nav-container {
        display: flex;
        gap: 10px;
        background-color: #FFFFFF;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #D0D4E4;
        margin-bottom: 25px;
        align-items: center;
    }

    .stButton > button {
        border-radius: 4px !important;
        font-weight: 800 !important;
        height: 42px;
        border: 1px solid #D0D4E4 !important;
        background-color: #FFFFFF !important;
        transition: all 0.2s;
        text-transform: uppercase;
        font-size: 12px;
    }

    .stButton > button[kind="primary"] {
        background-color: #E8F4FF !important;
        color: #0073EA !important;
        border: 1px solid #A2CFFF !important;
        border-left: 8px solid #0073EA !important;
    }
    
    .btn-logout button {
        border-left: 8px solid #E44258 !important;
        color: #E44258 !important;
        background-color: #FFF0F1 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. ENGINE DE DADOS ---
DB_NAME = 'sistema_elite_v51.db'

def run_db(query, params=(), is_select=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        try:
            if is_select: return pd.read_sql(query, conn, params=params)
            conn.execute(query, params); conn.commit()
            return True
        except Exception: return False

def init_db():
    run_db("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, ordem INTEGER, motivo_pausa TEXT)")
    run_db("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, vendedor TEXT, evento TEXT, motivo TEXT, valor REAL, itens INTEGER, data TEXT)")
    run_db("CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor BLOB)") # BLOB para suportar imagens
    run_db("INSERT OR IGNORE INTO config (chave, valor) VALUES ('meta_loja', 5000.0)")

init_db()

def get_logo():
    res = run_db("SELECT valor FROM config WHERE chave='logo_empresa'", is_select=True)
    if not res.empty and res.iloc[0,0]:
        return res.iloc[0,0]
    return None

# --- 3. LOGIN COM LOGO DINÂMICA ---
if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    _, col_login, _ = st.columns([1, 1.2, 1])
    with col_login:
        st.markdown("<div class='monday-card-pro' style='margin-top: 80px;'>", unsafe_allow_html=True)
        
        # Tenta exibir a logo salva
        logo_data = get_logo()
        if logo_data:
            st.image(logo_data, use_container_width=True)
        else:
            st.markdown("<h2 style='text-align: center; margin-bottom: 20px;'>PRO-Vez Elite</h2>", unsafe_allow_html=True)
        
        u = st.text_input("Usuário").lower()
        p = st.text_input("Senha", type="password")
        if st.button("ENTRAR NO PAINEL", type="primary", use_container_width=True):
            if u == "admin" and p == "admin123":
                st.session_state.logado = True
                st.rerun()
            else: st.error("Acesso negado.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- 4. NAVEGAÇÃO ---
if 'pagina' not in st.session_state: st.session_state.pagina = "OPERAÇÃO"

st.markdown("<div class='nav-container'>", unsafe_allow_html=True)
c1, c2, c3, c_space, c4 = st.columns([1.2, 1.2, 1.2, 3, 1])
with c1:
    if st.button("📋 OPERAÇÃO", type="primary" if st.session_state.pagina == "OPERAÇÃO" else "secondary", use_container_width=True):
        st.session_state.pagina = "OPERAÇÃO"; st.rerun()
with c2:
    if st.button("📊 DESEMPENHO", type="primary" if st.session_state.pagina == "DESEMPENHO" else "secondary", use_container_width=True):
        st.session_state.pagina = "DESEMPENHO"; st.rerun()
with c3:
    if st.button("⚙️ CONFIGURAÇÃO", type="primary" if st.session_state.pagina == "CONFIGURAÇÃO" else "secondary", use_container_width=True):
        st.session_state.pagina = "CONFIGURAÇÃO"; st.rerun()
with c4:
    st.markdown("<div class='btn-logout'>", unsafe_allow_html=True)
    if st.button("SAIR", use_container_width=True):
        st.session_state.logado = False
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# --- 5. CONTEÚDO ---
if st.session_state.pagina == "OPERAÇÃO":
    # (Mantido o código de operação da V57.1...)
    meta_val = float(run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0])
    st.write("### Painel de Atendimento")
    # ... código de faturamento e colunas ...

elif st.session_state.pagina == "CONFIGURAÇÃO":
    st.markdown("<div class='monday-card-pro'>", unsafe_allow_html=True)
    st.write("### ⚙️ CONFIGURAÇÕES")
    
    # SEÇÃO DE LOGO
    st.write("#### 🖼️ LOGO DA EMPRESA")
    logo_atual = get_logo()
    if logo_atual:
        st.image(logo_atual, width=150, caption="Logo atual")
    
    upload_logo = st.file_uploader("Alterar Logo (PNG/JPG)", type=['png', 'jpg', 'jpeg'])
    if upload_logo:
        bytes_data = upload_logo.getvalue()
        if st.button("SALVAR NOVA LOGO", type="primary"):
            run_db("INSERT OR REPLACE INTO config (chave, valor) VALUES ('logo_empresa', ?)", (bytes_data,))
            st.success("Logo atualizada!")
            st.rerun()

    st.divider()
    
    # SEÇÃO DE META
    meta_db = run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0]
    nova_meta = st.number_input("Meta Diária (R$):", value=float(meta_db))
    if st.button("SALVAR META", type="primary"):
        run_db("UPDATE config SET valor=? WHERE chave='meta_loja'", (nova_meta,))
        st.success("Meta salva!")
        
    st.divider()
    st.write("#### 👤 GERENCIAR EQUIPE")
    nn = st.text_input("Nome do Vendedor")
    if st.button("CADASTRAR", type="primary"):
        if nn: run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (nn, nn.lower(), 'Fora', 0)); st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)
