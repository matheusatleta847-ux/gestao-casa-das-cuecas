import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÕES DA PÁGINA & DESIGN PREMIUM ---
st.set_page_config(page_title="PRO-Vez | Casa das Cuecas", layout="wide", page_icon="🛍️")

# Injeção de CSS para transformar o visual do Streamlit
st.markdown("""
    <style>
    /* Importando fonte Google */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F8FAFC; }

    /* Estilização dos Cards de KPI */
    .metric-card {
        background: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-top: 4px solid #1E293B; margin-bottom: 20px;
    }
    .metric-title { color: #64748B; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-value { color: #1E293B; font-size: 24px; font-weight: 700; margin-top: 5px; }

    /* Estilização da Fila */
    .vendedor-box {
        background: white; padding: 12px 16px; border-radius: 8px;
        border: 1px solid #E2E8F0; margin-bottom: 8px;
        display: flex; justify-content: space-between; align-items: center;
    }
    .primeiro-vez { background: #F0FDF4; border: 1px solid #BBF7D0; }
    .status-badge { font-size: 11px; padding: 2px 8px; border-radius: 12px; font-weight: 600; }
    
    /* Botões Customizados */
    .stButton>button {
        border-radius: 8px; font-weight: 600; padding: 0.5rem 1rem;
        transition: all 0.2s ease; width: 100%;
    }
    .stButton>button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE DADOS ---
DB_NAME = 'lista_v3_pro.db'

def run_db(query, params=(), is_select=False):
    with sqlite3.connect(DB_NAME) as conn:
        if is_select: return pd.read_sql(query, conn, params=params)
        conn.execute(query, params); conn.commit()

def init_db():
    run_db('''CREATE TABLE IF NOT EXISTS usuarios 
              (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, ordem INTEGER, h_entrada TEXT)''')
    run_db('''CREATE TABLE IF NOT EXISTS historico 
              (id INTEGER PRIMARY KEY, vendedor TEXT, evento TEXT, motivo TEXT, valor REAL, itens INTEGER, data TEXT)''')

init_db()

# --- 3. CONTROLE DE ACESSO ---
if 'user' not in st.session_state: st.session_state.user = None

if not st.session_state.user:
    st.markdown("<h2 style='text-align: center; color: #1E293B;'>🏢 Acesso Restrito</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        with st.form("login_form"):
            u = st.text_input("Usuário:").strip().lower()
            p = st.text_input("Senha (Admin):", type="password")
            if st.form_submit_button("Entrar"):
                if u == "admin" and p == "admin@123":
                    st.session_state.user = {"nome": "Admin", "is_admin": True}
                    st.rerun()
                else:
                    res = run_db("SELECT * FROM usuarios WHERE login = ?", (u,), True)
                    if not res.empty:
                        st.session_state.user = {"nome": res.iloc[0]['nome'], "is_admin": False}
                        st.rerun()
    st.stop()

# --- 4. HEADER & KPIs PROFISSIONAIS ---
st.markdown(f"""
    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;'>
        <h1 style='color: #1E293B; font-size: 28px;'>PRO-Vez <span style='color: #64748B; font-weight: 400;'>| {st.session_state.user['nome']}</span></h1>
        <div style='color: #64748B;'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
    </div>
""", unsafe_allow_html=True)

# Cálculo de Metas Mensais (BI)
dados_mes = run_db("SELECT * FROM historico WHERE data >= ?", ((datetime.now() - timedelta(days=30)).isoformat(),), True)
faturamento = dados_mes['valor'].sum()
atendimentos = len(dados_mes)
vendas_sucesso = len(dados_mes[dados_mes['evento'] == 'Sucesso'])
taxa_conv = (vendas_sucesso / atendimentos * 100) if atendimentos > 0 else 0
ticket_medio = (faturamento / vendas_sucesso) if vendas_sucesso > 0 else 0

k1, k2, k3, k4 = st.columns(4)
for col, title, val, prefix in zip([k1, k2, k3, k4], 
                                 ["Faturamento Mensal", "Taxa Conversão", "Ticket Médio", "Total Atendimentos"],
                                 [faturamento, taxa_conv, ticket_medio, atendimentos],
                                 ["R$ ", "", "R$ ", ""]):
    with col:
        st.markdown(f"""<div class="metric-card"><div class="metric-title">{title}</div>
                    <div class="metric-value">{prefix}{val:,.2f if isinstance(val, float) else val}</div></div>""", unsafe_allow_html=True)

# --- 5. TABS PRINCIPAIS ---
t1, t2, t3 = st.tabs(["📋 FILA DE ATENDIMENTO", "📊 PERFORMANCE & RANKING", "⚙️ GERENCIAMENTO"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_esp, c_atend, c_fora = st.columns(3)

    with c_esp:
        st.markdown("### ⏳ Esperando a Vez")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            is_primeiro = (i == 0)
            classe = "vendedor-box primeiro-vez" if is_primeiro else "vendedor-box"
            st.markdown(f"<div class='{classe}'><span><b>{v['nome']}</b></span> <span class='status-badge' style='background:#BBF7D0; color:#166534;'>{i+1}º DA VEZ</span></div>", unsafe_allow_html=True)
            
            if st.button("🚀 INICIAR VEZ", key=f"start_{v['id']}"):
                if not is_primeiro:
                    st.session_state[f"furo_{v['id']}"] = True
                else:
                    run_db("UPDATE usuarios SET status='Atendendo', h_entrada=? WHERE id=?", (datetime.now().isoformat(), v['id']))
                    st.rerun()
            
            # Modal de Justificativa para Furar Fila
            if st.session_state.get(f"furo_{v['id']}", False):
                with st.expander("⚠️ Por que está saindo da fila de espera?", expanded=True):
                    mot = st.radio("Justificativa:", ["Preferência do cliente", "Operacional", "Retorno cliente"], key=f"mot_{v['id']}")
                    if st.button("Confirmar Atendimento", key=f"conf_{v['id']}"):
                        run_db("UPDATE usuarios SET status='Atendendo', h_entrada=? WHERE id=?", (datetime.now().isoformat(), v['id']))
                        run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", (v['nome'], "Furo de Fila", mot, datetime.now().isoformat()))
                        st.session_state[f"furo_{v['id']}"] = False
                        st.rerun()

    with c_atend:
        st.markdown("### 🚀 Em Atendimento")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container(border=True):
                st.write(f"**{v['nome']}**")
                if st.button("🏁 FINALIZAR", key=f"fin_{v['id']}", type="primary"):
                    st.session_state[f"modal_fin_{v['id']}"] = True
            
            if st.session_state.get(f"modal_fin_{v['id']}", False):
                with st.expander("📝 Detalhes do Atendimento", expanded=True):
                    res = st.selectbox("Resultado:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    vlr, pcas = 0.0, 1
                    if res == "Sucesso":
                        vlr = st.number_input("Valor da Venda:", min_value=0.0)
                        pcas = st.number_input("Peças:", min_value=1)
                    
                    if st.button("Salvar e Ir para Fim da Fila", key=f"save_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, valor, itens, data) VALUES (?,?,?,?,?)",
                              (v['nome'], res, vlr, pcas, datetime.now().isoformat()))
                        # Lógica de Fila: Max ordem + 1
                        res_max = run_db("SELECT MAX(ordem) FROM usuarios", is_select=True).iloc[0,0] or 0
                        run_db("UPDATE usuarios SET status='Esperando', ordem=?, h_entrada=NULL WHERE id=?", (res_max + 1, v['id']))
                        st.session_state[f"modal_fin_{v['id']}"] = False
                        st.rerun()

    with c_fora:
        st.markdown("### 💤 Fora da Loja")
        fora = vendedores[vendedores['status'] == 'Fora']
        for _, v in fora.iterrows():
            if st.button(f"RETORNAR: {v['nome']}", key=f"ret_{v['id']}"):
                res_max = run_db("SELECT MAX(ordem) FROM usuarios", is_select=True).iloc[0,0] or 0
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (res_max + 1, v['id']))
                st.rerun()

with t2:
    st.subheader("🏆 Ranking de Vendas")
    ranking = run_db("SELECT vendedor, SUM(valor) as total FROM historico GROUP BY vendedor ORDER BY total DESC", is_select=True)
    if not ranking.empty:
        st.bar_chart(ranking.set_index('vendedor'))
    else: st.info("Sem dados.")

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("Gerenciar Equipe")
        novo = st.text_input("Nome Completo do Vendedor:")
        if st.button("Cadastrar Novo"):
            if novo:
                login = novo.lower().replace(" ", ".")
                run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (novo.title(), login, 'Fora', 99))
                st.success(f"Vendedor {novo} adicionado! Login: {login}")
        
        st.divider()
        if st.button("🔥 RESET TOTAL DO SISTEMA"):
            run_db("DELETE FROM usuarios"); run_db("DELETE FROM historico")
            st.rerun()
    else: st.warning("Acesso restrito.")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3081/3081559.png", width=80)
    if st.button("Sair / Trocar Usuário"):
        st.session_state.user = None
        st.rerun()
