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
    .vendedor-box { background: white; padding: 14px; border-radius: 10px; border: 1px solid #E2E8F0; margin-bottom: 15px; display: flex; flex-direction: column; gap: 5px; width: 100%; }
    .primeiro-vez { border: 2px solid #22C55E; background: #F0FDF4; }
    .status-badge { font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 700; }
    .stButton>button { border-radius: 8px; font-weight: 600; width: 100%; transition: 0.2s; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE DADOS ---
DB_NAME = 'gestao_casa_v10.db'

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

# --- 3. ACESSO ---
if 'user' not in st.session_state: st.session_state.user = None

if not st.session_state.user:
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>🏢 Painel PRO-Vez</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.form("login"):
            u = st.text_input("Login:").strip().lower()
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
                    else: st.error("Acesso negado.")
    st.stop()

# --- 4. KPIs (PERFORMANCE DE VENDAS) ---
dados_raw = run_db("SELECT * FROM historico WHERE data >= ?", 
                   ((datetime.now() - timedelta(days=30)).isoformat(),), True)

# Filtro para Dashboards: Apenas vendas e tentativas
atendimentos_reais = dados_raw[dados_raw['evento'].isin(['Sucesso', 'Não convertido', 'Troca'])]

faturado = atendimentos_reais['valor'].sum() if not atendimentos_reais.empty else 0
vendas = len(atendimentos_reais[atendimentos_reais['evento'] == 'Sucesso'])
taxa = (vendas / len(atendimentos_reais) * 100) if not atendimentos_reais.empty else 0

k1, k2, k3 = st.columns(3)
k1.markdown(f'<div class="metric-card">Faturamento (30d)<br><span class="metric-value">R$ {faturado:,.2f}</span></div>', unsafe_allow_html=True)
k2.markdown(f'<div class="metric-card">Conversão Real<br><span class="metric-value">{taxa:.1f}%</span></div>', unsafe_allow_html=True)
k3.markdown(f'<div class="metric-card">Atendimentos<br><span class="metric-value">{len(atendimentos_reais)}</span></div>', unsafe_allow_html=True)

# --- 5. OPERACIONAL ---
t1, t2, t3 = st.tabs(["📋 LISTA DA VEZ", "📊 PERFORMANCE", "⚙️ CONFIGURAÇÕES"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_esp, c_atend, c_fora = st.columns(3)

    def next_ordem():
        with sqlite3.connect(DB_NAME) as conn:
            res = conn.execute("SELECT MAX(ordem) FROM usuarios").fetchone()[0]
            return (res if res is not None else 0) + 1

    with c_esp:
        st.subheader("⏳ Na Fila")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            is_primeiro = (i == 0)
            classe = "vendedor-box primeiro-vez" if is_primeiro else "vendedor-box"
            st.markdown(f"<div class='{classe}'><b>{v['nome']}</b><span class='status-badge' style='background:#BBF7D0;'>{i+1}º da Fila</span></div>", unsafe_allow_html=True)
            
            b1, b2 = st.columns(2)
            if b1.button("Atender", key=f"at_{v['id']}"):
                run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],))
                st.rerun()
            if b2.button("Sair", key=f"p_{v['id']}"):
                st.session_state[f"modal_p_{v['id']}"] = True

            if st.session_state.get(f"modal_p_{v['id']}", False):
                with st.expander("Motivo da Saída:", expanded=True):
                    mot = st.selectbox("Justificativa:", ["Finalizar dia", "Almoço", "Lanche", "Banheiro", "Tarefas Externas"], key=f"sel_{v['id']}")
                    if st.button("Confirmar Saída", key=f"ok_{v['id']}"):
                        run_db("UPDATE usuarios SET status='Fora', motivo_pausa=? WHERE id=?", (mot, v['id']))
                        # REGISTRO DE SAÍDA NO HISTÓRICO (Para o Excel)
                        run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", 
                               (v['nome'], "SAÍDA", mot, datetime.now().isoformat()))
                        st.session_state[f"modal_p_{v['id']}"] = False
                        st.rerun()

    with c_atend:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container(border=True):
                st.write(f"**{v['nome']}**")
                if st.button("Finalizar", key=f"fin_{v['id']}", type="primary"):
                    st.session_state[f"f_{v['id']}"] = True
            
            if st.session_state.get(f"f_{v['id']}", False):
                with st.expander("Resultado:", expanded=True):
                    res = st.selectbox("Status:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    vlr = st.number_input("Valor R$:", min_value=0.0) if res == "Sucesso" else 0.0
                    if st.button("Salvar Resultado", key=f"sv_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, valor, data) VALUES (?,?,?,?)", 
                               (v['nome'], res, vlr, datetime.now().isoformat()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", 
                               (next_ordem(), v['id']))
                        st.session_state[f"f_{v['id']}"] = False
                        st.rerun()

    with c_fora:
        st.subheader("💤 Fora da Loja")
        fora = vendedores[vendedores['status'] == 'Fora']
        for _, v in fora.iterrows():
            with st.container():
                st.markdown(f"<div class='vendedor-box' style='border-left:5px solid #64748B;'><b>{v['nome']}</b><br><small>Status: {v['motivo_pausa']}</small></div>", unsafe_allow_html=True)
                if st.button(f"Retornar: {v['nome']}", key=f"ret_{v['id']}"):
                    # REGISTRO DE VOLTA NO HISTÓRICO (Para o Excel)
                    run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", 
                           (v['nome'], "RETORNO", v['motivo_pausa'], datetime.now().isoformat()))
                    run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", 
                           (next_ordem(), v['id']))
                    st.rerun()

with t2:
    st.subheader("🏆 Performance & Relatórios")
    if not dados_raw.empty:
        # Gráfico foca apenas em valores de venda
        if not atendimentos_reais.empty:
            st.bar_chart(atendimentos_reais.groupby('vendedor')['valor'].sum())
        
        # EXPORTAÇÃO EXCEL XLSX (Inclui tudo: Vendas + Saídas + Retornos)
        buffer = io.BytesIO()
        try:
            # Ordenamos por data para o Excel fazer sentido cronológico
            relatorio_completo = dados_raw.sort_values(by='data', ascending=False)
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                relatorio_completo.to_excel(writer, sheet_name='Log_Completo', index=False)
            
            st.download_button(
                label="📊 Baixar Log Completo em Excel (Vendas e Pausas)",
                data=buffer.getvalue(),
                file_name=f"Relatorio_Geral_CasaCuecas_{datetime.now().strftime('%d_%m_%Hh%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except: st.error("Erro ao gerar arquivo Excel.")

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("⚙️ Gestão de Equipe")
        with st.container(border=True):
            n = st.text_input("Nome do Vendedor:")
            if st.button("Cadastrar Novo"):
                if n:
                    log = n.lower().replace(" ", ".")
                    run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (n.title(), log, 'Fora', 0))
                    st.rerun()
        
        st.divider()
        equipe = run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True)
        for _, r in equipe.iterrows():
            col_info, col_btn = st.columns([4, 1])
            col_info.write(f"👤 **{r['nome']}** (Login: {r['login']})")
            if col_btn.button("Excluir", key=f"del_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],))
                st.rerun()
    else: st.warning("Acesso restrito ao Administrador.")

with st.sidebar:
    st.write(f"Conectado como: **{st.session_state.user['nome']}**")
    if st.button("Logoff"):
        st.session_state.user = None
        st.rerun()
