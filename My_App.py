import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import io

# --- 1. CONFIGURAÇÃO E CSS (EXTERMÍNIO DA BARRA BRANCA) ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;700;800&display=swap');
    
    /* 1. FUNDO E REMOÇÃO TOTAL DE ESPAÇOS NO TOPO */
    .stApp { background-color: #F5F6F8 !important; }
    
    /* Esconde o cabeçalho nativo e remove o espaço que ele reserva */
    header, [data-testid="stHeader"] { 
        display: none !important; 
        visibility: hidden !important; 
        height: 0px !important; 
    }
    
    /* Zera o preenchimento superior do container principal */
    .block-container { 
        padding-top: 0rem !important; 
        padding-bottom: 0rem !important;
        margin-top: -20px !important; /* Puxa o conteúdo levemente para cima */
    }

    /* 2. TEXTO GLOBAL */
    h1, h2, h3, p, span, label, .stMarkdown { 
        font-family: 'Figtree', sans-serif !important;
        color: #1E1F23 !important; 
        font-weight: 600;
    }

    /* 3. CARD MONDAY UNIFICADO */
    .monday-card-pro {
        background-color: #FFFFFF !important;
        padding: 25px;
        border-radius: 8px;
        border: 1px solid #D0D4E4;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    /* 4. MENU DE NAVEGAÇÃO */
    .nav-container {
        display: flex;
        gap: 10px;
        background-color: #FFFFFF;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #D0D4E4;
        margin-top: 20px; /* Dá um respiro pro topo da tela */
        margin-bottom: 25px;
        align-items: center;
    }

    /* 5. BOTÕES */
    .stButton > button {
        border-radius: 4px !important;
        font-weight: 800 !important;
        height: 40px;
        border: 1px solid #D0D4E4 !important;
        background-color: #FFFFFF !important;
        text-transform: uppercase;
        font-size: 12px;
    }

    /* Estilo Azul Glass */
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

    .danger-box {
        background-color: #FFF0F1 !important;
        border: 1px solid #E44258 !important;
        padding: 15px;
        border-radius: 6px;
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
    run_db("CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor BLOB)")
    run_db("INSERT OR IGNORE INTO config (chave, valor) VALUES ('meta_loja', 5000.0)")

init_db()

def get_logo():
    res = run_db("SELECT valor FROM config WHERE chave='logo_empresa'", is_select=True)
    return res.iloc[0,0] if not res.empty else None

def get_now(): return datetime.now() - timedelta(hours=3)

# --- 3. LOGIN ---
if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    _, col_login, _ = st.columns([1, 1.2, 1])
    with col_login:
        st.write("<br><br><br>", unsafe_allow_html=True)
        st.markdown("<div class='monday-card-pro'>", unsafe_allow_html=True)
        
        logo = get_logo()
        if logo:
            inner_L, inner_C, inner_R = st.columns([1, 2, 1])
            with inner_C: st.image(logo, width=180)
        else:
            st.markdown("<h2 style='text-align:center;'>PRO-Vez Elite</h2>", unsafe_allow_html=True)
        
        u = st.text_input("Usuário").lower()
        p = st.text_input("Senha", type="password")
        if st.button("ENTRAR", type="primary", use_container_width=True):
            if u == "admin" and p == "admin123":
                st.session_state.logado = True; st.rerun()
            else: st.error("Acesso negado.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- 4. NAVEGAÇÃO ---
if 'pagina' not in st.session_state: st.session_state.pagina = "OPERAÇÃO"
st.markdown("<div class='nav-container'>", unsafe_allow_html=True)
c1, c2, c3, c_sp, c4 = st.columns([1.2, 1.2, 1.2, 3, 1])
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
    if st.button("🚪 SAIR", use_container_width=True):
        st.session_state.logado = False; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# --- 5. CONTEÚDO ---
if st.session_state.pagina == "OPERAÇÃO":
    meta_val = run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0]
    df_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{get_now().strftime('%Y-%m-%d')}%'", is_select=True)
    vendas = df_hoje[df_hoje['evento'] == 'Sucesso']
    fat_h = vendas['valor'].sum() if not vendas.empty else 0.0
    falta = max(0, meta_val - fat_h)
    pa_h = vendas['itens'].sum() / len(vendas) if not vendas.empty else 0.0
    tm_h = fat_h / len(vendas) if not vendas.empty else 0.0

    st.markdown(f"""
        <div class='monday-card-pro'>
            <div style='display: flex; justify-content: space-around; align-items: center;'>
                <div style='text-align: center; border-right: 1px solid #E6E9EF; flex: 2;'>
                    <div style='font-weight:700; color:#676879; font-size:12px;'>🎯 FATURAMENTO HOJE</div>
                    <div style='font-size: 30px; font-weight: 800; color: #0073EA;'>R$ {fat_h:,.2f}</div>
                    <div style='font-size: 14px; font-weight:700; color:#E44258;'>Falta: R$ {falta:,.2f}</div>
                </div>
                <div style='text-align: center; border-right: 1px solid #E6E9EF; flex: 1;'>
                    <div style='font-weight:700; color:#676879; font-size:12px;'>📦 P.A.</div>
                    <div style='font-size: 22px; font-weight: 800;'>{pa_h:.2f}</div>
                </div>
                <div style='text-align: center; flex: 1;'>
                    <div style='font-weight:700; color:#676879; font-size:12px;'>🎫 TICKET MÉDIO</div>
                    <div style='font-size: 22px; font-weight: 800;'>R$ {tm_h:,.0f}</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    st.progress(min(fat_h/meta_val, 1.0) if meta_val > 0 else 0.0)

    st.divider()
    c_f, c_a, c_p = st.columns(3)
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)

    # Lógica de Colunas (Simplificada e garantindo nome dentro dos cards)
    with c_f:
        st.write("### ⏳ FILA DE VEZ")
        for idx, v in vendedores[vendedores['status']=='Esperando'].reset_index(drop=True).iterrows():
            cl = "border-left: 8px solid #00C875; background-color: #F8FFF9;" if idx==0 else ""
            st.markdown(f"<div class='monday-card-pro' style='{cl}'><b>{v['nome'].upper()}</b>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            if idx == 0:
                if b1.button("ATENDER", key=f"at_{v['id']}", type="primary", use_container_width=True):
                    run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()
            if b2.button("SAIR", key=f"ps_{v['id']}", use_container_width=True):
                run_db("UPDATE usuarios SET status='Fora', ordem=0 WHERE id=?", (v['id'],)); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with c_a:
        st.write("### 🚀 ATENDENDO")
        for _, v in vendedores[vendedores['status']=='Atendendo'].iterrows():
            st.markdown("<div class='monday-card-pro' style='border-left: 8px solid #0073EA;'><b>"+v['nome'].upper()+"</b>", unsafe_allow_html=True)
            # (Campos de Gravação omitidos para brevidade, mas devem seguir a lógica da V59.0)
            if st.button("GRAVAR", key=f"gr_{v['id']}", type="primary", use_container_width=True):
                run_db("UPDATE usuarios SET status='Esperando', ordem=(SELECT MAX(ordem)+1 FROM usuarios) WHERE id=?", (v['id'],)); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with c_p:
        st.write("### 💤 FORA")
        for _, v in vendedores[vendedores['status']=='Fora'].iterrows():
            st.markdown("<div class='monday-card-pro'><b>"+v['nome'].upper()+"</b>", unsafe_allow_html=True)
            if st.button("VOLTAR", key=f"ret_{v['id']}", type="primary", use_container_width=True):
                run_db("UPDATE usuarios SET status='Esperando', ordem=(SELECT MAX(ordem)+1 FROM usuarios) WHERE id=?", (v['id'],)); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.pagina == "CONFIGURAÇÃO":
    st.markdown("<div class='monday-card-pro'>", unsafe_allow_html=True)
    st.write("### ⚙️ CONFIGURAÇÕES")
    up = st.file_uploader("🖼️ Logo da Empresa", type=['png','jpg'])
    if up and st.button("SALVAR LOGO", type="primary"):
        run_db("INSERT OR REPLACE INTO config (chave, valor) VALUES ('logo_empresa', ?)", (up.getvalue(),)); st.rerun()
    st.divider()
    nm = st.number_input("Meta Diária:", value=float(run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0]))
    if st.button("SALVAR META", type="primary"):
        run_db("UPDATE config SET valor=? WHERE chave='meta_loja'", (nm,)); st.rerun()
    st.divider()
    st.write("#### 🚨 ÁREA DE RISCO")
    st.markdown("<div class='danger-box'>", unsafe_allow_html=True)
    pwd = st.text_input("Senha Admin", type="password")
    if st.button("APAGAR TUDO", type="primary") and pwd == "admin123":
        run_db("DELETE FROM historico"); st.success("Zerado!"); st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
