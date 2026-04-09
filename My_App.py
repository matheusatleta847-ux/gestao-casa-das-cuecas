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
    .metric-value { color: #1E293B; font-size: 28px; font-weight: 700; }
    .vendedor-box { 
        background: white; padding: 16px; border-radius: 10px; 
        border: 1px solid #E2E8F0; margin-bottom: 12px; 
        display: flex; flex-direction: column; gap: 8px; width: 100%; 
    }
    .primeiro-vez { border: 2px solid #22C55E; background: #F0FDF4; }
    .stButton>button { border-radius: 8px; font-weight: 600; width: 100%; height: 40px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. FUNÇÕES DE SUPORTE ---
def get_now_br_str():
    return (datetime.now() - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M:%S')

DB_NAME = 'gestao_elite_v18.db'

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

# --- 3. LOGIN ---
if 'user' not in st.session_state: st.session_state.user = None
if not st.session_state.user:
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>🔐 Painel Casa das Cuecas</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.form("login_form"):
            u = st.text_input("Usuário:").strip().lower()
            p = st.text_input("Senha:", type="password")
            if st.form_submit_button("Entrar"):
                if u == "admin" and p == "admin@123":
                    st.session_state.user = {"nome": "Admin", "is_admin": True}; st.rerun()
                else:
                    res = run_db("SELECT * FROM usuarios WHERE login = ?", (u,), True)
                    if not res.empty:
                        st.session_state.user = {"nome": res.iloc[0]['nome'], "is_admin": False}; st.rerun()
                    else: st.error("Acesso negado.")
    st.stop()

# --- 4. KPIs ---
dados_raw = run_db("SELECT * FROM historico", is_select=True)
vendas_sucesso = dados_raw[dados_raw['evento'] == 'Sucesso']
atendimentos = dados_raw[dados_raw['evento'].isin(['Sucesso', 'Não convertido', 'Troca'])]

faturamento = vendas_sucesso['valor'].sum() if not vendas_sucesso.empty else 0
conversao = (len(vendas_sucesso) / len(atendimentos) * 100) if not atendimentos.empty else 0
pa_medio = (vendas_sucesso['itens'].sum() / len(vendas_sucesso)) if not vendas_sucesso.empty else 0

k1, k2, k3 = st.columns(3)
k1.markdown(f'<div class="metric-card">Faturamento<br><span class="metric-value">R$ {faturamento:,.2f}</span></div>', unsafe_allow_html=True)
k2.markdown(f'<div class="metric-card">Conversão<br><span class="metric-value">{conversao:.1f}%</span></div>', unsafe_allow_html=True)
k3.markdown(f'<div class="metric-card">P.A. Médio<br><span class="metric-value">{pa_medio:.2f}</span></div>', unsafe_allow_html=True)

# --- 5. OPERAÇÃO ---
t1, t2, t3 = st.tabs(["📋 FILA", "📊 DESEMPENHO", "⚙️ CONFIG"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_fila, c_atend, c_fora = st.columns(3)

    with c_fila:
        st.subheader("⏳ Na Fila")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            classe = "vendedor-box primeiro-vez" if i == 0 else "vendedor-box"
            st.markdown(f"<div class='{classe}'><b>{v['nome']}</b><br><small>{i+1}º da Vez</small></div>", unsafe_allow_html=True)
            col_a, col_b = st.columns(2)
            if col_a.button("Atender", key=f"at_{v['id']}"):
                run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],))
                st.rerun()
            if col_b.button("Sair", key=f"p_{v['id']}"):
                st.session_state[f"modal_{v['id']}"] = True
            
            if st.session_state.get(f"modal_{v['id']}", False):
                with st.expander("Motivo da Saída:", expanded=True):
                    mot = st.selectbox("Selecione:", ["Almoço", "Banheiro", "Lanche", "Finalizar dia", "Externo"], key=f"sel_{v['id']}")
                    if st.button("Confirmar", key=f"ok_{v['id']}"):
                        ev = "FINAL DE DIA" if mot == "Finalizar dia" else "SAÍDA (PAUSA)"
                        run_db("UPDATE usuarios SET status='Fora', motivo_pausa=? WHERE id=?", (mot, v['id']))
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], ev, mot, 0, 0, get_now_br_str()))
                        st.session_state[f"modal_{v['id']}"] = False; st.rerun()

    with c_atend:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container(border=True):
                st.markdown(f"**{v['nome']}**")
                if st.button("Concluir Atendimento", key=f"fin_{v['id']}", type="primary"):
                    st.session_state[f"f_{v['id']}"] = True
            
            if st.session_state.get(f"f_{v['id']}", False):
                with st.expander("Resultado do Atendimento:", expanded=True):
                    res = st.selectbox("Status:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    
                    # Campos dinâmicos baseados na escolha
                    if res == "Sucesso":
                        vlr = st.number_input("Valor R$:", min_value=0.0, key=f"v_{v['id']}")
                        it = st.number_input("Itens:", min_value=1, key=f"i_{v['id']}")
                        motivo_final = "Venda"
                    else:
                        vlr, it = 0.0, 0
                        motivo_final = st.selectbox("Motivo:", ["Preço", "Falta Tamanho", "Só olhando", "Falta Cor", "Troca"], key=f"m_{v['id']}")

                    if st.button("Salvar Registro", key=f"sv_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", 
                               (v['nome'], res, motivo_final, vlr, it, get_now_br_str()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (next_ordem(), v['id']))
                        st.session_state[f"f_{v['id']}"] = False; st.rerun()

    with c_fora:
        st.subheader("💤 Fora da Loja")
        fora = vendedores[vendedores['status'] == 'Fora']
        for _, v in fora.iterrows():
            with st.container():
                st.markdown(f"<div class='vendedor-box' style='border-left:5px solid #64748B;'><b>{v['nome']}</b><br><small>Status: {v['motivo_pausa']}</small></div>", unsafe_allow_html=True)
                if st.button(f"Retornar: {v['nome']}", key=f"ret_{v['id']}"):
                    ev = "INÍCIO DE DIA" if v['motivo_pausa'] in ["Finalizar dia", None] else "RETORNO (PAUSA)"
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], ev, v['motivo_pausa'], 0, 0, get_now_br_str()))
                    run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (next_ordem(), v['id']))
                    st.rerun()

