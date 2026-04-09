import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date, time
import plotly.express as px
import io

# --- 1. CONFIGURAÇÃO E CSS (DESIGN MONDAY COM MENU INTEGRADO) ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;700;800&display=swap');
    
    /* FUNDO PRINCIPAL */
    .stApp { background-color: #F5F6F8 !important; }
    
    /* LIMPEZA TOTAL DO TOPO */
    header { visibility: hidden !important; height: 0px !important; }
    .block-container { padding-top: 1rem !important; }

    /* TEXTO GLOBAL */
    h1, h2, h3, p, span, label, .stMarkdown { 
        font-family: 'Figtree', sans-serif !important;
        color: #1E1F23 !important; 
    }

    /* CARTÃO ESTILO MONDAY */
    .monday-card-pro {
        background-color: #FFFFFF !important;
        padding: 22px;
        border-radius: 8px;
        border: 1px solid #D0D4E4;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    /* ESTILO DO NOVO MENU (SUBSTITUTO DAS TABS) */
    .nav-container {
        display: flex;
        gap: 10px;
        background-color: #FFFFFF;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #D0D4E4;
        margin-bottom: 25px;
    }

    /* BOTÕES GLOBAIS */
    .stButton > button {
        border-radius: 4px !important;
        font-weight: 700 !important;
        height: 40px;
        border: 1px solid #D0D4E4 !important;
        background-color: #FFFFFF !important;
        transition: all 0.2s;
        text-transform: uppercase;
        font-size: 12px;
    }

    /* BOTÃO AZUL GLASS (IDENTIDADE) */
    .stButton > button[kind="primary"] {
        background-color: #E8F4FF !important;
        color: #0073EA !important;
        border: 1px solid #A2CFFF !important;
        border-left: 8px solid #0073EA !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        background-color: #D1E9FF !important;
        border-color: #0073EA !important;
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

# --- 3. CONTROLE DE NAVEGAÇÃO (SUBSTITUI TABS) ---
if 'pagina' not in st.session_state: st.session_state.pagina = "OPERAÇÃO"

# Menu Superior customizado
st.markdown("<div class='nav-container'>", unsafe_allow_html=True)
c_nav1, c_nav2, c_nav3, c_nav_extra = st.columns([1, 1, 1, 3])

with c_nav1:
    if st.button("📋 OPERAÇÃO", type="primary" if st.session_state.pagina == "OPERAÇÃO" else "secondary", use_container_width=True):
        st.session_state.pagina = "OPERAÇÃO"; st.rerun()
with c_nav2:
    if st.button("📊 DESEMPENHO", type="primary" if st.session_state.pagina == "DESEMPENHO" else "secondary", use_container_width=True):
        st.session_state.pagina = "DESEMPENHO"; st.rerun()
with c_nav3:
    if st.button("⚙️ CONFIGURAÇÃO", type="primary" if st.session_state.pagina == "CONFIGURAÇÃO" else "secondary", use_container_width=True):
        st.session_state.pagina = "CONFIGURAÇÃO"; st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

# --- 4. CONTEÚDO DAS PÁGINAS ---

if st.session_state.pagina == "OPERAÇÃO":
    meta_val = run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0]
    df_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{get_now().strftime('%Y-%m-%d')}%'", is_select=True)
    
    vendas_sucesso = df_hoje[df_hoje['evento'] == 'Sucesso']
    fat_h = vendas_sucesso['valor'].sum() if not vendas_sucesso.empty else 0.0
    falta_meta = max(0, meta_val - fat_h)
    pa_hoje = vendas_sucesso['itens'].sum() / len(vendas_sucesso) if not vendas_sucesso.empty else 0.0
    tm_hoje = fat_h / len(vendas_sucesso) if not vendas_sucesso.empty else 0.0

    st.markdown(f"""
        <div class='monday-card-pro'>
            <div style='display: flex; justify-content: space-around; align-items: center;'>
                <div style='text-align: center; border-right: 1px solid #E6E9EF; flex: 2;'>
                    <div style='font-weight:700; color:#676879; font-size:12px; text-transform:uppercase;'>🎯 Faturamento Hoje</div>
                    <div style='font-size: 30px; font-weight: 800; color: #0073EA;'>R$ {fat_h:,.2f}</div>
                    <div style='font-size: 14px; font-weight:700; color:#E44258;'>Falta: R$ {falta_meta:,.2f}</div>
                </div>
                <div style='text-align: center; border-right: 1px solid #E6E9EF; flex: 1;'>
                    <div style='font-weight:700; color:#676879; font-size:12px; text-transform:uppercase;'>📦 P.A.</div>
                    <div style='font-size: 22px; font-weight: 800;'>{pa_hoje:.2f}</div>
                </div>
                <div style='text-align: center; flex: 1;'>
                    <div style='font-weight:700; color:#676879; font-size:12px; text-transform:uppercase;'>🎫 Ticket Médio</div>
                    <div style='font-size: 22px; font-weight: 800;'>R$ {tm_hoje:,.0f}</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    st.progress(min(fat_h/meta_val, 1.0) if meta_val > 0 else 0.0)

    st.divider()
    c_f, c_a, c_p = st.columns(3)
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)

    with c_f:
        st.write("### ⏳ FILA DE VEZ")
        fila = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for idx, v in fila.iterrows():
            is_1 = (idx == 0)
            cl = "border-left: 8px solid #00C875; background-color: #F0FFF4;" if is_1 else ""
            st.markdown(f"<div class='monday-card-pro' style='padding:15px; {cl}'><b>{v['nome'].upper()}</b>", unsafe_allow_html=True)
            
            b_cols = st.columns([1, 1, 1])
            if is_1:
                if b_cols[0].button("ATENDER", key=f"at_{v['id']}", type="primary"):
                    run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()
            else:
                if b_cols[0].button("FURAR", key=f"fu_{v['id']}", type="primary"):
                    st.session_state[f"f_{v['id']}"] = True
            
            if b_cols[1].button("SAIR", key=f"ps_{v['id']}"):
                st.session_state[f"p_{v['id']}"] = True

            if st.session_state.get(f"f_{v['id']}", False):
                mot_f = st.selectbox("Justificativa:", ["Cliente Voltou", "Específico", "Troca"], key=f"s_f_{v['id']}")
                if st.button("Confirmar Furada", key=f"ok_f_{v['id']}", type="primary"):
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Fura-Fila", mot_f, 0.0, 0, get_now().isoformat()))
                    run_db("UPDATE usuarios SET status='Atendendo', ordem=? WHERE id=?", (get_min_ordem(), v['id']))
                    st.session_state[f"f_{v['id']}"] = False; st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with c_a:
        st.write("### 🚀 ATENDENDO")
        for _, v in vendedores[vendedores['status'] == 'Atendendo'].iterrows():
            st.markdown("<div class='monday-card-pro'>", unsafe_allow_html=True)
            st.write(f"VENDEDOR: **{v['nome'].upper()}**")
            res = st.selectbox("Resultado", ["Sucesso", "Não convertido", "Troca"], key=f"r_{v['id']}")
            vlr, it, mot = 0.0, 0, res
            if res == "Sucesso":
                vlr = st.number_input("R$:", min_value=0.0, key=f"v_{v['id']}")
                it = st.number_input("Peças:", min_value=1, step=1, key=f"i_{v['id']}")
            elif res == "Não convertido":
                mot = st.selectbox("Motivo:", ["Preço", "Tamanho", "Cor", "Só olhando"], key=f"m_{v['id']}")
            if st.button("GRAVAR", key=f"ff_{v['id']}", type="primary", use_container_width=True):
                run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, mot, vlr, it, get_now().isoformat()))
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with c_p:
        st.write("### 💤 FORA")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown("<div class='monday-card-pro'>", unsafe_allow_html=True)
            st.write(f"👤 **{v['nome'].upper()}**")
            if st.button(f"ENTRAR", key=f"ret_{v['id']}", type="primary", use_container_width=True):
                run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Entrada", "Entrou", 0.0, 0, get_now().isoformat()))
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.pagina == "DESEMPENHO":
    st.markdown("<div class='monday-card-pro'>", unsafe_allow_html=True)
    st.write("### 📈 DESEMPENHO E HISTÓRICO")
    d_r = st.date_input("Filtrar Período:", value=(date.today() - timedelta(days=7), date.today()))
    if isinstance(d_r, tuple) and len(d_r) == 2:
        df_f = run_db("SELECT * FROM historico WHERE date(data) BETWEEN ? AND ?", (d_r[0].isoformat(), d_r[1].isoformat()), is_select=True)
        if not df_f.empty:
            df_ed = st.data_editor(df_f, use_container_width=True, hide_index=True)
            if st.button("SALVAR ALTERAÇÕES", type="primary"):
                run_db("DELETE FROM historico WHERE date(data) BETWEEN ? AND ?", (d_r[0].isoformat(), d_r[1].isoformat()))
                for _, r in df_ed.iterrows():
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (r['vendedor'], r['evento'], r['motivo'], r['valor'], r['itens'], r['data']))
                st.success("Dados atualizados!"); st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.pagina == "CONFIGURAÇÃO":
    meta_val = run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0]
    st.markdown("<div class='monday-card-pro'>", unsafe_allow_html=True)
    st.write("### ⚙️ CONFIGURAÇÕES DA LOJA")
    nm = st.number_input("Meta Diária (R$):", value=float(meta_val))
    if st.button("SALVAR META", key="btn_meta_fin", type="primary"):
        run_db("UPDATE config SET valor=? WHERE chave='meta_loja'", (nm,))
        st.success("Meta salva!"); st.rerun()
    
    st.divider()
    st.write("#### 👤 GERENCIAR EQUIPE")
    nn = st.text_input("NOME DO VENDEDOR")
    if st.button("CADASTRAR VENDEDOR", key="btn_add_fin", type="primary"):
        if nn:
            run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (nn, nn.lower(), 'Fora', 0))
            st.rerun()
    
    st.divider()
    equipe = run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True)
    for _, r in equipe.iterrows():
        c1, c2 = st.columns([4,1])
        c1.write(f"👤 **{r['nome'].upper()}**")
        if c2.button("X", key=f"rm_{r['id']}"):
            run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
