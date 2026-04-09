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
    .vendedor-box { 
        padding: 15px; border-radius: 10px; margin-bottom: 10px; 
        background: rgba(128, 128, 128, 0.05); border: 1px solid rgba(128, 128, 128, 0.2); 
    }
    .primeiro { border: 2px solid #22C55E !important; background: rgba(34, 197, 94, 0.08) !important; }
    .stButton > button { width: 100%; height: 38px; font-weight: bold; }
    .meta-container { background: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 12px; border: 1px solid rgba(128, 128, 128, 0.2); margin-bottom: 15px; text-align: center; }
    </style>
""", unsafe_allow_html=True)

# --- 2. ENGINE DE DADOS ---
DB_NAME = 'sistema_elite_v49.db'

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

# --- 3. LOGIN ---
if 'user' not in st.session_state: st.session_state.user = None
if not st.session_state.user:
    with st.columns([1,1.2,1])[1]:
        st.title("🔐 Login Elite")
        u, p = st.text_input("Usuário").lower(), st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "admin123": st.session_state.user = {"nome":"Admin", "role":"admin"}; st.rerun()
            else: st.error("Acesso negado")
    st.stop()

tab1, tab2, tab3 = st.tabs(["🛒 Operação", "📈 Desempenho", "⚙️ Configurações"])

with tab1:
    # Dados de Meta e Hoje
    meta_loja = run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0]
    hoje_dt = get_now().strftime('%Y-%m-%d')
    df_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{hoje_dt}%'", is_select=True)
    fat_h = df_hoje[df_hoje['evento']=='Sucesso']['valor'].sum() if not df_hoje.empty else 0
    
    st.markdown(f"<div class='meta-container'><h3>🎯 Meta: R$ {meta_loja:,.2f} | Realizado: R$ {fat_h:,.2f}</h3></div>", unsafe_allow_html=True)
    st.progress(min(fat_h/meta_loja, 1.0) if meta_loja > 0 else 0.0)

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
                # Nome do Vendedor em destaque
                st.markdown(f"<div class='{cl}'>👤 <b>{v['nome'].upper()}</b></div>", unsafe_allow_html=True)
                
                # Grupo de Botões Juntos
                b_cols = st.columns([1.2, 1, 1])
                
                if is_1:
                    if b_cols[0].button("▶️ ATENDER", key=f"at_{v['id']}", type="primary"):
                        run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()
                else:
                    if b_cols[0].button("⚡ FURAR", key=f"fu_{v['id']}"):
                        st.session_state[f"fura_{v['id']}"] = True
                
                if b_cols[1].button("☕ PAUSA", key=f"ps_{v['id']}"):
                    st.session_state[f"pausa_{v['id']}"] = True

                # Interface de Justificativa (Aparece apenas se clicado)
                if st.session_state.get(f"fura_{v['id']}", False):
                    mot_f = st.selectbox("Motivo do Fura-Fila:", ["Cliente Voltou", "Atendimento Específico", "Finalização", "Troca", "Outros"], key=f"sel_f_{v['id']}")
                    c1, c2 = st.columns(2)
                    if c1.button("Confirmar", key=f"ok_f_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Fura-Fila", mot_f, 0.0, 0, get_now().isoformat()))
                        run_db("UPDATE usuarios SET status='Atendendo', ordem=? WHERE id=?", (get_min_ordem(), v['id']))
                        st.session_state[f"fura_{v['id']}"] = False; st.rerun()
                    if c2.button("Cancelar", key=f"can_f_{v['id']}"):
                        st.session_state[fura_{v['id']}] = False; st.rerun()

                if st.session_state.get(f"pausa_{v['id']}", False):
                    mot_p = st.selectbox("Tipo de Pausa:", ["Almoço", "Feedback", "Banheiro", "Café", "Outros"], key=f"sel_p_{v['id']}")
                    c1, c2 = st.columns(2)
                    if c1.button("Confirmar", key=f"ok_p_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "Pausa", mot_p, 0.0, 0, get_now().isoformat()))
                        run_db("UPDATE usuarios SET status='Pausa', ordem=0 WHERE id=?", (v['id'],))
                        st.session_state[f"pausa_{v['id']}"] = False; st.rerun()
                    if c2.button("Cancelar", key=f"can_p_{v['id']}"):
                        st.session_state[f"pausa_{v['id']}"] = False; st.rerun()

    with col_a:
        st.write("### 🚀 Atendendo")
        for _, v in vendedores[vendedores['status'] == 'Atendendo'].iterrows():
            with st.container(border=True):
                st.write(f"Vendedor: **{v['nome']}**")
                res = st.selectbox("Resultado", ["Sucesso", "Não convertido", "Troca"], key=f"r_{v['id']}")
                vlr, it, mot = 0.0, 0, res
                if res == "Sucesso":
                    vlr = st.number_input("R$:", min_value=0.0, key=f"v_{v['id']}")
                    it = st.number_input("Itens:", min_value=1, step=1, key=f"i_{v['id']}")
                elif res == "Não convertido":
                    mot = st.selectbox("Motivo:", ["Preço", "Tamanho", "Cor", "Só olhando"], key=f"m_{v['id']}")
                if st.button("Gravar Atendimento", key=f"ff_{v['id']}", type="primary"):
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, mot, vlr, it, get_now().isoformat()))
                    run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()

    with col_p:
        st.write("### ☕ Pausados")
        for _, v in vendedores[vendedores['status'] == 'Pausa'].iterrows():
            st.warning(f"👤 {v['nome']}")
            if st.button(f"Retornar à Fila: {v['nome']}", key=f"ret_{v['id']}"):
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()

with tab2:
    st.write("### 📊 Relatórios")
    # Filtro de Período
    d_r = st.date_input("Filtrar Período:", value=(date.today() - timedelta(days=7), date.today()))
    if isinstance(d_r, tuple) and len(d_r) == 2:
        df_f = run_db("SELECT * FROM historico WHERE date(data) BETWEEN ? AND ?", (d_r[0].isoformat(), d_r[1].isoformat()), is_select=True)
        if not df_f.empty:
            df_ed = st.data_editor(df_f, num_rows="dynamic", hide_index=True)
            if st.button("💾 Salvar Alterações"):
                run_db("DELETE FROM historico WHERE date(data) BETWEEN ? AND ?", (d_r[0].isoformat(), d_r[1].isoformat()))
                for _, r in df_ed.iterrows():
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (r['vendedor'], r['evento'], r['motivo'], r['valor'], r['itens'], r['data']))
                st.success("Sincronizado!"); st.rerun()
            towrite = io.BytesIO()
            df_f.to_excel(towrite, index=False, engine='xlsxwriter')
            st.download_button("📥 Baixar Excel", data=towrite.getvalue(), file_name="relatorio.xlsx")

with tab3:
    st.write("### ⚙️ Gestão")
    n_meta = st.number_input("Nova Meta Diária:", value=float(meta_loja))
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
