import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date, time
import plotly.express as px
import io

# --- 1. CONFIGURAÇÃO E CSS AVANÇADO (DESIGN INSPIRADO NO MODELO) ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide")

st.markdown("""
    <style>
    /* Global Styles */
    .reportview-container { background-color: #F4F7F9; }
    .main { background-color: #F4F7F9; }
    h1, h2, h3 { color: #2C3E50; font-weight: 700 !important; }

    /* Estilo do Cartão Principal (Widget Style) */
    .premium-card {
        background-color: #FFFFFF;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
        border: 1px solid #E6E9EC;
    }

    /* Estilo da Meta e Progresso */
    .meta-container {
        text-align: center;
        margin-bottom: 25px;
    }
    .meta-valor {
        font-size: 36px;
        font-weight: 800;
        color: #2C3E50;
    }

    /* Estilo do Vendedor na Fila */
    .vendedor-fila-card {
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 12px;
        background-color: #F8F9FA;
        border: 1px solid #E6E9EC;
        transition: all 0.3s ease;
    }
    .primeiro-da-fila {
        background-color: #E8F8F1; /* Verde Pastel Suave igual ao modelo */
        border: 2px solid #2ECC71 !important;
    }
    .vendedor-nome {
        font-size: 18px;
        font-weight: 700;
        color: #2C3E50;
        margin-bottom: 10px;
    }

    /* Estilo dos Botões Modernos (Estilo Dashboard) */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        height: 42px;
        transition: all 0.2s ease;
        border: none;
    }
    /* Botão Primário (Azul Dashboard) */
    .stButton > button.st-emotion-cache-12w0qpk { 
        background-color: #007BFF; /* Azul Principal do modelo */
        color: white;
    }
    /* Botão Pausa (Vermelho Pastel) */
    .stButton > button[key^="ps_"] {
        background-color: #FADBD8; /* Vermelho Pastel Suave */
        color: #C0392B;
    }
    /* Botão Furar (Amarelo Pastel) */
    .stButton > button[key^="fu_"] {
        background-color: #FEF9E7; /* Amarelo Pastel Suave */
        color: #F39C12;
    }
    
    /* Outros Ajustes */
    .stProgress > div > div > div > div { background-color: #007BFF; } /* Cor da barra */
    </style>
""", unsafe_allow_html=True)

# --- 2. ENGINE DE DADOS ---
DB_NAME = 'sistema_elite_v52.db'

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
        if st.button("Entrar", type="primary"):
            if u == "admin" and p == "admin123": st.session_state.user = {"nome":"Admin", "role":"admin"}; st.rerun()
            else: st.error("Acesso negado")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

tab1, tab2, tab3 = st.tabs(["🛒 OPERAÇÃO", "📈 DESEMPENHO", "⚙️ CONFIGURAÇÕES"])

