import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import plotly.express as px

# --- 1. CONFIGURAÇÃO PREMIUM & UI ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F8FAFC; }
    
    .metric-card { 
        background: white; padding: 20px; border-radius: 12px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
        border-top: 4px solid #1E293B; margin-bottom: 20px; 
    }
    .metric-title { color: #64748B; font-size: 13px; font-weight: 600; text-transform: uppercase; }
    .metric-value { color: #1E293B; font-size: 28px; font-weight: 700; }

    .vendedor-box { 
        background: white; padding: 16px; border-radius: 10px; 
        border: 1px solid #E2E8F0; margin-bottom: 12px; 
        display: flex; flex-direction: column; gap: 8px; width: 100%; 
    }
    .primeiro-vez { border: 2px solid #22C55E; background: #F0FDF4; box-shadow: 0 4px 12px rgba(34, 197, 94, 0.15); }
    .status-badge { font-size: 11px; padding: 3px 10px; border-radius: 20px; font-weight: 700; text-align: center;}
    
    .stButton>button { border-radius: 8px; font-weight: 600; width: 100%; transition: 0.3s; height: 45px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE DADOS ---
DB_NAME = 'gestao_elite_v15.db'

def run_db(query, params=(), is_select=False):
    with sqlite3.connect(DB_NAME) as conn:
        if is_select: return pd.read_sql(query, conn, params=params)
        conn.execute(query, params); conn.commit()

def init_db():
    run_db('''CREATE TABLE IF NOT EXISTS usuarios 
              (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, motivo_pausa TEXT, ordem INTEGER)''')
    run_db('''CREATE TABLE IF NOT EXISTS historico 
              (id INTEGER PRIMARY KEY, vendedor TEXT, evento TEXT, motivo TEXT, valor REAL, itens INTEGER, data TEXT)''')

init_db()

# --- 3. FUNÇÃO DE FILA (CORRIGIDA PARA EVITAR TYPEERROR) ---
def next_ordem():
    with sqlite3.connect(DB_NAME) as conn:
        res = conn.execute("SELECT MAX(ordem) FROM usuarios").fetchone()[0]
        return (int(res) if res is not None else 0) + 1

# --- 4. CONTROLE DE ACESSO ---
if 'user' not in st.session_state: st.session_state.user = None

if not st.session_state.user:
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>🔐 Painel de Gestão Elite</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.form("login_form"):
            u = st.text_input("Utilizador:").strip().lower()
            p = st.text_input("Password Admin:", type="password")
            if st.form_submit_button("Entrar no Sistema"):
                if u == "admin" and p == "admin@123":
                    st.session_state.user = {"nome": "Administrador", "is_admin": True}; st.rerun()
                else:
                    res = run_db("SELECT * FROM usuarios WHERE login = ?", (u,), True)
                    if not res.empty:
                        st.session_state.user = {"nome": res.iloc[0]['nome'], "is_admin": False}; st.rerun()
                    else: st.error("Acesso negado.")
    st.stop()

# --- 5. KPIs DE INTELIGÊNCIA ---
dados_raw = run_db("SELECT * FROM historico WHERE data >= ?", 
                   ((datetime.now() - timedelta(days=30)).isoformat(),), True)

vendas_sucesso = dados_raw[dados_raw['evento'] == 'Sucesso']
atendimentos_reais = dados_raw[dados_raw['evento'].isin(['Sucesso', 'Não convertido', 'Troca'])]

faturamento = vendas_sucesso['valor'].sum() if not vendas_sucesso.empty else 0
conversao = (len(vendas_sucesso) / len(atendimentos_reais) * 100) if not atendimentos_reais.empty else 0
pa_medio = (vendas_sucesso['itens'].sum() / len(vendas_sucesso)) if not vendas_sucesso.empty else 0
ticket_medio = (faturamento / len(vendas_sucesso)) if not vendas_sucesso.empty else 0

k1, k2, k3, k4 = st.columns(4)
k1.markdown(f'<div class="metric-card"><div class="metric-title">Faturamento</div><div class="metric-value">R$ {faturamento:,.2f}</div></div>', unsafe_allow_html=True)
k2.markdown(f'<div class="metric-card"><div class="metric-title">Conversão</div><div class="metric-value">{conversao:.1f}%</div></div>', unsafe_allow_html=True)
k3.markdown(f'<div class="metric-card"><div class="metric-title">P.A. (Itens)</div><div class="metric-value">{pa_medio:.2f}</div></div>', unsafe_allow_html=True)
k4.markdown(f'<div class="metric-card"><div class="metric-title">Ticket Médio</div><div class="metric-value">R$ {ticket_medio:,.2f}</div></div>', unsafe_allow_html=True)

# --- 6. INTERFACE OPERACIONAL ---
t1, t2, t3 = st.tabs(["📋 FILA DA VEZ", "📊 DASHBOARDS", "⚙️ CONFIGURAÇÕES"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_esp, c_atend, c_fora = st.columns(3)

    with c_esp:
        st.subheader("⏳ Na Fila")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            is_primeiro = (i == 0)
            classe = "vendedor-box primeiro-vez" if is_primeiro else "vendedor-box"
            st.markdown(f"<div class='{classe}'><b>{v['nome']}</b><span class='status-badge' style='background:#BBF7D0;'>{i+1}º na Fila</span></div>", unsafe_allow_html=True)
            
            b1, b2 = st.columns(2)
            if b1.button("Atender", key=f"at_{v['id']}"):
                run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],))
                st.rerun()
            if b2.button("Sair/Pausa", key=f"p_{v['id']}"):
                st.session_state[f"m_p_{v['id']}"] = True

            if st.session_state.get(f"m_p_{v['id']}", False):
                with st.expander("Motivo:", expanded=True):
                    mot = st.selectbox("Justificativa:", ["Almoço", "Banheiro", "Lanche", "Finalizar dia", "Externo"], key=f"sel_{v['id']}")
                    if st.button("Confirmar", key=f"ok_{v['id']}"):
                        ev_log = "FINAL DE DIA" if mot == "Finalizar dia" else "SAÍDA (PAUSA)"
                        run_db("UPDATE usuarios SET status='Fora', motivo_pausa=? WHERE id=?", (mot, v['id']))
                        run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", (v['nome'], ev_log, mot, datetime.now().isoformat()))
                        st.session_state[f"m_p_{v['id']}"] = False; st.rerun()

    with c_atend:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container(border=True):
                st.write(f"Vendedor: **{v['nome']}**")
                if st.button("Finalizar Atendimento", key=f"fin_{v['id']}", type="primary"):
                    st.session_state[f"f_{v['id']}"] = True
            
            if st.session_state.get(f"f_{v['id']}", False):
                with st.expander("Resultado:", expanded=True):
                    res = st.selectbox("Status:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    if res == "Sucesso":
                        vlr = st.number_input("Valor total (R$):", min_value=0.0)
                        itens = st.number_input("Itens (P.A.):", min_value=1)
                        motivo_perda = "Venda Realizada"
                    else:
                        vlr, itens = 0.0, 0
                        motivo_perda = st.selectbox("Motivo perda:", ["Preço", "Falta Tamanho", "Só olhando", "Falta Cor", "Troca"])

                    if st.button("Gravar", key=f"sv_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", 
                               (v['nome'], res, motivo_perda, vlr, itens, datetime.now().isoformat()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (next_ordem(), v['id']))
                        st.session_state[f"f_{v['id']}"] = False; st.rerun()

    with c_fora:
        st.subheader("💤 Fora da Loja")
        fora = vendedores[vendedores['status'] == 'Fora']
        for _, v in fora.iterrows():
            with st.container():
                st.markdown(f"<div class='vendedor-box' style='border-left:5px solid #64748B;'><b>{v['nome']}</b><br><small>Status: {v['motivo_pausa']}</small></div>", unsafe_allow_html=True)
                if st.button(f"Entrar / Retornar: {v['nome']}", key=f"ret_{v['id']}"):
                    ev_log = "INÍCIO DE DIA" if v['motivo_pausa'] in ["Finalizar dia", None] else "RETORNO (PAUSA)"
                    run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", (v['nome'], ev_log, v['motivo_pausa'], datetime.now().isoformat()))
                    run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (next_ordem(), v['id']))
                    st.rerun()

with t2:
    st.subheader("📊 Dashboards Interativos")
    if not atendimentos_reais.empty:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            df_fat = vendas_sucesso.groupby('vendedor')['valor'].sum().reset_index()
            fig1 = px.bar(df_fat, x='vendedor', y='valor', title="Faturamento por Vendedor (R$)", color='valor', color_continuous_scale='Greens')
            st.plotly_chart(fig1, use_container_width=True)
        with col_g2:
            df_perda = atendimentos_reais[atendimentos_reais['evento'] == 'Não convertido'].groupby('motivo').size().reset_index(name='qtd')
            fig2 = px.pie(df_perda, values='qtd', names='motivo', title="Motivos de Perda", hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()
        buffer = io.BytesIO()
        df_export = dados_raw.sort_values(by='data', ascending=False)
        df_export.columns = ['ID', 'Vendedor', 'Evento', 'Detalhe', 'Valor (R$)', 'Peças', 'Data/Hora']
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Logs')
        st.download_button("📊 Baixar Relatório Completo (.xlsx)", data=buffer.getvalue(), 
                         file_name=f"Auditoria_Elite_{datetime.now().strftime('%d_%m')}.xlsx",
                         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else: st.info("Sem dados.")

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("⚙️ Gestão de Equipe")
        with st.container(border=True):
            nome_n = st.text_input("Nome do Vendedor:")
            if st.button("Cadastrar"):
                if nome_n:
                    log_n = nome_n.lower().replace(" ", ".")
                    check = run_db("SELECT * FROM usuarios WHERE login = ?", (log_n,), is_select=True)
                    if not check.empty: st.error("Utilizador já existe.")
                    else:
                        run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (nome_n.title(), log_n, 'Fora', 0))
                        st.rerun()
        
        st.divider()
        equipe = run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True)
        for _, r in equipe.iterrows():
            ci, cd = st.columns([4, 1])
            ci.write(f"👤 **{r['nome']}** | Login: {r['login']}")
            if cd.button("Excluir", key=f"del_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
    else: st.warning("Acesso Admin necessário.")

with st.sidebar:
    st.image("https://casadascuecas.vteximg.com.br/arquivos/logo-casa-das-cuecas.png", width=150)
    st.write(f"Operador: **{st.session_state.user['nome']}**")
    if st.button("Logout"):
        st.session_state.user = None; st.rerun()
