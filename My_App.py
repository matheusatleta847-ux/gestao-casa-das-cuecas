import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import plotly.express as px

# --- 1. CONFIGURAÇÃO PREMIUM ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide")

st.markdown("""
    <style>
    .vendedor-box { background: white; padding: 15px; border-radius: 10px; border: 1px solid #E2E8F0; margin-bottom: 12px; }
    .primeiro-vez { border: 2px solid #22C55E; background: #F0FDF4; box-shadow: 0 4px 10px rgba(34,197,94,0.1); }
    .metric-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); border-top: 4px solid #1E293B; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE DADOS ---
DB_NAME = 'gestao_elite_v16.db'

# Função para obter o horário de Brasília (UTC-3)
def get_now_br():
    return datetime.utcnow() - timedelta(hours=3)

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

# --- 3. FUNÇÃO DE ORDEM BLINDADA ---
def get_next_ordem():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.execute("SELECT MAX(ordem) FROM usuarios")
        res = cursor.fetchone()[0]
        # Tratamento rigoroso para evitar ValueError ou TypeError
        try:
            if res is None: return 1
            return int(res) + 1
        except (ValueError, TypeError):
            return 1

# --- 4. ACESSO ---
if 'user' not in st.session_state: st.session_state.user = None
if not st.session_state.user:
    st.markdown("<h2 style='text-align: center;'>🔐 Login PRO-Vez Elite</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.form("login"):
            u = st.text_input("Usuário:").strip().lower()
            p = st.text_input("Senha Admin:", type="password")
            if st.form_submit_button("Entrar"):
                if u == "admin" and p == "admin@123":
                    st.session_state.user = {"nome": "Admin", "is_admin": True}; st.rerun()
                else:
                    res = run_db("SELECT * FROM usuarios WHERE login = ?", (u,), True)
                    if not res.empty: 
                        st.session_state.user = {"nome": res.iloc[0]['nome'], "is_admin": False}
                        st.rerun()
                    else: st.error("Login inválido.")
    st.stop()

# --- 5. KPIs DE INTELIGÊNCIA ---
dados_raw = run_db("SELECT * FROM historico", is_select=True)
vendas_reais = dados_raw[dados_raw['evento'] == 'Sucesso']
atendimentos = dados_raw[dados_raw['evento'].isin(['Sucesso', 'Não convertido', 'Troca'])]

faturamento = vendas_reais['valor'].sum() if not vendas_reais.empty else 0
pa_medio = (vendas_reais['itens'].sum() / len(vendas_reais)) if not vendas_reais.empty else 0
conversao = (len(vendas_reais) / len(atendimentos) * 100) if not atendimentos.empty else 0

k1, k2, k3, k4 = st.columns(4)
k1.markdown(f'<div class="metric-card">Faturamento<br><b>R$ {faturamento:,.2f}</b></div>', unsafe_allow_html=True)
k2.markdown(f'<div class="metric-card">Conversão<br><b>{conversao:.1f}%</b></div>', unsafe_allow_html=True)
k3.markdown(f'<div class="metric-card">P.A. (Peças)<br><b>{pa_medio:.2f}</b></div>', unsafe_allow_html=True)
k4.markdown(f'<div class="metric-card">Ticket Médio<br><b>R$ {(faturamento/len(vendas_reais) if not vendas_reais.empty else 0):,.2f}</b></div>', unsafe_allow_html=True)

# --- 6. OPERAÇÃO ---
t1, t2, t3 = st.tabs(["📋 OPERAÇÃO", "📊 DASHBOARD", "⚙️ EQUIPE"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_fila, c_atend, c_fora = st.columns(3)

    with c_fila:
        st.subheader("⏳ Na Fila")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            classe = "vendedor-box primeiro-vez" if i == 0 else "vendedor-box"
            st.markdown(f"<div class='{classe}'><b>{v['nome']}</b><br><small>{i+1}º da Vez</small></div>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            if col1.button("Atender", key=f"at_{v['id']}"):
                run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],))
                st.rerun()
            if col2.button("Pausa", key=f"out_{v['id']}"):
                st.session_state[f"m_{v['id']}"] = True
            
            if st.session_state.get(f"m_{v['id']}", False):
                with st.expander("Motivo:", expanded=True):
                    mot = st.selectbox("Selecione:", ["Almoço", "Banheiro", "Lanche", "Finalizar dia"], key=f"s_{v['id']}")
                    if st.button("OK", key=f"c_{v['id']}"):
                        ev = "FINAL DE DIA" if mot == "Finalizar dia" else "SAÍDA (PAUSA)"
                        run_db("UPDATE usuarios SET status='Fora', motivo_pausa=? WHERE id=?", (mot, v['id']))
                        run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", (v['nome'], ev, mot, get_now_br().isoformat()))
                        st.session_state[f"m_{v['id']}"] = False; st.rerun()

    with c_atend:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container(border=True):
                st.write(f"**{v['nome']}**")
                if st.button("Finalizar", key=f"fin_{v['id']}"):
                    st.session_state[f"f_{v['id']}"] = True
            if st.session_state.get(f"f_{v['id']}", False):
                with st.expander("Resultado:", expanded=True):
                    res = st.selectbox("Status:", ["Sucesso", "Não convertido", "Troca"], key=f"r_{v['id']}")
                    perda = st.selectbox("Motivo Perda:", ["Preço", "Tamanho", "Só olhando", "Troca"], key=f"p_{v['id']}") if res != "Sucesso" else ""
                    vlr = st.number_input("Valor R$:", min_value=0.0, key=f"v_{v['id']}") if res == "Sucesso" else 0.0
                    it = st.number_input("Itens (P.A.):", min_value=1, step=1, key=f"i_{v['id']}") if res == "Sucesso" else 0
                    if st.button("Gravar", key=f"g_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", 
                               (v['nome'], res, perda, vlr, it, get_now_br().isoformat()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (get_next_ordem(), v['id']))
                        st.session_state[f"f_{v['id']}"] = False; st.rerun()

    with c_fora:
        st.subheader("💤 Fora")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown(f"<div class='vendedor-box'><b>{v['nome']}</b><br><small>{v['motivo_pausa']}</small></div>", unsafe_allow_html=True)
            if st.button(f"Retornar: {v['nome']}", key=f"ret_{v['id']}"):
                ev = "INÍCIO DE DIA" if v['motivo_pausa'] in ["Finalizar dia", None] else "RETORNO (PAUSA)"
                run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", (v['nome'], ev, v['motivo_pausa'], get_now_br().isoformat()))
                run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (get_next_ordem(), v['id']))
                st.rerun()

with t2:
    if not atendimentos.empty:
        c1, c2 = st.columns(2)
        with c1:
            fig1 = px.bar(vendas_reais.groupby('vendedor')['valor'].sum().reset_index(), x='vendedor', y='valor', title="Faturamento por Vendedor", color_discrete_sequence=['#22C55E'])
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            df_p = atendimentos[atendimentos['evento'] == 'Não convertido'].groupby('motivo').size().reset_index(name='qtd')
            fig2 = px.pie(df_p, values='qtd', names='motivo', title="Motivos de Perda", hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)
        
        buffer = io.BytesIO()
        df_exp = run_db("SELECT vendedor, evento, motivo, valor, itens, data FROM historico ORDER BY data DESC", is_select=True)
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_exp.to_excel(writer, index=False)
        st.download_button("📥 Baixar Relatório Excel", data=buffer.getvalue(), file_name=f"Auditoria_{get_now_br().strftime('%d_%m_%Y')}.xlsx")

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("Equipe")
        n = st.text_input("Nome:")
        if st.button("Adicionar"):
            if n:
                l = n.lower().replace(" ", ".")
                try:
                    run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (n.title(), l, 'Fora', 0))
                    st.rerun()
                except: st.error("Erro ou login já existe.")
        equipe = run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True)
        for _, r in equipe.iterrows():
            c_n, c_e = st.columns([3, 1])
            c_n.write(f"**{r['nome']}**")
            if c_e.button("Remover", key=f"del_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
