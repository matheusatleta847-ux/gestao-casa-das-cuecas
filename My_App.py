import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io

# --- 1. CONFIGURAÇÃO & CSS (ESTABILIDADE TOTAL) ---
st.set_page_config(page_title="PRO-Vez | Casa das Cuecas", layout="wide", page_icon="🛍️")

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

    /* Estilo de Card para evitar sobreposição vertical */
    .vendedor-box { 
        background: white; padding: 16px; border-radius: 10px; 
        border: 1px solid #E2E8F0; margin-bottom: 15px; 
        width: 100%; display: block;
    }
    .primeiro-vez { border: 2px solid #22C55E; background: #F0FDF4; }
    
    /* Botões robustos para evitar cliques sobrepostos */
    .stButton>button { border-radius: 8px; font-weight: 600; width: 100%; height: 45px; margin-top: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE DADOS & HORA BRASÍLIA ---
DB_NAME = 'gestao_casa_v21_final.db'

def get_now_br_str():
    # Ajusta o servidor (UTC) para o fuso de Brasília (UTC-3)
    br_time = datetime.utcnow() - timedelta(hours=3)
    return br_time.strftime('%d/%m/%Y %H:%M:%S')

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

# --- 3. ACESSO ---
if 'user' not in st.session_state: st.session_state.user = None

if not st.session_state.user:
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>🔐 Acesso Casa das Cuecas</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.form("login_form"):
            u = st.text_input("Login:").strip().lower()
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

# --- 4. KPIs ---
dados_raw = run_db("SELECT * FROM historico", is_select=True)
atendimentos_reais = dados_raw[dados_raw['evento'].isin(['Sucesso', 'Não convertido', 'Troca'])]

faturamento = atendimentos_reais[atendimentos_reais['evento'] == 'Sucesso']['valor'].sum() if not atendimentos_reais.empty else 0
conversao = (len(atendimentos_reais[atendimentos_reais['evento'] == 'Sucesso']) / len(atendimentos_reais) * 100) if not atendimentos_reais.empty else 0

k1, k2, k3 = st.columns(3)
k1.markdown(f'<div class="metric-card">Faturamento<br><span class="metric-value">R$ {faturamento:,.2f}</span></div>', unsafe_allow_html=True)
k2.markdown(f'<div class="metric-card">Conversão Real<br><span class="metric-value">{conversao:.1f}%</span></div>', unsafe_allow_html=True)
k3.markdown(f'<div class="metric-card">Atendimentos Totais<br><span class="metric-value">{len(atendimentos_reais)}</span></div>', unsafe_allow_html=True)

# --- 5. OPERAÇÃO (LAYOUT VERTICAL ANTI-SOBREPOSIÇÃO) ---
st.divider()
t1, t2, t3 = st.tabs(["📋 FILA", "📊 PERFORMANCE", "⚙️ CONFIGURAÇÕES"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_col1, c_col2, c_col3 = st.columns(3)

    with c_col1:
        st.subheader("⏳ Na Fila")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            classe = "vendedor-box primeiro-vez" if i == 0 else "vendedor-box"
            with st.container():
                st.markdown(f"<div class='{classe}'><b>{v['nome']}</b><br><small>{i+1}º da Vez na Fila</small></div>", unsafe_allow_html=True)
                if st.button("Atender", key=f"at_{v['id']}"):
                    run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],))
                    st.rerun()
                if st.button("Sair / Pausa", key=f"p_{v['id']}"):
                    st.session_state[f"modal_{v['id']}"] = True
                
                if st.session_state.get(f"modal_{v['id']}", False):
                    with st.expander("Justificar Saída:", expanded=True):
                        mot = st.selectbox("Selecione:", ["Almoço", "Banheiro", "Lanche", "Finalizar dia", "Externo"], key=f"sel_{v['id']}")
                        if st.button("Confirmar", key=f"ok_{v['id']}"):
                            ev = "FINAL DE DIA" if mot == "Finalizar dia" else "SAÍDA (PAUSA)"
                            run_db("UPDATE usuarios SET status='Fora', motivo_pausa=? WHERE id=?", (mot, v['id']))
                            run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], ev, mot, 0, 0, get_now_br_str()))
                            st.session_state[f"modal_{v['id']}"] = False; st.rerun()

    with c_col2:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container():
                st.markdown(f"<div class='vendedor-box'><b>{v['nome']}</b></div>", unsafe_allow_html=True)
                if st.button("Finalizar Atendimento", key=f"fin_{v['id']}", type="primary"):
                    st.session_state[f"f_{v['id']}"] = True
                
                if st.session_state.get(f"f_{v['id']}", False):
                    with st.expander("Resultado do Atendimento:", expanded=True):
                        res = st.selectbox("Status:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                        vlr = st.number_input("Valor R$:", min_value=0.0, key=f"v_{v['id']}") if res == "Sucesso" else 0.0
                        it = st.number_input("Itens:", min_value=1, key=f"i_{v['id']}") if res == "Sucesso" else 0
                        if st.button("Salvar Registro", key=f"sv_{v['id']}"):
                            run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, "Venda", vlr, it, get_now_br_str()))
                            run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (next_ordem(), v['id']))
                            st.session_state[f"f_{v['id']}"] = False; st.rerun()

    with c_col3:
        st.subheader("💤 Fora")
        fora = vendedores[vendedores['status'] == 'Fora']
        for _, v in fora.iterrows():
            with st.container():
                st.markdown(f"<div class='vendedor-box' style='border-left:5px solid #64748B;'><b>{v['nome']}</b><br><small>Status: {v['motivo_pausa']}</small></div>", unsafe_allow_html=True)
                if st.button(f"Entrar / Retornar: {v['nome']}", key=f"ret_{v['id']}"):
                    ev = "INÍCIO DE DIA" if v['motivo_pausa'] in ["Finalizar dia", None] else "RETORNO (PAUSA)"
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], ev, v['motivo_pausa'], 0, 0, get_now_br_str()))
                    run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (next_ordem(), v['id']))
                    st.rerun()

with t2:
    st.subheader("🏆 Performance & Relatórios")
    if not atendimentos_reais.empty:
        vendas_por_vendedor = atendimentos_reais[atendimentos_reais['evento'] == 'Sucesso'].groupby('vendedor')['valor'].sum()
        if not vendas_por_vendedor.empty:
            st.markdown("### Faturamento por Vendedor (R$)")
            st.bar_chart(vendas_por_vendedor)
        
        st.divider()
        df_export = dados_raw.sort_values(by='id', ascending=False)
        df_export.columns = ['ID', 'Vendedor', 'Tipo de Evento', 'Detalhe/Motivo', 'Valor da Venda', 'Itens', 'Data e Hora (SP)']
        
        buffer = io.BytesIO