with tab1:
    meta_loja = run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0]
    hoje_dt = get_now().strftime('%Y-%m-%d')
    df_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{hoje_dt}%'", is_select=True)
    fat_h = df_hoje[df_hoje['evento']=='Sucesso']['valor'].sum() if not df_hoje.empty else 0
    
    # Header de Meta (Estilo "ARR Goal" do modelo)
    with st.container():
        st.markdown("<div class='premium-card meta-container'>", unsafe_allow_html=True)
        st.write("🏆 Meta Diária da Loja")
        st.markdown(f"<div class='meta-valor'>R$ {fat_h:,.2f} <span style='font-size:20px; color:#7F8C8D; font-weight:400;'>de R$ {meta_loja:,.2f}</span></div>", unsafe_allow_html=True)
        st.progress(min(fat_h/meta_loja, 1.0) if meta_loja > 0 else 0.0)
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    col_f, col_a, col_p = st.columns(3)
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)

    with col_f:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        st.write("### ⏳ Fila de Vez")
        fila = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        if fila.empty: st.info("Fila vazia.")
        for idx, v in fila.iterrows():
            is_1 = (idx == 0)
            cl = "vendedor-fila-card primeiro-da-fila" if is_1 else "vendedor-fila-card"
            
            with st.container():
                st.markdown(f"<div class='{cl}'>", unsafe_allow_html=True)
                st.markdown(f"<div class='vendedor-nome'>👤 {v['nome'].upper()}</div>", unsafe_allow_html=True)
                
                # Grupo de Botões Juntos (Estilo Ícones do modelo)
                b_cols = st.columns([1, 1, 1])
                
                if is_1:
                    if b_cols[0].button("▶️ Atender", key=f"at_{v['id']}", type="primary"):
                        run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()
                else:
                    if b_cols[0].button("⚡ Furar", key=f"fu_{v['id']}"):
                        st.session_state[f"fura_{v['id']}"] = True
                
                if b_cols[1].button("☕ Pausa", key=f"ps_{v['id']}"):
                    st.session_state[f"pausa_{v['id']}"] = True

                # Lógicas de Interface
                if st.session_state.get(f"fura_{v['id']}", False):
                    st.markdown("<div style='background:#FEF9E7; padding:10px; border-radius:8px; margin-top:10px;'>", unsafe_allow_html=True)
                    mot_f = st.selectbox("Justificativa:", ["Cliente Voltou", "Específico", "Finalização", "Troca"], key=f"sel_f_{v['id']}")
                    c1, c2 = st.columns(2)
                    if c1.button("Confirmar", key=f"ok_f_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Fura-Fila", mot_f, 0.0, 0, get_now().isoformat()))
                        run_db("UPDATE usuarios SET status='Atendendo', ordem=? WHERE id=?", (get_min_ordem(), v['id']))
                        st.session_state[f"fura_{v['id']}"] = False; st.rerun()
                    if c2.button("X", key=f"can_f_{v['id']}"): st.session_state[f"fura_{v['id']}"] = False; st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

                if st.session_state.get(f"pausa_{v['id']}", False):
                    st.markdown("<div style='background:#FADBD8; padding:10px; border-radius:8px; margin-top:10px;'>", unsafe_allow_html=True)
                    mot_p = st.selectbox("Motivo:", ["Almoço", "Feedback", "Banheiro", "Café"], key=f"sel_p_{v['id']}")
                    if c1.button("Sair", key=f"ok_p_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Saída", mot_p, 0.0, 0, get_now().isoformat()))
                        run_db("UPDATE usuarios SET status='Fora', ordem=0 WHERE id=?", (v['id'],))
                        st.session_state[f"pausa_{v['id']}"] = False; st.rerun()
                    if c2.button("X", key=f"can_p_{v['id']}"): st.session_state[f"pausa_{v['id']}"] = False; st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True) # Fecha card vendedor
        st.markdown("</div>", unsafe_allow_html=True) # Fecha card Fila

    with col_a:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        st.write("### 🚀 Atendendo")
        for _, v in vendedores[vendedores['status'] == 'Atendendo'].iterrows():
            with st.container(border=True):
                st.write(f"Vendedor: **{v['nome']}**")
                res = st.selectbox("Resultado", ["Sucesso", "Não convertido", "Troca"], key=f"r_{v['id']}")
                vlr, it, mot = 0.0, 0, res
                if res == "Sucesso":
                    vlr = st.number_input("R$:", min_value=0.0, key=f"v_{v['id']}")
                    it = st.number_input("Itens:", min_value=1, step=1, key=f"i_{v['id']}")
                elif res == "Não convertido":
                    mot = st.selectbox("Motivo:", ["Preço", "Tamanho", "Cor", "Só olhando"], key=f"m_{v['id']}")
                if st.button("Gravar", key=f"ff_{v['id']}", type="primary"):
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, mot, vlr, it, get_now().isoformat()))
                    run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col_p:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        st.write("### 💤 Fora da Loja")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            with st.container(border=True):
                st.write(f"👤 **{v['nome']}** (Pausado)")
                if st.button(f"Entrar", key=f"ret_{v['id']}", type="primary"):
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Entrada", "Entrou", 0.0, 0, get_now().isoformat()))
                    run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.write("### 📊 Relatórios de Consultoria")
    # ... (Aba de desempenho permanece igual para manter estabilidade, mas dentro do card)
    d_r = st.date_input("Filtrar Período:", value=(date.today() - timedelta(days=7), date.today()))
    if isinstance(d_r, tuple) and len(d_r) == 2:
        df_f = run_db("SELECT * FROM historico WHERE date(data) BETWEEN ? AND ?", (d_r[0].isoformat(), d_r[1].isoformat()), is_select=True)
        if not df_f.empty:
            df_ed = st.data_editor(df_f, num_rows="dynamic", hide_index=True)
            if st.button("💾 Salvar Alterações na Planilha"):
                run_db("DELETE FROM historico WHERE date(data) BETWEEN ? AND ?", (d_r[0].isoformat(), d_r[1].isoformat()))
                for _, r in df_ed.iterrows():
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (r['vendedor'], r['evento'], r['motivo'], r['valor'], r['itens'], r['data']))
                st.success("Sincronizado!"); st.rerun()
            towrite = io.BytesIO()
            df_f.to_excel(towrite, index=False, engine='xlsxwriter')
            st.download_button("📥 Baixar Excel", data=towrite.getvalue(), file_name="relatorio_cuecas.xlsx")
    st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.write("### ⚙️ Configurações")
    # ... (Aba de configurações permanece igual, mas dentro do card)
    n_meta = st.number_input("Nova Meta Diária:", value=float(meta_loja))
    if st.button("Salvar Meta"): run_db("UPDATE config SET valor=? WHERE chave='meta_loja'", (n_meta,)); st.rerun()
    st.divider()
    with st.form("add_v"):
        nn = st.text_input("Nome do Novo Vendedor")
        if st.form_submit_button("Cadastrar Novo"):
            run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (nn, nn.lower(), 'Fora', 0)); st.rerun()
    for _, r in run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True).iterrows():
        c1, c2 = st.columns([4,1])
        c1.write(f"👤 {r['nome']}")
        if c2.button("Remover", key=f"rm_{r['id']}"): run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