with t2:
    st.subheader("📊 Gráficos de Vendas")
    if not atendimentos.empty:
        c1, c2 = st.columns(2)
        with c1:
            fig1 = px.bar(vendas_sucesso.groupby('vendedor')['valor'].sum().reset_index(), x='vendedor', y='valor', title="Faturamento (R$)", color='valor', color_continuous_scale='Greens')
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            fig2 = px.pie(atendimentos[atendimentos['evento'] == 'Não convertido'].groupby('motivo').size().reset_index(name='qtd'), values='qtd', names='motivo', title="Motivos de Perda", hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)
        
        st.divider()
        buffer = io.BytesIO()
        df_exp = dados_raw.sort_values(by='id', ascending=False)
        df_exp.columns = ['ID', 'Vendedor', 'Evento', 'Detalhe', 'Valor (R$)', 'Itens', 'Data/Hora']
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_exp.to_excel(writer, index=False, sheet_name='Logs')
        st.download_button("📥 Baixar Excel", data=buffer.getvalue(), file_name="Relatorio_Casa_Cuecas.xlsx")

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("⚙️ Gestão de Equipe")
        nome_n = st.text_input("Nome do Vendedor:")
        if st.button("Cadastrar"):
            if nome_n:
                log_n = nome_n.lower().replace(" ", ".")
                try:
                    run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (nome_n.title(), log_n, 'Fora', 0))
                    st.rerun()
                except: st.error("Login já existe.")
        equipe = run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True)
        for _, r in equipe.iterrows():
            cn, ce = st.columns([4, 1])
            cn.write(f"👤 **{r['nome']}**")
            if ce.button("Remover", key=f"del_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
