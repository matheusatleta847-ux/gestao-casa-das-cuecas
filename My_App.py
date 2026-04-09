import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import io

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

    /* CARD MONDAY UNIFICADO */
    .monday-card-pro {
        background-color: #FFFFFF !important;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #D0D4E4;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    /* MENU DE NAVEGAÇÃO SUPERIOR */
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

    /* BOTÕES GLOBAIS */
    .stButton > button {
        border-radius: 4px !important;
        font-weight: 800 !important;
        height: 40px;
        border: 1px solid #D0D4E4 !important;
        background-color: #FFFFFF !important;
        transition: all 0.2s;
        text-transform: uppercase;
        font-size: 12px;
    }

    /* BOTÃO AZUL GLASS */
    .stButton > button[kind="primary"] {
        background-color: #E8F4FF !important;
        color: #0073EA !important;
        border: 1px solid #A2CFFF !important;
        border-left: 8px solid #0073EA !important;
    }
    
    /* BOTÃO DE LOGOUT (VERMELHO SUAVE) */
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
        margin-top: 10px;
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
    run_db("CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor REAL)")
    run_db("INSERT OR IGNORE INTO config VALUES ('meta_loja', 5000.0)")

init_db()

# --- 3. GESTÃO DE ACESSO ---
if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    with st.columns([1,1,1])[1]:
        st.markdown("<div style='margin-top:100px;' class='monday-card-pro'>", unsafe_allow_html=True)
        st.title("PRO-Vez Elite")
        u = st.text_input("Usuário").lower()
        p = st.text_input("Senha", type="password")
        if st.button("ENTRAR NO PAINEL", type="primary", use_container_width=True):
            if u == "admin" and p == "admin123":
                st.session_state.logado = True
                st.rerun()
            else: st.error("Acesso negado.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- 4. NAVEGAÇÃO E LOGOUT ---
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
    if st.button("🚪 SAIR", use_container_width=True):
        st.session_state.logado = False
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# --- 5. FUNÇÕES AUXILIARES ---
def get_now(): return datetime.now() - timedelta(hours=3)
def get_max_ordem(): 
    res = run_db("SELECT MAX(ordem) FROM usuarios", is_select=True).iloc[0,0]
    return (int(res) if res else 0) + 1
def get_min_ordem(): 
    res = run_db("SELECT MIN(ordem) FROM usuarios WHERE status='Esperando'", is_select=True).iloc[0,0]
    return (int(res) if res else 0) - 1

# --- 6. CONTEÚDO ---
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
            if b2.button("SAIR", key=f"ps_{v['id']}", use_container_width=True):
                st.session_state[f"p_{v['id']}"] = True
            
            if st.session_state.get(f"f_{v['id']}", False):
                mot = st.selectbox("Motivo:", ["Cliente Voltou", "Troca"], key=f"sf_{v['id']}")
                if st.button("Confirmar Furada", key=f"okf_{v['id']}", type="primary"):
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Fura-Fila", mot, 0, 0, get_now().isoformat()))
                    run_db("UPDATE usuarios SET status='Atendendo', ordem=? WHERE id=?", (get_min_ordem(), v['id'])); st.rerun()
            
            if st.session_state.get(f"p_{v['id']}", False):
                mot_p = st.selectbox("Motivo Saída:", ["Almoço", "Café", "Banheiro"], key=f"sp_{v['id']}")
                if st.button("Sair", key=f"okp_{v['id']}", type="primary"):
                    run_db("UPDATE usuarios SET status='Fora', ordem=0, motivo_pausa=? WHERE id=?", (mot_p, v['id'])); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with c_aten:
        st.write("### 🚀 ATENDENDO")
        for _, v in vendedores[vendedores['status'] == 'Atendendo'].iterrows():
            st.markdown("<div class='monday-card-pro' style='border-left: 8px solid #0073EA;'><b>" + v['nome'].upper() + "</b>", unsafe_allow_html=True)
            res = st.selectbox("Resultado", ["Sucesso", "Não convertido"], key=f"res_{v['id']}")
            if res == "Sucesso":
                vlr = st.number_input("R$:", min_value=0.0, key=f"v_{v['id']}")
                it = st.number_input("Peças:", min_value=1, step=1, key=f"i_{v['id']}")
            if st.button("GRAVAR ATENDIMENTO", key=f"gr_{v['id']}", type="primary", use_container_width=True):
                run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, "Venda", vlr if res=="Sucesso" else 0, it if res=="Sucesso" else 0, get_now().isoformat()))
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with c_fora:
        st.write("### 💤 FORA")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown("<div class='monday-card-pro'><b>" + v['nome'].upper() + "</b>", unsafe_allow_html=True)
            if st.button("VOLTAR P/ FILA", key=f"ret_{v['id']}", type="primary", use_container_width=True):
                run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.pagina == "DESEMPENHO":
    st.markdown("<div class='monday-card-pro'>### 📈 HISTÓRICO</div>", unsafe_allow_html=True)
    # Lógica de edição de dados (simplificada)
    df_f = run_db("SELECT * FROM historico ORDER BY data DESC LIMIT 100", is_select=True)
    st.dataframe(df_f, use_container_width=True)

elif st.session_state.pagina == "CONFIGURAÇÃO":
    st.markdown("<div class='monday-card-pro'>### ⚙️ EQUIPE</div>", unsafe_allow_html=True)
    nn = st.text_input("Novo Vendedor")
    if st.button("CADASTRAR", type="primary"):
        if nn: run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (nn, nn.lower(), 'Fora', 0)); st.rerun()
    
    st.divider()
    st.write("#### 🚨 RESET")
    st.markdown("<div class='danger-box'>", unsafe_allow_html=True)
    pwd = st.text_input("Senha Admin", type="password")
    if st.button("LIMPAR TUDO", type="primary"):
        if pwd == "admin123": run_db("DELETE FROM historico"); st.success("Zerado!"); st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
