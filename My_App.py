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

# --- 2. FUNÇÕES DE SUPORTE (DATA E HORA BRASÍLIA) ---
def get_now_br():
    # Ajusta o horário do servidor (UTC) para Brasília (UTC-3)
    return datetime.now() - timedelta(hours=3)

def get_now_str():
    return get_now_br().strftime('%d/%m/%Y %H:%M:%S')

# --- 3. MOTOR DE DADOS ---
DB_NAME = 'gestao_elite_v16.db'

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

def next_ordem():
    with sqlite3.connect(DB_NAME) as conn:
        res = conn.execute("SELECT MAX(ordem) FROM usuarios").fetchone()[0]
        return (int(res) if res is not None else 0) + 1

# --- 4. ACESSO ---
if 'user' not in st.session_state: st.session_state.user = None

if not st.session_state.user:
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>🔐 Painel Elite - Casa das Cuecas</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.form("login_form"):
            u = st.text_input("Usuário:").strip().lower()
            p = st.text_input("Senha Admin:", type="password")
            if st.form_submit_button("Entrar"):
                if u == "admin" and p == "admin@123":
                    st.session_state.user = {"nome": "Admin", "is_admin": True}; st.rerun()
                else:
                    res = run_db("SELECT * FROM usuarios WHERE login = ?", (u,), True)
                    if not res.empty:
                        st.session_state.user = {"nome": res.iloc[0]['nome'], "is_admin": False}; st.rerun()
                    else: st.error("Acesso negado.")
    st.stop()

# --- 5. DASHBOARD & KPIs ---
dados_raw = run_db("SELECT * FROM historico", is_select=True) # Carrega todo o histórico

vendas_sucesso = dados_raw[dados_raw['evento'] == 'Sucesso']
atendimentos = dados_raw[dados_raw['evento'].isin(['Sucesso', 'Não convertido', 'Troca'])]

faturamento = vendas_sucesso['valor'].sum() if not vendas_sucesso.empty else 0
conversao = (len(vendas_sucesso) / len(atendimentos) * 100) if not atendimentos.empty else 0
pa_medio = (vendas_sucesso['itens'].sum() / len(vendas_sucesso)) if not vendas_sucesso.empty else 0
ticket_medio = (faturamento / len(vendas_sucesso)) if not vendas_sucesso.empty else 0

k1, k2, k3, k4 = st.columns(4)
k1.markdown(f'<div class="metric-card"><div class="metric-title">Faturamento</div><div class="metric-value">R$ {faturamento:,.2f}</div></div>', unsafe_allow_html=True)
k2.markdown(f'<div class="metric-card"><div class="metric-title">Conversão</div><div class="metric-value">{conversao:.1f}%</div></div>', unsafe_allow_html=True)
k3.markdown(f'<div class="metric-card"><div class="metric-title">P.A. (Itens)</div><div class="metric-value">{pa_medio:.2f}</div></div>', unsafe_allow_html=True)
k4.markdown(f'<div class="metric-card"><div class="metric-title">Ticket Médio</div><div class="metric-value">R$ {ticket_medio:,.2f}</div></div>', unsafe_allow_html=True)

