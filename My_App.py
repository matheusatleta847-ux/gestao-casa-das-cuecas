import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date, time
import plotly.express as px
import io

# --- 1. CONFIGURAÇÃO E CSS (DESIGN DASHBOARD MODERNO) ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide")

st.markdown("""
    <style>
    /* Forçar Fundo Cinza Claro e Texto Escuro */
    .stApp { background-color: #F8F9FB !important; }
    h1, h2, h3, p, span, label, .stMarkdown { color: #2C3E50 !important; }

    /* Cartões Estilo Widget */
    .premium-card {
        background-color: #FFFFFF !important;
        padding: 22px;
        border-radius: 14px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
        border: 1px solid #E0E4E8;
    }

    /* Meta e Faturamento */
    .meta-valor {
        font-size: 34px;
        font-weight: 800;
        color: #007BFF !important;
        margin: 10px 0;
    }

    /* Vendedor na Fila */
    .vendedor-fila-box {
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 12px;
        background-color: #FFFFFF !important;
        border: 1px solid #E0E4E8;
        transition: transform 0.2s;
    }
    .primeiro-da-fila {
        background-color: #EBFBEE !important;
        border: 2px solid #2ECC71 !important;
    }

    /* Botões Modernos */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        height: 40px;
        border: none !important;
    }
    
    /* Botão ATENDER (Azul) */
    div[data-testid="stVerticalBlock"] > div:nth-child(1) button[key^="at_"] {
        background-color: #007BFF !important;
        color: white !important;
    }
    
    /* Inputs */
    .stNumberInput input, .stSelectbox div {
        background-color: #FDFDFD !important;
        color: #2C3E50 !important;
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
    with st.columns([1,1.2,1])[1]:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        st.title("🔐 Login Elite")
        u, p = st.text_input("Usuário").lower(), st.text_input("Senha", type="password")
        if st.button("Entrar", type="primary", use_container_width=True):
            if u == "admin" and p == "admin123": 
                st.session_state.user = {"nome":"Admin", "role":"admin"}
                st.rerun()
            else: st.error("Acesso negado")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- 4. TABS ---
tab1, tab2, tab3 = st.tabs(["🛒 OPERAÇÃO", "📈 DESEMPENHO", "⚙️ CONFIGURAÇÕES"])

with tab1:
    meta_res = run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True)
    meta_loja = meta_res.iloc[0,0] if not meta_res.empty else 5000.0
    
    hoje_dt = get_now().strftime('%Y-%m-%d')
    df_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{hoje_dt}%'", is_select=True)
    fat_h = df_hoje[df_hoje['evento']=='Sucesso']['valor'].sum() if not df_hoje.empty else 0
    
    # Widget de Meta
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.write("🏆 **Faturamento Hoje**")
    st.markdown(f"<div class='meta-valor'>R$ {fat_h:,.2f} <span style='font-size:18px; color:#7F8C8D; font-weight:400;'>de R$ {meta_loja:,.2f}</span></div>", unsafe_allow_html=True)
    st.progress(min(fat_h/meta_loja, 1.0) if meta_loja > 0 else 0.0)
    st.markdown("</div>", unsafe_allow_html=True)

    col_f, col_a, col_p = st.columns(3)
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)

    with col_f:
        st.write("### ⏳ Fila de Vez")
        fila = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        if fila.empty: st.info("Ninguém na fila. Atendentes precisam entrar na loja.")
        for idx, v in fila.iterrows():
            is_1 = (idx == 0)
            cl_primeiro = "primeiro-da-fila" if is_1 else ""
            
            st.markdown(f"<div class='vendedor-fila-box {cl_primeiro}'>", unsafe_allow_html=True)
            st.markdown(f"**{v['nome'].upper()}**")
            
            b_cols = st.columns([1.2, 1, 1])
            
            if is_1:
                if b_cols[0].button("▶️ ATENDER", key=f"at_{v['id']}", type="primary"):
                    run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()
            else:
                if b_cols[0].button("⚡ FURAR", key=f"fu_{v['id']}"):
                    st.session_state[f"fura_{v['id']}"] = True
            
            if b_cols[1].button("☕ SAIR", key=f"ps_{v['id']}"):
                st.session_state[f"pausa_{v['id']}"] = True

            # Form Fura-Fila
            if st.session_state.get(f"fura_{v['id']}", False):
                mot_f = st.selectbox("Justificativa:", ["Cliente Voltou", "Específico", "Finalização", "Troca"], key=f"sel_f_{v['id']}")
                if st.button("Confirmar", key=f"ok_f_{v['id']}"):
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Fura-Fila", mot_f, 0.0, 0, get_now().isoformat()))
                    run_db("UPDATE usuarios SET status='Atendendo', ordem=? WHERE id=?", (get_min_ordem(), v['id']))
                    st.session_state[f"fura_{v['id']}"] = False; st.rerun()

            # Form Saída
            if st.session_state.get(f"pausa_{v['id']}", False):
                mot_p = st.selectbox("Motivo Saída:", ["Almoço", "Feedback", "Banheiro", "Café", "Fim de Turno"], key=f"sel_p_{v['id']}")
                if st.button("Sair", key=f"ok_p_{v['id']}"):
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Saída", mot_p, 0.0, 0, get_now().isoformat()))
                    run_db("UPDATE usuarios SET status='Fora', ordem=0 WHERE id=?", (v['id'],))
                    st.session_state[f"pausa_{v['id']}"] = False; st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with col_a:
        st.write("### 🚀 Atendendo")
        for _, v in vendedores[vendedores['status'] == 'Atendendo'].iterrows():
            st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
            st.write(f"Vendedor: **{v['nome']}**")
            res = st.selectbox("Resultado", ["Sucesso", "Não convertido", "Troca"], key=f"r_{v['id']}")
            vlr, it, mot = 0.0, 0, res
            if res == "Sucesso":
                vlr = st.number_input("R$:", min_value=0.0, key=f"v_{v['id']}")
                it = st.number_input("Itens:", min_value=1, step=1, key=f"i_{v['id']}")
            elif res == "Não convertido":
                mot = st.selectbox("Motivo:", ["Preço", "Tamanho", "Só olhando"], key=f"m_{v['id']}")
            if st.button("Gravar", key=f"ff_{v['id']}", type="primary", use_container_width=True):
                run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, mot, vlr, it, get_now().isoformat()))
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with col_p:
        st.write("### 💤 Fora da Loja")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
            st.write(f"👤 **{v['nome']}**")
            if st.button(f"Entrar na Fila", key=f"ret_{v['id']}", type="primary", use_container_width=True):
                run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Entrada", "Entrou na Loja", 0.0, 0, get_now().isoformat()))
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.write("### 📊 Relatório e Ajustes")
    d_r = st.date_input("Filtrar Período:", value=(date.today() - timedelta(days=7), date.today()))
    if isinstance(d_r, tuple) and len(d_r) == 2:
        df_f = run_db("SELECT * FROM historico WHERE date(data) BETWEEN ? AND ?", (d_r[0].isoformat(), d_r[1].isoformat()), is_select=True)
        if not df_f.empty:
            df_ed = st.data_editor(df_f, use_container_width=True, hide_index=True)
            if st.button("💾 Salvar Alterações"):
                run_db("DELETE FROM historico WHERE date(data) BETWEEN ? AND ?", (d_r[0].isoformat(), d_r[1].isoformat()))
                for _, r in df_ed.iterrows():
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (r['vendedor'], r['evento'], r['motivo'], r['valor'], r['itens'], r['data']))
                st.success("Dados Atualizados!"); st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.write("### ⚙️ Gestão de Meta e Equipe")
    n_meta = st.number_input("Meta Diária (R$):", value=float(meta_loja), min_value=0.0)
    if st.button("💾 Salvar Nova Meta"):
        run_db("UPDATE config SET valor=? WHERE chave='meta_loja'", (n_meta,))
        st.success("Meta salva!"); st.rerun()
    
    st.divider()
    with st.form("add_v"):
        nn = st.text_input("Novo Vendedor")
        if st.form_submit_button("➕ Cadastrar"):
            run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (nn, nn.lower(), 'Fora', 0))
            st.rerun()
    
    equipe = run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True)
    for _, r in equipe.iterrows():
        c1, c2 = st.columns([4,1])
        c1.write(f"👤 {r['nome']}")
        if c2.button("🗑️", key=f"rm_{r['id']}"):
            run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
