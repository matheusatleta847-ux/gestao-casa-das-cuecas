import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date, time
import plotly.express as px
import io

# --- 1. CONFIGURAÇÃO E CSS (FONTE ENCORPADA & CONTRASTE) ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;700;800&display=swap');

    /* Fundo suave Monday */
    .stApp { background-color: #F5F6F8 !important; }
    
    /* Global Text - FORTE E EM NEGRITO */
    h1, h2, h3, p, span, label, .stMarkdown { 
        font-family: 'Figtree', sans-serif !important;
        color: #1E1F23 !important; /* Grafite quase preto para contraste total */
    }

    /* Títulos de Seções */
    h3 { font-weight: 800 !important; font-size: 22px !important; }

    /* Cartão Monday White */
    .monday-card {
        background-color: #FFFFFF !important;
        padding: 24px;
        border-radius: 8px;
        border: 1px solid #C3C6D4;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        margin-bottom: 20px;
    }

    /* Meta Valor - SUPER DESTAQUE */
    .meta-valor {
        font-size: 34px;
        font-weight: 800;
        color: #0073EA !important;
    }

    /* Item da Fila - Nomes em Negrito */
    .vendedor-item {
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 10px;
        background-color: #FFFFFF !important;
        border: 1px solid #BDC1D1;
    }
    .vendedor-nome-texto {
        font-weight: 700 !important;
        font-size: 18px !important;
        letter-spacing: -0.5px;
    }
    
    .primeiro-da-vez {
        border-left: 8px solid #00C875 !important;
        background-color: #F0FFF4 !important;
    }

    /* BOTÕES - BORDAS MAIS FORTES */
    .stButton > button {
        border-radius: 4px !important;
        font-weight: 700 !important;
        height: 40px;
        border: 2px solid #D0D4E4 !important;
        color: #1E1F23 !important;
    }

    /* Botão Primário Azul */
    .stButton > button[kind="primary"] {
        background-color: #0073EA !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    
    /* Inputs com texto forte */
    input, select, textarea { font-weight: 600 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE DADOS ---
DB_NAME = 'sistema_elite_v51.db'

def run_db(query, params=(), is_select=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        try:
            if is_select: return pd.read_sql(query, conn, params=params)
            conn.execute(query, params); conn.commit()
            return True
        except Exception: return False

def init_db():
    run_db("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, ordem INTEGER)")
    run_db("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, vendedor TEXT, evento TEXT, motivo TEXT, valor REAL, itens INTEGER, data TEXT)")
    run_db("CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor REAL)")
    run_db("INSERT OR IGNORE INTO config VALUES ('meta_loja', 5000.0)")

init_db()

def get_now(): return datetime.now() - timedelta(hours=3)
def get_max_ordem(): 
    res = run_db("SELECT MAX(ordem) FROM usuarios", is_select=True).iloc[0,0]
    return (int(res) if res else 0) + 1
def get_min_ordem(): 
    res = run_db("SELECT MIN(ordem) FROM usuarios WHERE status='Esperando'", is_select=True).iloc[0,0]
    return (int(res) if res else 0) - 1

# --- 3. LOGIN ---
if 'user' not in st.session_state: st.session_state.user = None
if not st.session_state.user:
    with st.columns([1,1,1])[1]:
        st.markdown("<div class='monday-card'>", unsafe_allow_html=True)
        st.title("Acesse o Painel")
        u, p = st.text_input("Login").lower(), st.text_input("Senha", type="password")
        if st.button("Entrar", type="primary", use_container_width=True):
            if u == "admin" and p == "admin123": 
                st.session_state.user = {"nome":"Admin", "role":"admin"}
                st.rerun()
            else: st.error("Dados incorretos.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

tab1, tab2, tab3 = st.tabs(["📋 OPERAÇÃO", "📊 DESEMPENHO", "⚙️ CONFIGURAÇÕES"])

with tab1:
    meta_val = run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0]
    hoje_dt = get_now().strftime('%Y-%m-%d')
    df_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{hoje_dt}%'", is_select=True)
    fat_h = df_hoje[df_hoje['evento']=='Sucesso']['valor'].sum() if not df_hoje.empty else 0
    
    st.markdown("<div class='monday-card'>", unsafe_allow_html=True)
    st.write("🎯 **META DIÁRIA**")
    st.markdown(f"<div class='meta-valor'>R$ {fat_h:,.2f} <span style='font-size:16px; color:#676879; font-weight:700;'>/ R$ {meta_val:,.2f}</span></div>", unsafe_allow_html=True)
    st.progress(min(fat_h/meta_val, 1.0) if meta_val > 0 else 0.0)
    st.markdown("</div>", unsafe_allow_html=True)

    c_f, c_a, c_p = st.columns(3)
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)

    with c_f:
        st.write("### ⏳ FILA DE VEZ")
        fila = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for idx, v in fila.iterrows():
            is_1 = (idx == 0)
            cl = "vendedor-item primeiro-da-vez" if is_1 else "vendedor-item"
            st.markdown(f"<div class='{cl}'><span class='vendedor-nome-texto'>{v['nome'].upper()}</span>", unsafe_allow_html=True)
            
            b_cols = st.columns([1, 1, 1])
            if is_1:
                if b_cols[0].button("ATENDER", key=f"at_{v['id']}", type="primary"):
                    run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()
            else:
                if b_cols[0].button("FURAR", key=f"fu_{v['id']}"):
                    st.session_state[f"f_{v['id']}"] = True
            
            if b_cols[1].button("SAIR", key=f"ps_{v['id']}"):
                st.session_state[f"p_{v['id']}"] = True

            if st.session_state.get(f"f_{v['id']}", False):
                mot_f = st.selectbox("**Justificativa:**", ["Cliente Voltou", "Específico", "Troca"], key=f"s_f_{v['id']}")
                if st.button("Confirmar Furada", key=f"ok_f_{v['id']}", type="primary"):
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Fura-Fila", mot_f, 0.0, 0, get_now().isoformat()))
                    run_db("UPDATE usuarios SET status='Atendendo', ordem=? WHERE id=?", (get_min_ordem(), v['id']))
                    st.session_state[f"f_{v['id']}"] = False; st.rerun()

            if st.session_state.get(f"p_{v['id']}", False):
                mot_p = st.selectbox("**Motivo:**", ["Almoço", "Banheiro", "Café"], key=f"s_p_{v['id']}")
                if st.button("Confirmar Saída", key=f"ok_p_{v['id']}", type="primary"):
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Saída", mot_p, 0.0, 0, get_now().isoformat()))
                    run_db("UPDATE usuarios SET status='Fora', ordem=0 WHERE id=?", (v['id'],))
                    st.session_state[f"p_{v['id']}"] = False; st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with c_a:
        st.write("### 🚀 ATENDENDO")
        for _, v in vendedores[vendedores['status'] == 'Atendendo'].iterrows():
            st.markdown("<div class='monday-card'>", unsafe_allow_html=True)
            st.write(f"VENDEDOR: **{v['nome'].upper()}**")
            res = st.selectbox("**RESULTADO**", ["Sucesso", "Não convertido", "Troca"], key=f"r_{v['id']}")
            vlr, it, mot = 0.0, 0, res
            if res == "Sucesso":
                vlr = st.number_input("R$:", min_value=0.0, key=f"v_{v['id']}")
                it = st.number_input("Itens:", min_value=1, step=1, key=f"i_{v['id']}")
            elif res == "Não convertido":
                mot = st.selectbox("Motivo:", ["Preço", "Tamanho", "Só olhando"], key=f"m_{v['id']}")
            if st.button("GRAVAR ATENDIMENTO", key=f"ff_{v['id']}", type="primary", use_container_width=True):
                run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, mot, vlr, it, get_now().isoformat()))
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with c_p:
        st.write("### 💤 FORA DA LOJA")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown("<div class='monday-card'>", unsafe_allow_html=True)
            st.write(f"👤 **{v['nome'].upper()}**")
            if st.button(f"ENTRAR NA FILA", key=f"ret_{v['id']}", type="primary", use_container_width=True):
                run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Entrada", "Entrou", 0.0, 0, get_now().isoformat()))
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown("<div class='monday-card'>", unsafe_allow_html=True)
    st.write("### ⚙️ CONFIGURAÇÕES")
    nm = st.number_input("**Meta da Loja (R$):**", value=float(meta_val))
    if st.button("ATUALIZAR META", type="primary"):
        run_db("UPDATE config SET valor=? WHERE chave='meta_loja'", (nm,))
        st.rerun()
    st.divider()
    with st.form("add_v"):
        nn = st.text_input("**NOME DO NOVO VENDEDOR**")
        if st.form_submit_button("CADASTRAR", type="primary"):
            run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (nn, nn.lower(), 'Fora', 0)); st.rerun()
    equipe = run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True)
    for _, r in equipe.iterrows():
        c1, c2 = st.columns([4,1])
        c1.write(f"**👤 {r['nome'].upper()}**")
        if c2.button("X", key=f"rm_{r['id']}"): run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