# --- 6. OPERAÇÃO ---
t1, t2, t3 = st.tabs(["📋 OPERAÇÃO", "📊 PERFORMANCE", "⚙️ CONFIG"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_esp, c_atend, c_fora = st.columns(3)

    with c_esp:
        st.subheader("⏳ Na Fila")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            classe = "vendedor-box primeiro-vez" if i == 0 else "vendedor-box"
            st.markdown(f"<div class='{classe}'><b>{v['nome']}</b><span class='status-badge' style='background:#BBF7D0;'>{i+1}º na Fila</span></div>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            if col1.button("Atender", key=f"at_{v['id']}"):
                run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],))
                st.rerun()
            if col2.button("Sair/Pausa", key=f"p_{v['id']}"):
                st.session_state[f"modal_{v['id']}"] = True
            
            if st.session_state.get(f"modal_{v['id']}", False):
                with st.expander("Motivo da Saída:", expanded=True):
                    mot = st.selectbox("Selecione:", ["Almoço", "Banheiro", "Lanche", "Finalizar dia", "Externo"], key=f"sel_{v['id']}")
                    if st.button("Confirmar", key=f"ok_{v['id']}"):
                        ev = "FINAL DE DIA" if mot == "Finalizar dia" else "SAÍDA (PAUSA)"
                        run_db("UPDATE usuarios SET status='Fora', motivo_pausa=? WHERE id=?", (mot, v['id']))
                        run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", (v['nome'], ev, mot, get_now_str()))
                        st.session_state[f"modal_{v['id']}"] = False; st.rerun()

    with c_atend:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container(border=True):
                st.write(f"**{v['nome']}**")
                if st.button("Finalizar", key=f"f_{v['id']}", type="primary"):
                    st.session_state[f"fin_{v['id']}"] = True
            if st.session_state.get(f"fin_{v['id']}", False):
                with st.expander("Dados da Venda:", expanded=True):
                    res = st.selectbox("Status:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    vlr = st.number_input("Valor R$:", min_value=0.0, key=f"v_{v['id']}") if res == "Sucesso" else 0.0
                    it = st.number_input("Qtd Itens:", min_value=1, key=f"i_{v['id']}") if res == "Sucesso" else 0
                    if st.button("Gravar Atendimento", key=f"g_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", 
                               (v['nome'], res, "Venda" if res=="Sucesso" else "Não Converteu", vlr, it, get_now_str()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (next_ordem(), v['id']))
                        st.session_state[f"fin_{v['id']}"] = False; st.rerun()

    with c_fora:
        st.subheader("💤 Fora da Loja")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown(f"<div class='vendedor-box'><b>{v['nome']}</b><br><small>Status: {v['motivo_pausa']}</small></div>", unsafe_allow_html=True)
            if st.button(f"Entrar / Retornar: {v['nome']}", key=f"ret_{v['id']}"):
                ev = "INÍCIO DE DIA" if v['motivo_pausa'] in ["Finalizar dia", None] else "RETORNO (PAUSA)"
                run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", (v['nome'], ev, v['motivo_pausa'], get_now_str()))
                run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (next_ordem(), v['id']))
                st.rerun()

with t2:
    st.subheader("📊 Performance Inteligente")
    if not atendimentos.empty:
        c1, c2 = st.columns(2)
        with c1:
            df_f = vendas_sucesso.groupby('vendedor')['valor'].sum().reset_index()
            fig1 = px.bar(df_f, x='vendedor', y='valor', title="Faturamento por Vendedor", color='valor', color_continuous_scale='Greens')
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            df_p = atendimentos[atendimentos['evento'] == 'Não convertido'].groupby('motivo').size().reset_index(name='qtd')
            fig2 = px.pie(df_p, values='qtd', names='motivo', title="Por que não vendemos?", hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()
        buffer = io.BytesIO()
        df_export = dados_raw.sort_values(by='id', ascending=False)
        df_export.columns = ['ID', 'Vendedor', 'Evento', 'Detalhe', 'Valor (R$)', 'Peças', 'Data e Hora (SP)']
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Auditoria_Casa_Cuecas')
        st.download_button("📥 Baixar Relatório Excel Completo", data=buffer.getvalue(), 
                         file_name=f"Relatorio_Casa_Cuecas_{get_now_br().strftime('%d_%m')}.xlsx",
                         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("⚙️ Gestão de Equipe")
        with st.container(border=True):
            n_nv = st.text_input("Nome do Vendedor:")
            if st.button("Cadastrar Novo"):
                if n_nv:
                    l_nv = n_nv.lower().replace(" ", ".")
                    try:
                        run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (n_nv.title(), l_nv, 'Fora', 0))
                        st.success("Cadastrado!"); st.rerun()
                    except: st.error("Login já existe.")
        equipe = run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True)
        for _, r in equipe.iterrows():
            c_n, c_e = st.columns([4, 1])
            c_n.write(f"👤 **{r['nome']}**")
            if c_e.button("Remover", key=f"del_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
