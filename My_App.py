import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import io
import plotly.express as px

# --- 1. CONFIGURAÇÃO E CSS ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    :root { --card-bg: rgba(128, 128, 128, 0.1); --card-border: rgba(128, 128, 128, 0.2); }
    .vendedor-box, .metric-card { 
        padding: 16px; border-radius: 10px; border: 1px solid var(--card-border); 
        margin-bottom: 12px; background-color: var(--card-bg) !important; color: inherit !important; 
    }
    .primeiro-vez { border: 2px solid #22C55E !important; background-color: rgba(34, 197, 94, 0.15) !important; }
    .meta-container { background: var(--card-bg); padding: 20px; border-radius: 15px; border: 1px solid var(--card-border); margin-bottom: 20px; text-align: center; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE DADOS (NOME FIXO PARA NÃO PERDER DADOS) ---
DB_NAME = 'gestao_casa_cuecas_oficial.db'

def get_now_br():
    return datetime.utcnow() - timedelta(hours=3)

def run_db(query, params=(), is_select=False):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    try:
        if is_select:
            df = pd.read_sql(query, conn, params=params)
            return df
        else:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit() # FORÇA A GRAVAÇÃO
            return True
    except Exception as e:
        st.error(f"Erro no Banco: {e}")
        return None
    finally:
        conn.close()

def init_db():
    run_db('''CREATE TABLE IF NOT EXISTS usuarios 
              (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, motivo_pausa TEXT, ordem INTEGER)''')
    run_db('''CREATE TABLE IF NOT EXISTS historico 
              (id INTEGER PRIMARY KEY, vendedor TEXT, evento TEXT, motivo TEXT, valor REAL, itens INTEGER, data TEXT)''')
    run_db('''CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor REAL)''')
    run_db("INSERT OR IGNORE INTO config (chave, valor) VALUES ('meta_loja', 5000.0)")

init_db()

def get_next_ordem():
    res = run_db("SELECT MAX(ordem) FROM usuarios", is_select=True)
    val = res.iloc[0,0] if not res.empty else 0
    return (int(val) if val is not None else 0) + 1

# --- 3. ACESSO ---
if 'user' not in st.session_state: st.session_state.user = None
if not st.session_state.user:
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>🔐 Login Casa das Cuecas</h2>", unsafe_allow_html=True)
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
                        st.session_state.user = {"nome": res.iloc[0]['nome'], "is_admin": False}; st.rerun()
                    else: st.error("Acesso negado.")
    st.stop()

# --- 4. TABS ---
t1, t2, t3 = st.tabs(["📋 OPERAÇÃO", "📊 HISTÓRICO E EDIÇÃO", "⚙️ EQUIPE"])

with t1:
    meta_val = run_db("SELECT valor FROM config WHERE chave = 'meta_loja'", is_select=True).iloc[0,0]
    st.markdown(f"<div class='meta-container'><h3>🎯 Meta Diária: R$ {meta_val:,.2f}</h3></div>", unsafe_allow_html=True)

    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("⏳ Na Fila")
        for i, v in vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True).iterrows():
            classe = "vendedor-box primeiro-vez" if i == 0 else "vendedor-box"
            st.markdown(f"<div class='{classe}'>👤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
            if st.button("Atender", key=f"at_{v['id']}"):
                run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()

    with c2:
        st.subheader("🚀 Atendendo")
        for _, v in vendedores[vendedores['status'] == 'Atendendo'].iterrows():
            with st.container(border=True):
                st.write(f"Vendedor: **{v['nome']}**")
                if st.button("Finalizar", key=f"f_{v['id']}"):
                    st.session_state[f"fin_{v['id']}"] = True
            
            if st.session_state.get(f"fin_{v['id']}", False):
                with st.expander("Registrar Venda", expanded=True):
                    dt_venda = st.date_input("Data:", value=date.today(), key=f"dt_{v['id']}")
                    res = st.selectbox("Resultado:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    vlr = st.number_input("Valor R$:", min_value=0.0, key=f"v_{v['id']}")
                    it = st.number_input("Itens:", min_value=0, step=1, key=f"i_{v['id']}")
                    
                    if st.button("GRAVAR AGORA", key=f"gv_{v['id']}"):
                        data_final = datetime.combine(dt_venda, datetime.now().time()).isoformat()
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", 
                               (v['nome'], res, res, vlr, it, data_final))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_next_ordem(), v['id']))
                        st.session_state[f"fin_{v['id']}"] = False; st.rerun()

    with c3:
        st.subheader("💤 Fora")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown(f"<div class='vendedor-box'>💤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
            if st.button(f"Entrar: {v['nome']}", key=f"in_{v['id']}"):
                run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (get_next_ordem(), v['id'])); st.rerun()

with t2:
    st.subheader("📊 Histórico de Vendas")
    ver_tudo = st.checkbox("🔓 Ver todo o histórico (sem filtro de data)")
    
    if ver_tudo:
        df_f = run_db("SELECT * FROM historico ORDER BY data DESC", is_select=True)
    else:
        hoje = date.today().strftime('%Y-%m-%d')
        df_f = run_db("SELECT * FROM historico WHERE data LIKE ? ORDER BY data DESC", (f"{hoje}%",), is_select=True)

    if not df_f.empty:
        st.write("### 📝 Tabela de Edição")
        edt = st.data_editor(df_f, hide_index=True, use_container_width=True)
        if st.button("💾 SALVAR ALTERAÇÕES"):
            for _, r in edt.iterrows():
                run_db("UPDATE historico SET vendedor=?, evento=?, valor=?, itens=?, data=? WHERE id=?", 
                       (r['vendedor'], r['evento'], r['valor'], r['itens'], r['data'], r['id']))
            st.success("✅ Salvo!"); st.rerun()
            
        fig = px.bar(df_f[df_f['evento']=='Sucesso'].groupby('vendedor')['valor'].sum().reset_index(), x='vendedor', y='valor', title="Vendas do Período")
        st.plotly_chart(fig)
    else:
        st.warning("Nenhum dado encontrado para hoje. Use a aba OPERAÇÃO para lançar ou marque 'Ver todo o histórico'.")

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("⚙️ Configurações")
        m = st.number_input("Meta Diária:", value=meta_val)
        if st.button("Salvar Meta"):
            run_db("UPDATE config SET valor = ? WHERE chave = 'meta_loja'", (m,))
            st.rerun()
        
        st.divider()
        n = st.text_input("Vendedor:")
        if st.button("Adicionar"):
            if n:
                run_db("INSERT OR IGNORE INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", 
                       (n.title(), n.lower().replace(" ","."), 'Fora', 0))
                st.rerun()
        
        for _, r in run_db("SELECT * FROM usuarios", is_select=True).iterrows():
            c1, c2 = st.columns([3, 1])
            c1.write(f"👤 {r['nome']}")
            if c2.button("Remover", key=f"rem_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
