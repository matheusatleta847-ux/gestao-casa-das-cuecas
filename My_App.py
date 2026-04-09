import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io

# --- 1. DESIGN & CSS ---
st.set_page_config(page_title="PRO-Vez | Casa das Cuecas", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F8FAFC; }
    .metric-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border-top: 4px solid #1E293B; margin-bottom: 20px; }
    .metric-value { color: #1E293B; font-size: 26px; font-weight: 700; }
    .vendedor-box { background: white; padding: 14px; border-radius: 10px; border: 1px solid #E2E8F0; margin-bottom: 15px; display: flex; flex-direction: column; gap: 8px; width: 100%; }
    .primeiro-vez { border: 2px solid #22C55E; background: #F0FDF4; }
    .status-badge { font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 700; text-transform: uppercase; }
    .stButton>button { border-radius: 8px; font-weight: 600; width: 100%; transition: 0.2s; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE DADOS ---
DB_NAME = 'gestao_casa_v8.db'

def run_db(query, params=(), is_select=False):
    with sqlite3.connect(DB_NAME) as conn:
        if is_select: return pd.read_sql(query, conn, params=params)
        conn.execute(query, params); conn.commit()

def init_db():
    run_db('''CREATE TABLE IF NOT EXISTS usuarios 
              (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, motivo_pausa TEXT, ordem INTEGER)''')
    run_db('''CREATE TABLE IF NOT EXISTS historico 
              (id INTEGER PRIMARY KEY, vendedor TEXT, evento TEXT, motivo TEXT, valor REAL, data TEXT)''')

init_db()

# --- 3. LOGIN ---
if 'user' not in st.session_state: st.session_state.user = None

if not st.session_state.user:
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>🏢 Acesso Casa das Cuecas</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.form("login_form"):
            u = st.text_input("Login:").strip().lower()
            p = st.text_input("Senha (Admin):", type="password")
            if st.form_submit_button("Entrar"):
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

# --- 4. KPIs (FILTRADOS PARA NÃO CONTABILIZAR PAUSAS) ---
# Pegamos o histórico dos últimos 30 dias
dados_raw = run_db("SELECT * FROM historico WHERE data >= ?", 
                   ((datetime.now() - timedelta(days=30)).isoformat(),), True)

# FILTRO CRÍTICO: Somente eventos que são ATENDIMENTOS REAIS de clientes
atendimentos_reais = dados_raw[dados_raw['evento'].isin(['Sucesso', 'Não convertido', 'Troca'])]

faturamento = atendimentos_reais['valor'].sum() if not atendimentos_reais.empty else 0
vendas_sucesso = len(atendimentos_reais[atendimentos_reais['evento'] == 'Sucesso'])
# Taxa baseada apenas em quem entrou para ser atendido
taxa_conv = (vendas_sucesso / len(atendimentos_reais) * 100) if not atendimentos_reais.empty else 0

k1, k2, k3 = st.columns(3)
k1.markdown(f'<div class="metric-card"><div class="metric-title">Faturamento (30d)</div><div class="metric-value">R$ {faturamento:,.2f}</div></div>', unsafe_allow_html=True)
k2.markdown(f'<div class="metric-card"><div class="metric-title">Taxa de Conversão Real</div><div class="metric-value">{taxa_conv:.1f}%</div></div>', unsafe_allow_html=True)
k3.markdown(f'<div class="metric-card"><div class="metric-title">Atendimentos Reais</div><div class="metric-value">{len(atendimentos_reais)}</div></div>', unsafe_allow_html=True)

# --- 5. OPERACIONAL ---
t1, t2, t3 = st.tabs(["📋 LISTA DA VEZ", "🏆 PERFORMANCE", "⚙️ CONFIGURAÇÕES"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_esp, c_atend, c_fora = st.columns(3)

    def next_ordem():
        with sqlite3.connect(DB_NAME) as conn:
            res = conn.execute("SELECT MAX(ordem) FROM usuarios").fetchone()[0]
            return (res if res is not None else 0) + 1

    with c_esp:
        st.subheader("⏳ Esperando a Vez")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            is_primeiro = (i == 0)
            classe = "vendedor-box primeiro-vez" if is_primeiro else "vendedor-box"
            st.markdown(f"<div class='{classe}'><b>{v['nome']}</b><span class='status-badge' style='background:#BBF7D0;'>{i+1}º da Fila</span></div>", unsafe_allow_html=True)
            
            cb1, cb2 = st.columns(2)
            if cb1.button("Atender", key=f"at_{v['id']}"):
                run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],))
                st.rerun()
            if cb2.button("Sair", key=f"pausa_{v['id']}"):
                st.session_state[f"p_{v['id']}"] = True

            if st.session_state.get(f"p_{v['id']}", False):
                with st.expander("🚪 Motivo da Saída:", expanded=True):
                    mot = st.selectbox("Selecione:", ["Finalizar dia", "Almoço", "Lanche", "Banheiro", "Tarefas Externas"], key=f"s_{v['id']}")
                    if st.button("Concluir", key=f"c_{v['id']}"):
                        run_db("UPDATE usuarios SET status='Fora', motivo_pausa=? WHERE id=?", (mot, v['id']))
                        # Evento 'Fluxo' não entra na conta de conversão
                        run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", (v['nome'], "Fluxo-Saída", mot, datetime.now().isoformat()))
                        st.session_state[f"p_{v['id']}"] = False
                        st.rerun()

    with c_atend:
        st.subheader("🚀 Em Atendimento")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container(border=True):
                st.markdown(f"**{v['nome']}**")
                if st.button("Finalizar Atendimento", key=f"fin_{v['id']}", type="primary"):
                    st.session_state[f"f_{v['id']}"] = True
            
            if st.session_state.get(f"f_{v['id']}", False):
                with st.expander("🏁 Resultado:", expanded=True):
                    res = st.selectbox("Status:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    vlr = st.number_input("Valor R$:", min_value=0.0) if res == "Sucesso" else 0.0
                    if st.button("Salvar", key=f"sv_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, valor, data) VALUES (?,?,?,?)", (v['nome'], res, vlr, datetime.now().isoformat()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (next_ordem(), v['id']))
                        st.session_state[f"f_{v['id']}"] = False
                        st.rerun()

    with c_fora:
        st.subheader("💤 Fora da Loja")
        fora = vendedores[vendedores['status'] == 'Fora']
        for _, v in fora.iterrows():
            with st.container():
                st.markdown(f"<div class='vendedor-box' style='border-left:5px solid #64748B;'><b>{v['nome']}</b><br><small>{v['motivo_pausa']}</small></div>", unsafe_allow_html=True)
                if st.button(f"Retornar: {v['nome']}", key=f"ret_{v['id']}"):
                    run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (next_ordem(), v['id']))
                    st.rerun()

with t2:
    st.subheader("🏆 Performance")
    if not atendimentos_reais.empty:
        st.bar_chart(atendimentos_reais.groupby('vendedor')['valor'].sum())
        
        # EXPORTAÇÃO EXCEL (XLSX)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            atendimentos_reais.to_excel(writer, sheet_name='Vendas', index=False)
        
        st.download_button(
            label="📊 Baixar Relatório em Excel (XLSX)",
            data=buffer.getvalue(),
            file_name=f"Relatorio_Vendas_{datetime.now().strftime('%d_%m')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("👤 Gestão")
        n = st.text_input("Nome:")
        if st.button("Cadastrar"):
            if n:
                login = n.lower().replace(" ", ".")
                run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (n.title(), login, 'Fora', 0))
                st.rerun()
        
        st.markdown("---")
        equipe = run_db("SELECT * FROM usuarios", is_select=True)
        for _, r in equipe.iterrows():
            c_i, c_d = st.columns([4, 1])
            c_i.write(f"**{r['nome']}** ({r['login']})")
            if c_d.button("Excluir", key=f"del_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],))
                st.rerun()
    else: st.warning("Acesso Admin necessário.")

with st.sidebar:
    st.write(f"Vendedor: **{st.session_state.user['nome']}**")
    if st.button("Sair"):
        st.session_state.user = None
        st.rerun()
