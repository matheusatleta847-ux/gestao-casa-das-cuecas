import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÕES DA PÁGINA & DESIGN PREMIUM ---
st.set_page_config(page_title="PRO-Vez | Casa das Cuecas", layout="wide", page_icon="🛍️")

# Injeção de CSS para o visual moderno (SaaS Style)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F8FAFC; }

    /* Cards de KPI Estilizados */
    .metric-card {
        background: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-top: 4px solid #1E293B; margin-bottom: 20px;
    }
    .metric-title { color: #64748B; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-value { color: #1E293B; font-size: 26px; font-weight: 700; margin-top: 5px; }

    /* Fila de Atendimento */
    .vendedor-box {
        background: white; padding: 14px 18px; border-radius: 10px;
        border: 1px solid #E2E8F0; margin-bottom: 10px;
        display: flex; justify-content: space-between; align-items: center;
    }
    .primeiro-vez { background: #F0FDF4; border: 2px solid #BBF7D0; }
    .status-badge { font-size: 11px; padding: 3px 10px; border-radius: 12px; font-weight: 600; }
    
    /* Botões */
    .stButton>button {
        border-radius: 8px; font-weight: 600; padding: 0.6rem;
        transition: all 0.2s ease; width: 100%;
    }
    .stButton>button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE BANCO DE DADOS ---
DB_NAME = 'lista_v4_final.db'

def run_db(query, params=(), is_select=False):
    with sqlite3.connect(DB_NAME) as conn:
        if is_select:
            return pd.read_sql(query, conn, params=params)
        conn.execute(query, params)
        conn.commit()

def init_db():
    run_db('''CREATE TABLE IF NOT EXISTS usuarios 
              (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, ordem INTEGER, h_entrada TEXT)''')
    run_db('''CREATE TABLE IF NOT EXISTS historico 
              (id INTEGER PRIMARY KEY, vendedor TEXT, evento TEXT, motivo TEXT, valor REAL, itens INTEGER, data TEXT)''')

init_db()

# --- 3. GESTÃO DE ACESSO ---
if 'user' not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.markdown("<h2 style='text-align: center; color: #1E293B; margin-top: 50px;'>🏢 Acesso PRO-Vez</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.form("login_form"):
            u = st.text_input("Usuário:").strip().lower()
            p = st.text_input("Senha (Admin):", type="password")
            if st.form_submit_button("Entrar no Painel", use_container_width=True):
                if u == "admin" and p == "admin@123":
                    st.session_state.user = {"nome": "Administrador", "is_admin": True}
                    st.rerun()
                else:
                    res = run_db("SELECT * FROM usuarios WHERE login = ?", (u,), True)
                    if not res.empty:
                        st.session_state.user = {"nome": res.iloc[0]['nome'], "is_admin": False}
                        st.rerun()
                    else:
                        st.error("Login não identificado.")
    st.stop()

# --- 4. KPIs PROFISSIONAIS (Cálculos e Formatação Corrigida) ---
dados_mes = run_db("SELECT * FROM historico WHERE data >= ?", 
                   ((datetime.now() - timedelta(days=30)).isoformat(),), True)

# Cálculos seguros
faturamento = dados_mes['valor'].sum() if not dados_mes.empty else 0
atendimentos = len(dados_mes)
vendas_sucesso = len(dados_mes[dados_mes['evento'] == 'Sucesso'])
taxa_conv = (vendas_sucesso / atendimentos * 100) if atendimentos > 0 else 0
ticket_medio = (faturamento / vendas_sucesso) if vendas_sucesso > 0 else 0

k1, k2, k3, k4 = st.columns(4)
titulos = ["Faturamento Mensal", "Taxa Conversão", "Ticket Médio", "Total Atendimentos"]
valores = [faturamento, taxa_conv, ticket_medio, atendimentos]
pre = ["R$ ", "", "R$ ", ""]
suf = ["", "%", "", ""]

for col, t, v, p, s in zip([k1, k2, k3, k4], titulos, valores, pre, suf):
    val_fmt = f"{v:,.2f}" if isinstance(v, (float, int)) and v > 0 else "0.00"
    if t == "Total Atendimentos": val_fmt = str(int(v)) # Sem decimais para contagem
    
    with col:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">{t}</div>
                <div class="metric-value">{p}{val_fmt}{s}</div>
            </div>
        """, unsafe_allow_html=True)

# --- 5. OPERACIONAL & ABAS ---
st.markdown("---")
t1, t2, t3 = st.tabs(["📋 FILA DE ATENDIMENTO", "🏆 PERFORMANCE & RANKING", "⚙️ CONFIGURAÇÕES"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_esp, c_atend, c_fora = st.columns(3)

    with c_esp:
        st.subheader("⏳ Esperando a Vez")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            is_primeiro = (i == 0)
            classe = "vendedor-box primeiro-vez" if is_primeiro else "vendedor-box"
            st.markdown(f"""
                <div class='{classe}'>
                    <span><b>{v['nome']}</b></span> 
                    <span class='status-badge' style='background:#BBF7D0; color:#166534;'>{i+1}º DA VEZ</span>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("🚀 INICIAR ATENDIMENTO", key=f"start_{v['id']}"):
                if not is_primeiro:
                    st.session_state[f"furo_{v['id']}"] = True
                else:
                    run_db("UPDATE usuarios SET status='Atendendo', h_entrada=? WHERE id=?", (datetime.now().isoformat(), v['id']))
                    st.rerun()
            
            if st.session_state.get(f"furo_{v['id']}", False):
                with st.expander("❗ Justificar Furo de Fila", expanded=True):
                    mot = st.selectbox("Motivo:", ["Preferência do cliente", "Operacional", "Retorno cliente"], key=f"mot_{v['id']}")
                    if st.button("Confirmar", key=f"conf_{v['id']}"):
                        run_db("UPDATE usuarios SET status='Atendendo', h_entrada=? WHERE id=?", (datetime.now().isoformat(), v['id']))
                        run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", (v['nome'], "Furo de Fila", mot, datetime.now().isoformat()))
                        st.session_state[f"furo_{v['id']}"] = False
                        st.rerun()

    with c_atend:
        st.subheader("🚀 Em Atendimento")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container(border=True):
                st.write(f"**{v['nome']}**")
                if st.button("🏁 FINALIZAR", key=f"fin_{v['id']}", type="primary"):
                    st.session_state[f"modal_{v['id']}"] = True
            
            if st.session_state.get(f"modal_{v['id']}", False):
                with st.expander("📝 Resultado do Atendimento", expanded=True):
                    res = st.selectbox("Status:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    vlr, pcas = 0.0, 1
                    if res == "Sucesso":
                        vlr = st.number_input("Valor R$:", min_value=0.0)
                        pcas = st.number_input("Qtd Peças:", min_value=1)
                    
                    if st.button("Concluir e Ir p/ Fim da Fila", key=f"save_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, valor, itens, data) VALUES (?,?,?,?,?)",
                              (v['nome'], res, vlr, pcas, datetime.now().isoformat()))
                        # Lógica de Fila SQL
                        res_max = run_db("SELECT MAX(ordem) FROM usuarios", is_select=True).iloc[0,0] or 0
                        run_db("UPDATE usuarios SET status='Esperando', ordem=?, h_entrada=NULL WHERE id=?", (res_max + 1, v['id']))
                        st.session_state[f"modal_{v['id']}"] = False
                        st.rerun()

    with c_fora:
        st.subheader("💤 Fora da Loja")
        fora = vendedores[vendedores['status'] == 'Fora']
        for _, v in fora.iterrows():
            if st.button(f"RETORNAR: {v['nome']}", key=f"ret_{v['id']}", use_container_width=True):
                res_max = run_db("SELECT MAX(ordem) FROM usuarios", is_select=True).iloc[0,0] or 0
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (res_max + 1, v['id']))
                st.rerun()

with t2:
    st.subheader("🏆 Ranking de Vendas (30 dias)")
    ranking = run_db("SELECT vendedor, SUM(valor) as total FROM historico GROUP BY vendedor ORDER BY total DESC", is_select=True)
    if not ranking.empty:
        st.bar_chart(ranking.set_index('vendedor'))
    else: st.info("Sem dados para exibir no ranking.")

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("👤 Gestão de Equipe")
        novo = st.text_input("Nome Completo:")
        if st.button("Cadastrar Vendedor"):
            if novo:
                login = novo.lower().replace(" ", ".")
                run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (novo.title(), login, 'Fora', 99))
                st.success(f"Vendedor {novo} cadastrado! Login: {login}")
        
        st.divider()
        if st.button("🔥 LIMPAR SISTEMA (RESET TOTAL)"):
            run_db("DELETE FROM usuarios"); run_db("DELETE FROM historico")
            st.rerun()
    else: st.warning("Apenas administradores podem acessar esta aba.")

with st.sidebar:
    st.markdown("### PRO-Vez")
    st.caption("Gestão Casa das Cuecas")
    if st.button("Deslogar"):
        st.session_state.user = None
        st.rerun()
