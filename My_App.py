import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date, time
import plotly.express as px
import io

# --- 1. CONFIGURAÇÃO E CSS ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide")

st.markdown("""
    <style>
    .metric-card { padding: 15px; border-radius: 10px; border: 1px solid rgba(128,128,128,0.2); background: rgba(128,128,128,0.05); text-align: center; }
    .vendedor-box { padding: 10px; border-radius: 8px; margin-bottom: 5px; background: rgba(128,128,128,0.1); border: 1px solid rgba(128,128,128,0.2); }
    .primeiro { border: 2px solid #22C55E !important; background: rgba(34,197,94,0.1) !important; }
    .meta-container { background: rgba(128,128,128,0.05); padding: 15px; border-radius: 12px; border: 1px solid rgba(128,128,128,0.2); margin-bottom: 15px; text-align: center; }
    .stButton > button { width: 100%; padding: 2px; font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. ENGINE DE DADOS ---
DB_NAME = 'sistema_elite_v48.db'

def run_db(query, params=(), is_select=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        try:
            if is_select: return pd.read_sql(query, conn, params=params)
            conn.execute(query, params); conn.commit()
            return True
        except Exception: return False

def init_db():
    run_db("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, ordem INTEGER)")
    run_db("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, vendedor TEXT, evento TEXT, motivo TEXT, valor REAL, itens INTEGER, data TEXT)")
    run_db("CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor REAL)")
    run_db("INSERT OR IGNORE INTO config VALUES ('meta_loja', 5000.0)")

init_db()

def get_now(): return datetime.now() - timedelta(hours=3)
def get_max_ordem(): 
    res = run_db("SELECT MAX(ordem) FROM usuarios", is_select=True).iloc[0,0]
    return (int(res) if res else 0) + 1
def get_min_ordem(): 
    res = run_db("SELECT MIN(ordem) FROM usuarios WHERE status='Esperando'", is_select=True).iloc[0,0]
    return (int(res) if res else 0) - 1

# --- 3. INDICADORES ---
def exibir_indicadores(df):
    if df.empty: return
    vendas = df[df['evento'] == 'Sucesso']
    total_fat = vendas['valor'].sum()
    atend = len(df[df['evento'].isin(['Sucesso', 'Não convertido'])])
    pa = vendas['itens'].sum() / len(vendas) if not vendas.empty else 0
    tm = total_fat / len(vendas) if not vendas.empty else 0
    conv = (len(vendas) / atend * 100) if atend > 0 else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Faturamento", f"R$ {total_fat:,.2f}")
    c2.metric("📈 Conversão", f"{conv:.1f}%")
    c3.metric("📦 P.A.", f"{pa:.2f}")
    c4.metric("🎫 Ticket Médio", f"R$ {tm:,.2f}")

# --- 4. LOGIN ---
if 'user' not in st.session_state: st.session_state.user = None
if not st.session_state.user:
    with st.columns([1,1.2,1])[1]:
        st.title("🔐 Login")
        u, p = st.text_input("Usuário").lower(), st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "admin123": st.session_state.user = {"nome":"Admin", "role":"admin"}; st.rerun()
            else: st.error("Acesso negado")
    st.stop()

tab1, tab2, tab3 = st.tabs(["🛒 Operação", "📈 Desempenho", "⚙️ Configurações"])

with tab1:
    meta_loja = run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0]
    df_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{get_now().strftime('%Y-%m-%d')}%'", is_select=True)
    fat_h = df_hoje[df_hoje['evento']=='Sucesso']['valor'].sum() if not df_hoje.empty else 0
    st.markdown(f"<div class='meta-container'><h3>🎯 Meta: R$ {meta_loja:,.2f} | Realizado: R$ {fat_h:,.2f}</h3></div>", unsafe_allow_html=True)
    st.progress(min(fat_h/meta_loja, 1.0) if meta_loja > 0 else 0.0)
    exibir_indicadores(df_hoje)

    st.divider()
    col_f, col_a, col_p = st.columns(3)
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)

    with col_f:
        st.write("### ⏳ Fila de Vez")
        fila = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for idx, v in fila.iterrows():
            is_1 = (idx == 0)
            cl = "vendedor-box primeiro" if is_1 else "vendedor-box"
            
            with st.container():
                st.markdown(f"<div class='{cl}'>👤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
                btn_cols = st.columns([1, 1, 1])
                
                if is_1:
                    if btn_cols[0].button("Atender", key=f"at_{v['id']}", type="primary"):
                        run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()
                else:
                    if btn_cols[0].button("⚡ Furar", key=f"fu_{v['id']}"):
                        st.session_state[f"f_{v['id']}"] = True
                
                if btn_cols[1].button("☕ Pausa", key=f"ps_{v['id']}"):
                    st.session_state[f"p_{v['id']}"] = True

                # --- RESPOSTAS PRÉ-DEFINIDAS NO FURA-FILA ---
                if st.session_state.get(f"f_{v['id']}", False):
                    with st.expander("⚡ Justificativa Fura-Fila", expanded=True):
                        mot_f = st.selectbox("Selecione o Motivo:", 
                                            ["Cliente Voltou", "Atendimento Específico", "Finalização de Venda", "Troca Rápida", "Outros"], 
                                            key=f"sm_f_{v['id']}")
                        if st.button("Confirmar Prioridade", key=f"cfm_f_{v['id']}"):
                            run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Fura-Fila", mot_f, 0.0, 0, get_now().isoformat()))
                            run_db("UPDATE usuarios SET status='Atendendo', ordem=? WHERE id=?", (get_min_ordem(), v['id']))
                            st.session_state[f"f_{v['id']}"] = False; st.rerun()

                if st.session_state.get(f"p_{v['id']}", False):
                    with st.expander("☕ Motivo Pausa", expanded=True):
                        mot_p = st.selectbox("Tipo:", ["Almoço", "Feedback", "Banheiro", "Café/Lanche", "Outros"], key=f"sm_p_{v['id']}")
                        if st.button("Confirmar Pausa", key=f"cfm_p_{v['id']}"):
                            run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Pausa", mot_p, 0.0, 0, get_now().isoformat()))
                            run_db("UPDATE usuarios SET status='Pausa', ordem=0 WHERE id=?", (v['id'],))
                            st.session_state[f"p_{v['id']}"] = False; st.rerun()

    with col_a:
        st.write("### 🚀 Atendendo")
        for _, v in vendedores[vendedores['status'] == 'Atendendo'].iterrows():
            with st.expander(f"Finalizar: {v['nome']}", expanded=True):
                res = st.selectbox("Resultado", ["Sucesso", "Não convertido", "Troca"], key=f"r_{v['id']}")
                vlr, it, mot = 0.0, 0, res
                if res == "Sucesso":
                    vlr = st.number_input("R$:", min_value=0.0, key=f"v_{v['id']}")
                    it = st.number_input("Itens:", min_value=1, step=1, key=f"i_{v['id']}")
                elif res == "Não convertido":
                    mot = st.selectbox("Motivo:", ["Preço", "Tamanho", "Cor", "Só olhando"], key=f"m_{v['id']}")
                if st.button("✅ Concluir", key=f"ff_{v['id']}"):
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, mot, vlr, it, get_now().isoformat()))
                    run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()

    with col_p:
        st.write("### ☕ Pausados")
        for _, v in vendedores[vendedores['status'] == 'Pausa'].iterrows():
            st.warning(f"👤 {v['nome']}")
            if st.button(f"Retornar: {v['nome']}", key=f"ret_{v['id']}"):
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()

with tab2:
    st.write("### 📊 Gestão e Histórico")
    # ... (Seção de Lançamento Manual e Editor de Dados idêntica à v47 para manter estabilidade)
    with st.expander("➕ Lançamento Manual"):
        with st.form("f_man"):
            m_v = st.selectbox("Vendedor", run_db("SELECT nome FROM usuarios", is_select=True))
            m_d, m_r = st.date_input("Data"), st.selectbox("Tipo", ["Sucesso", "Não convertido", "Troca"])
            m_vlr = st.number_input("R$", min_value=0.0) if m_r == "Sucesso" else 0.0
            m_it = st.number_input("Itens", min_value=0, step=1) if m_r == "Sucesso" else 0
            if st.form_submit_button("Salvar"):
                run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (m_v, m_r, m_r, m_vlr, m_it, datetime.combine(m_d, time(12, 0)).isoformat()))
                st.success("Salvo!"); st.rerun()
    
    d_r = st.date_input("Filtrar Período:", value=(date.today() - timedelta(days=7), date.today()))
    if isinstance(d_r, tuple) and len(d_r) == 2:
        df_f = run_db("SELECT * FROM historico WHERE date(data) BETWEEN ? AND ?", (d_r[0].isoformat(), d_r[1].isoformat()), is_select=True)
        if not df_f.empty:
            exibir_indicadores(df_f)
            df_ed = st.data_editor(df_f, num_rows="dynamic", hide_index=True)
            if st.button("💾 Salvar Alterações"):
                run_db("DELETE FROM historico WHERE date(data) BETWEEN ? AND ?", (d_r[0].isoformat(), d_r[1].isoformat()))
                for _, r in df_ed.iterrows():
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (r['vendedor'], r['evento'], r['motivo'], r['valor'], r['itens'], r['data']))
                st.success("Sincronizado!"); st.rerun()
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: df_f.to_excel(writer, index=False)
            st.download_button("📥 Baixar Excel", data=buffer.getvalue(), file_name="relatorio_final.xlsx")

with tab3:
    n_meta = st.number_input("Meta Diária:", value=float(meta_loja))
    if st.button("Salvar Meta"): run_db("UPDATE config SET valor=? WHERE chave='meta_loja'", (n_meta,)); st.rerun()
    st.divider()
    with st.form("add_v"):
        nn = st.text_input("Novo Vendedor")
        if st.form_submit_button("Cadastrar"):
            run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (nn, nn.lower(), 'Esperando', get_max_ordem())); st.rerun()
    for _, r in run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True).iterrows():
        c1, c2 = st.columns([4,1])
        c1.write(f"👤 {r['nome']}")
        if c2.button("Remover", key=f"rm_{r['id']}"): run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
