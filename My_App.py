import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import io

# --- 1. CONFIGURAÇÃO E CSS (FOCO NA BARRA SUPERIOR E CARDS) ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;700;800&display=swap');
    
    /* EXTERMÍNIO DA BARRA BRANCA SUPERIOR */
    header, [data-testid="stHeader"] { visibility: hidden !important; height: 0px !important; margin: 0px !important; }
    .block-container { padding-top: 0rem !important; margin-top: -45px !important; }
    .stApp { background-color: #F5F6F8 !important; }

    h1, h2, h3, p, span, label, .stMarkdown { 
        font-family: 'Figtree', sans-serif !important;
        color: #1E1F23 !important; 
        font-weight: 600;
    }

    /* CARD MONDAY UNIFICADO */
    .monday-card-pro {
        background-color: #FFFFFF !important;
        padding: 22px;
        border-radius: 8px;
        border: 1px solid #D0D4E4;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    /* STATUS BADGE DENTRO DO CARD */
    .status-badge {
        background-color: #F0F7FF;
        color: #0073EA;
        padding: 6px;
        border-radius: 4px;
        border: 1px dashed #0073EA;
        text-align: center;
        font-weight: 800;
        font-size: 11px;
        text-transform: uppercase;
        margin-bottom: 12px;
    }

    /* MENU NAVEGAÇÃO */
    .nav-container {
        display: flex;
        gap: 10px;
        background-color: #FFFFFF;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #D0D4E4;
        margin-top: 15px;
        margin-bottom: 25px;
        align-items: center;
    }

    /* BOTÕES ESTILO MONDAY */
    .stButton > button {
        border-radius: 4px !important;
        font-weight: 800 !important;
        height: 40px;
        border: 1px solid #D0D4E4 !important;
        background-color: #FFFFFF !important;
        text-transform: uppercase;
        font-size: 11px;
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
        if logo: st.image(logo, width=180)
        else: st.markdown("<h2 style='text-align:center;'>PRO-Vez Elite</h2>", unsafe_allow_html=True)
        u = st.text_input("Usuário").lower()
        p = st.text_input("Senha", type="password")
        if st.button("ACESSAR", type="primary", use_container_width=True):
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

# --- 5. CONTEÚDO (OPERAÇÃO) ---
if st.session_state.pagina == "OPERAÇÃO":
    # Dash Metas
    meta_val = run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0]
    df_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{get_now().strftime('%Y-%m-%d')}%'", is_select=True)
    vendas = df_hoje[df_hoje['evento'] == 'Sucesso']
    fat_h = vendas['valor'].sum() if not vendas.empty else 0.0
    
    st.markdown(f"""
        <div class='monday-card-pro'>
            <div style='display: flex; justify-content: space-around; align-items: center;'>
                <div style='text-align: center; border-right: 1px solid #E6E9EF; flex: 2;'>
                    <div style='font-weight:700; color:#676879; font-size:12px;'>🎯 FATURAMENTO HOJE</div>
                    <div style='font-size: 28px; font-weight: 800; color: #0073EA;'>R$ {fat_h:,.2f}</div>
                    <div style='font-size: 13px; font-weight:700; color:#E44258;'>Falta: R$ {max(0, float(meta_val) - fat_h):,.2f}</div>
                </div>
                <div style='text-align: center; flex: 1;'>
                    <div style='font-weight:700; color:#676879; font-size:12px;'>📦 P.A. / TICKET</div>
                    <div style='font-size: 18px; font-weight: 800;'>Mantenha o foco!</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.divider()
    c_fila, c_aten, c_fora = st.columns(3)
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)

    with c_fila:
        st.write("### ⏳ FILA DE VEZ")
        fila = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for idx, v in fila.iterrows():
            is_1 = (idx == 0)
            cl = "border-left: 8px solid #00C875; background-color: #F8FFF9;" if is_1 else ""
            st.markdown(f"<div class='monday-card-pro' style='{cl}'><b>{v['nome'].upper()}</b>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            if is_1:
                if b1.button("ATENDER", key=f"at_{v['id']}", type="primary", use_container_width=True):
                    run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()
            else:
                if b1.button("FURAR", key=f"fu_{v['id']}", type="primary", use_container_width=True):
                    st.session_state[f"f_{v['id']}"] = True
            
            if b2.button("PAUSA", key=f"ps_{v['id']}", use_container_width=True):
                st.session_state[f"p_{v['id']}"] = True

            # Lógica Fura-Fila
            if st.session_state.get(f"f_{v['id']}", False):
                mot = st.selectbox("Justificativa:", ["Cliente Voltou", "Troca", "Específico"], key=f"sf_{v['id']}")
                if st.button("Confirmar Furada", key=f"okf_{v['id']}", type="primary"):
                    min_ord = run_db("SELECT MIN(ordem) FROM usuarios WHERE status='Esperando'", is_select=True).iloc[0,0]
                    run_db("UPDATE usuarios SET status='Atendendo', ordem=? WHERE id=?", (int(min_ord or 0) - 1, v['id'])); st.rerun()

            # Lógica Pausa (Almoço/Café)
            if st.session_state.get(f"p_{v['id']}", False):
                mot_p = st.selectbox("Motivo:", ["Almoço", "Café", "Banheiro"], key=f"sp_{v['id']}")
                if st.button("Confirmar Saída", key=f"okp_{v['id']}", type="primary"):
                    run_db("UPDATE usuarios SET status='Fora', ordem=0, motivo_pausa=? WHERE id=?", (mot_p, v['id'])); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with c_aten:
        st.write("### 🚀 ATENDENDO")
        for _, v in vendedores[vendedores['status'] == 'Atendendo'].iterrows():
            st.markdown("<div class='monday-card-pro' style='border-left: 8px solid #0073EA;'>", unsafe_allow_html=True)
            st.markdown(f"<div class='status-badge'>🚀 EM ATENDIMENTO...</div>", unsafe_allow_html=True)
            st.markdown(f"<b>{v['nome'].upper()}</b>", unsafe_allow_html=True)
            res = st.selectbox("Resultado", ["Sucesso", "Não convertido"], key=f"res_{v['id']}")
            v_val, i_val = 0.0, 0
            if res == "Sucesso":
                v_val = st.number_input("R$:", min_value=0.0, key=f"v_{v['id']}")
                i_val = st.number_input("Peças:", min_value=1, step=1, key=f"i_{v['id']}")
            if st.button("GRAVAR", key=f"gr_{v['id']}", type="primary", use_container_width=True):
                max_ord = run_db("SELECT MAX(ordem) FROM usuarios", is_select=True).iloc[0,0]
                run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, "Atendimento", v_val, i_val, get_now().isoformat()))
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (int(max_ord or 0) + 1, v['id'])); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with c_fora:
        st.write("### 💤 FORA")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown("<div class='monday-card-pro'>", unsafe_allow_html=True)
            m_p = v['motivo_pausa'] if v['motivo_pausa'] else "FORA"
            st.markdown(f"<div class='status-badge' style='background-color:#FFF0F1; color:#E44258;'>🍴 EM {m_p.upper()}...</div>", unsafe_allow_html=True)
            st.markdown(f"<b>{v['nome'].upper()}</b>", unsafe_allow_html=True)
            if st.button("RETORNAR", key=f"ret_{v['id']}", type="primary", use_container_width=True):
                max_ord = run_db("SELECT MAX(ordem) FROM usuarios", is_select=True).iloc[0,0]
                run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (int(max_ord or 0) + 1, v['id'])); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.pagina == "CONFIGURAÇÃO":
    st.markdown("<div class='monday-card-pro'>", unsafe_allow_html=True)
    st.write("### ⚙️ CONFIGURAÇÕES")
    
    # 1. LOGO E META
    col_l, col_m = st.columns(2)
    with col_l:
        st.write("#### 🖼️ LOGO")
        up = st.file_uploader("Upload", type=['png','jpg'])
        if up and st.button("SALVAR LOGO", type="primary"):
            run_db("INSERT OR REPLACE INTO config (chave, valor) VALUES ('logo_empresa', ?)", (up.getvalue(),)); st.rerun()
    with col_m:
        st.write("#### 🎯 META")
        nm = st.number_input("Meta Diária:", value=5000.0)
        if st.button("SALVAR META", type="primary"):
            run_db("UPDATE config SET valor=? WHERE chave='meta_loja'", (nm,)); st.rerun()

    st.divider()
    
    # 2. EQUIPE (ADICIONAR E REMOVER)
    st.write("#### 👤 GERENCIAR EQUIPE")
    cn = st.text_input("Nome do Vendedor")
    if st.button("CADASTRAR", type="primary") and cn:
        run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (cn, cn.lower(), 'Fora', 0)); st.rerun()
    
    equipe = run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True)
    for _, r in equipe.iterrows():
        c_n, c_x = st.columns([4,1])
        c_n.write(f"**{r['nome'].upper()}**")
        if c_x.button("X", key=f"del_{r['id']}"):
            run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()

    st.divider()
    
    # 3. ÁREA DE RISCO
    st.write("#### 🚨 ÁREA DE RISCO")
    pwd = st.text_input("Senha Admin", type="password")
    if st.button("ZERAR TUDO", type="primary") and pwd == "admin123":
        run_db("DELETE FROM historico"); st.success("Zerado!"); st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
