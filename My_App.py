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

# --- 2. BANCO DE DADOS (Adicionando coluna de itens) ---
DB_NAME = 'gestao_elite_v14.db'

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

# --- 3. ACESSO ---
if 'user' not in st.session_state: st.session_state.user = None
if not st.session_state.user:
    # (Mesmo bloco de login anterior...)
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
                    if not res.empty: st.session_state.user = {"nome": res.iloc[0]['nome'], "is_admin": False}; st.rerun()
                    else: st.error("Login inválido.")
    st.stop()

# --- 4. KPIs DE INTELIGÊNCIA ---
dados_raw = run_db("SELECT * FROM historico WHERE data >= ?", 
                   ((datetime.now() - timedelta(days=30)).isoformat(),), True)

vendas_reais = dados_raw[dados_raw['evento'] == 'Sucesso']
atendimentos = dados_raw[dados_raw['evento'].isin(['Sucesso', 'Não convertido', 'Troca'])]

faturamento = vendas_reais['valor'].sum() if not vendas_reais.empty else 0
pa_medio = (vendas_reais['itens'].sum() / len(vendas_reais)) if not vendas_reais.empty else 0
conversao = (len(vendas_reais) / len(atendimentos) * 100) if not atendimentos.empty else 0

k1, k2, k3, k4 = st.columns(4)
k1.markdown(f'<div class="metric-card">Faturamento Mensal<br><b>R$ {faturamento:,.2f}</b></div>', unsafe_allow_html=True)
k2.markdown(f'<div class="metric-card">Conversão Real<br><b>{conversao:.1f}%</b></div>', unsafe_allow_html=True)
k3.markdown(f'<div class="metric-card">P.A. (Itens/Venda)<br><b>{pa_medio:.2f}</b></div>', unsafe_allow_html=True)
k4.markdown(f'<div class="metric-card">Ticket Médio<br><b>R$ {(faturamento/len(vendas_reais) if not vendas_reais.empty else 0):,.2f}</b></div>', unsafe_allow_html=True)

# --- 5. OPERAÇÃO ---
t1, t2, t3 = st.tabs(["📋 OPERAÇÃO (FILA)", "📊 INTELIGÊNCIA (DASHBOARD)", "⚙️ EQUIPE"])

with t1:
    # (Lógica da Fila idêntica à v13, mas no fechamento da venda adicionamos o campo 'itens')
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_fila, c_atend, c_fora = st.columns(3)

    def get_next_ordem():
        res = run_db("SELECT MAX(ordem) FROM usuarios", is_select=True)
        return (res.iloc[0,0] if res.iloc[0,0] is not None else 0) + 1

    with c_fila:
        st.subheader("⏳ Na Vez")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            classe = "vendedor-box primeiro-vez" if i == 0 else "vendedor-box"
            st.markdown(f"<div class='{classe}'><b>{v['nome']}</b><br><small>{i+1}º da Vez</small></div>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            if col1.button("Atender", key=f"at_{v['id']}"):
                run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],))
                st.rerun()
            if col2.button("Pausa/Sair", key=f"out_{v['id']}"):
                st.session_state[f"m_{v['id']}"] = True
            
            if st.session_state.get(f"m_{v['id']}", False):
                with st.expander("Justificar:", expanded=True):
                    mot = st.selectbox("Motivo:", ["Almoço", "Banheiro", "Lanche", "Finalizar dia"], key=f"s_{v['id']}")
                    if st.button("Confirmar", key=f"c_{v['id']}"):
                        ev = "FINAL DE DIA" if mot == "Finalizar dia" else "SAÍDA (PAUSA)"
                        run_db("UPDATE usuarios SET status='Fora', motivo_pausa=? WHERE id=?", (mot, v['id']))
                        run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", (v['nome'], ev, mot, datetime.now().isoformat()))
                        st.session_state[f"m_{v['id']}"] = False; st.rerun()

    with c_atend:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container(border=True):
                st.write(f"**{v['nome']}**")
                if st.button("Concluir Atendimento", key=f"fin_{v['id']}"):
                    st.session_state[f"f_{v['id']}"] = True
            if st.session_state.get(f"f_{v['id']}", False):
                with st.expander("Dados da Venda:", expanded=True):
                    res = st.selectbox("Resultado:", ["Sucesso", "Não convertido", "Troca"], key=f"r_{v['id']}")
                    vlr = st.number_input("Valor R$:", min_value=0.0, key=f"v_{v['id']}") if res == "Sucesso" else 0.0
                    it = st.number_input("Qtd Itens:", min_value=1, key=f"i_{v['id']}") if res == "Sucesso" else 0
                    if st.button("Gravar", key=f"g_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, valor, itens, data) VALUES (?,?,?,?,?)", (v['nome'], res, vlr, it, datetime.now().isoformat()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_next_ordem(), v['id']))
                        st.session_state[f"f_{v['id']}"] = False; st.rerun()

    with c_fora:
        st.subheader("💤 Fora da Loja")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown(f"<div class='vendedor-box'><b>{v['nome']}</b><br><small>{v['motivo_pausa']}</small></div>", unsafe_allow_html=True)
            if st.button(f"Entrar: {v['nome']}", key=f"ret_{v['id']}"):
                ev = "INÍCIO DE DIA" if v['motivo_pausa'] in ["Finalizar dia", None] else "RETORNO (PAUSA)"
                run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", (v['nome'], ev, v['motivo_pausa'], datetime.now().isoformat()))
                run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (get_next_ordem(), v['id']))
                st.rerun()

with t2:
    st.subheader("📊 Dashboards de Performance")
    if not atendimentos.empty:
        c_g1, c_g2 = st.columns(2)
        
        with c_g1:
            # Gráfico de Faturamento Interativo
            df_f = vendas_reais.groupby('vendedor')['valor'].sum().reset_index()
            fig1 = px.bar(df_f, x='vendedor', y='valor', title="Faturamento por Vendedor (R$)", color='valor', color_continuous_scale='Greens')
            st.plotly_chart(fig1, use_container_width=True)
            
        with c_g2:
            # Gráfico de Motivos de Perda
            df_p = atendimentos[atendimentos['evento'] == 'Não convertido'].groupby('motivo').size().reset_index(name='qtd')
            fig2 = px.pie(df_p, values='qtd', names='motivo', title="Motivos de Perda de Venda", hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()
        # Botão Excel... (mesma lógica anterior)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            dados_raw.to_excel(writer, index=False)
        st.download_button("📥 Baixar Auditoria Completa (.xlsx)", data=buffer.getvalue(), file_name="Auditoria_Elite.xlsx")
    else: st.info("Aguardando dados...")

with t3:
    # (Lógica de Gestão de Equipe v13...)
    if st.session_state.user['is_admin']:
        st.subheader("Equipe")
        n_nv = st.text_input("Nome:")
        if st.button("Adicionar"):
            if n_nv:
                l_nv = n_nv.lower().replace(" ", ".")
                try:
                    run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (n_nv.title(), l_nv, 'Fora', 0))
                    st.rerun()
                except: st.error("Existe!")
        equipe = run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True)
        for _, r in equipe.iterrows():
            c_n, c_e = st.columns([3, 1])
            c_n.write(f"**{r['nome']}**")
            if c_e.button("Remover", key=f"del_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
