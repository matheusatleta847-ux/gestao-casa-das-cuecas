import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# --- 1. DESIGN PREMIUM & CSS ---
st.set_page_config(page_title="PRO-Vez | Casa das Cuecas", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F8FAFC; }
    
    /* Cards de KPI */
    .metric-card {
        background: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-top: 4px solid #1E293B; margin-bottom: 20px;
    }
    .metric-title { color: #64748B; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-value { color: #1E293B; font-size: 26px; font-weight: 700; margin-top: 5px; }

    /* Fila de Atendimento (Vertical e organizada) */
    .vendedor-box {
        background: white; padding: 14px 18px; border-radius: 10px;
        border: 1px solid #E2E8F0; margin-bottom: 12px;
        display: flex; justify-content: space-between; align-items: center;
        width: 100%;
    }
    .primeiro-vez { background: #F0FDF4; border: 2px solid #BBF7D0; box-shadow: 0 2px 10px rgba(34, 197, 94, 0.1); }
    .status-badge { font-size: 11px; padding: 3px 10px; border-radius: 12px; font-weight: 600; }
    
    /* Botões */
    .stButton>button { border-radius: 8px; font-weight: 600; padding: 0.6rem; width: 100%; transition: 0.2s; }
    .stButton>button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    
    /* Tabela de Gestão */
    .admin-table { width: 100%; border-collapse: collapse; margin-top: 20px; background: white; border-radius: 10px; overflow: hidden; }
    .admin-table th { background: #F1F5F9; padding: 12px; text-align: left; color: #475569; font-size: 13px; }
    .admin-table td { padding: 12px; border-bottom: 1px solid #F1F5F9; font-size: 14px; color: #1E293B; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE DADOS ---
DB_NAME = 'gestao_casa_v6.db'

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

# --- 3. LOGIN ---
if 'user' not in st.session_state: st.session_state.user = None

if not st.session_state.user:
    st.markdown("<h2 style='text-align: center; color: #1E293B; margin-top: 50px;'>🏢 Acesso PRO-Vez</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.form("login_form"):
            u = st.text_input("Usuário:").strip().lower()
            p = st.text_input("Senha (Admin):", type="password")
            if st.form_submit_button("Entrar no Painel"):
                if u == "admin" and p == "admin@123":
                    st.session_state.user = {"nome": "Administrador", "is_admin": True}
                    st.rerun()
                else:
                    res = run_db("SELECT * FROM usuarios WHERE login = ?", (u,), True)
                    if not res.empty:
                        st.session_state.user = {"nome": res.iloc[0]['nome'], "is_admin": False}
                        st.rerun()
                    else: st.error("Login inválido.")
    st.stop()

# --- 4. KPIs ---
dados_mes = run_db("SELECT * FROM historico WHERE data >= ?", 
                   ((datetime.now() - timedelta(days=30)).isoformat(),), True)

faturamento = dados_mes['valor'].sum() if not dados_mes.empty else 0
atendimentos = len(dados_mes)
vendas_sucesso = len(dados_mes[dados_mes['evento'] == 'Sucesso'])
taxa_conv = (vendas_sucesso / atendimentos * 100) if atendimentos > 0 else 0
ticket_medio = (faturamento / vendas_sucesso) if vendas_sucesso > 0 else 0

k1, k2, k3, k4 = st.columns(4)
indicadores = [
    ("Faturamento Mensal", faturamento, "R$ "),
    ("Taxa Conversão", taxa_conv, "", "%"),
    ("Ticket Médio", ticket_medio, "R$ "),
    ("Total Atendimentos", atendimentos, "")
]

for col, (titulo, valor, pre, *suf) in zip([k1, k2, k3, k4], indicadores):
    sufixo = suf[0] if suf else ""
    val_exibicao = f"{valor:,.2f}" if isinstance(valor, float) else f"{valor:,}"
    with col:
        st.markdown(f"""<div class="metric-card"><div class="metric-title">{titulo}</div>
                    <div class="metric-value">{pre}{val_exibicao}{sufixo}</div></div>""", unsafe_allow_html=True)

# --- 5. FILA E OPERACIONAL ---
st.markdown("---")
t1, t2, t3 = st.tabs(["📋 FILA DE ATENDIMENTO", "📊 PERFORMANCE & RANKING", "⚙️ CONFIGURAÇÕES"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_esp, c_atend, c_fora = st.columns(3)

    with c_esp:
        st.subheader("⏳ Esperando")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        # Loop para empilhar um abaixo do outro
        for i, v in esp.iterrows():
            is_primeiro = (i == 0)
            classe = "vendedor-box primeiro-vez" if is_primeiro else "vendedor-box"
            st.markdown(f"<div class='{classe}'><span><b>{v['nome']}</b></span> <span class='status-badge' style='background:#BBF7D0; color:#166534;'>{i+1}º DA VEZ</span></div>", unsafe_allow_html=True)
            
            if st.button("🚀 INICIAR ATENDIMENTO", key=f"start_{v['id']}"):
                if not is_primeiro: st.session_state[f"furo_{v['id']}"] = True
                else:
                    run_db("UPDATE usuarios SET status='Atendendo', h_entrada=? WHERE id=?", (datetime.now().isoformat(), v['id']))
                    st.rerun()
            
            if st.session_state.get(f"furo_{v['id']}", False):
                with st.expander("❗ Justificar Furo", expanded=True):
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
                with st.expander("📝 Detalhes", expanded=True):
                    res = st.selectbox("Status:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    vlr, pcas = 0.0, 1
                    if res == "Sucesso":
                        vlr = st.number_input("Valor R$:", min_value=0.0)
                        pcas = st.number_input("Qtd Peças:", min_value=1)
                    
                    if st.button("Salvar e Sair", key=f"save_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, valor, itens, data) VALUES (?,?,?,?,?)",
                              (v['nome'], res, vlr, pcas, datetime.now().isoformat()))
                        
                        with sqlite3.connect(DB_NAME) as conn:
                            res_sql = conn.execute("SELECT MAX(ordem) FROM usuarios").fetchone()[0]
                            max_o = res_sql if res_sql is not None else 0
                        
                        run_db("UPDATE usuarios SET status='Esperando', ordem=?, h_entrada=NULL WHERE id=?", (max_o + 1, v['id']))
                        st.session_state[f"modal_{v['id']}"] = False
                        st.rerun()

    with c_fora:
        st.subheader("💤 Fora da Loja")
        fora = vendedores[vendedores['status'] == 'Fora']
        for _, v in fora.iterrows():
            if st.button(f"RETORNAR: {v['nome']}", key=f"ret_{v['id']}"):
                with sqlite3.connect(DB_NAME) as conn:
                    res_sql = conn.execute("SELECT MAX(ordem) FROM usuarios").fetchone()[0]
                    max_o = res_sql if res_sql is not None else 0
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (max_o + 1, v['id']))
                st.rerun()

with t2:
    st.subheader("🏆 Ranking (30 dias)")
    ranking = run_db("SELECT vendedor, SUM(valor) as total FROM historico GROUP BY vendedor ORDER BY total DESC", is_select=True)
    if not ranking.empty: st.bar_chart(ranking.set_index('vendedor'))
    else: st.info("Sem dados.")

# --- 6. CONFIGURAÇÕES & GESTÃO DE EQUIPE ---
with t3:
    if st.session_state.user['is_admin']:
        st.subheader("👤 Cadastrar Novo Vendedor")
        with st.container(border=True):
            col_n, col_b = st.columns([3, 1])
            novo_nome = col_n.text_input("Nome Completo:", placeholder="Ex: Matheus Silva")
            if col_b.button("Cadastrar", use_container_width=True):
                if novo_nome:
                    login_gerado = novo_nome.lower().replace(" ", ".")
                    try:
                        run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", 
                               (novo_nome.title(), login_gerado, 'Fora', 0))
                        st.success(f"Vendedor cadastrado! Login: {login_gerado}")
                        st.rerun()
                    except: st.error("Este login já existe.")

        st.markdown("### 📋 Vendedores Cadastrados")
        equipe = run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True)
        
        if not equipe.empty:
            # Exibição em tabela com opção de excluir
            for _, row in equipe.iterrows():
                col_info, col_del = st.columns([4, 1])
                col_info.markdown(f"""
                    <div style='padding:10px; border-bottom:1px solid #eee;'>
                        <b>{row['nome']}</b> | <small>Login: {row['login']}</small> | <small>Status: {row['status']}</small>
                    </div>
                """, unsafe_allow_html=True)
                if col_del.button("🗑️ Excluir", key=f"del_{row['id']}"):
                    run_db("DELETE FROM usuarios WHERE id=?", (row['id'],))
                    st.warning(f"Vendedor {row['nome']} removido.")
                    st.rerun()
        else:
            st.info("Nenhum vendedor cadastrado.")

        st.divider()
        if st.button("🔥 RESET TOTAL DO HISTÓRICO (CUIDADO)"):
            run_db("DELETE FROM historico")
            st.success("Histórico de vendas limpo.")
            st.rerun()
    else:
        st.warning("Apenas administradores podem acessar as configurações de equipe.")

with st.sidebar:
    st.write(f"Vendedor: **{st.session_state.user['nome']}**")
    if st.button("Deslogar"):
        st.session_state.user = None
        st.rerun()
