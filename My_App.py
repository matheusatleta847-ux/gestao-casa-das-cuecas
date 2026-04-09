import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import io
import plotly.express as px

# --- 1. CONFIGURAÇÃO PREMIUM & CSS ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide", page_icon="📈")

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

# --- 2. MOTOR DE DADOS ---
DB_NAME = 'gestao_elite_v24.db'

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
    run_db('''CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor REAL)''')
    try: run_db("INSERT OR IGNORE INTO config (chave, valor) VALUES ('meta_loja', 5000.0)")
    except: pass

init_db()

def get_next_ordem():
    with sqlite3.connect(DB_NAME) as conn:
        res = conn.execute("SELECT MAX(ordem) FROM usuarios").fetchone()[0]
        return (int(res) if res is not None else 0) + 1

# --- 3. ACESSO ---
if 'user' not in st.session_state: st.session_state.user = None
if not st.session_state.user:
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>🔐 Login PRO-Vez Elite</h2>", unsafe_allow_html=True)
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
                    else: st.error("Login inválido.")
    st.stop()

# --- 4. INTERFACE ---
t1, t2, t3 = st.tabs(["📋 OPERAÇÃO", "📊 DESEMPENHO & CALENDÁRIO", "⚙️ EQUIPE"])

with t1:
    hoje_str = get_now_br().strftime('%Y-%m-%d')
    dados_hoje = run_db("SELECT * FROM historico WHERE data LIKE ?", (f"{hoje_str}%",), is_select=True)
    meta_val = run_db("SELECT valor FROM config WHERE chave = 'meta_loja'", is_select=True).iloc[0]['valor']
    vendas_hoje = dados_hoje[dados_hoje['evento'] == 'Sucesso']
    fat_hoje = vendas_hoje['valor'].sum() if not vendas_hoje.empty else 0
    
    st.markdown(f"<div class='meta-container'><h3 style='margin:0;'>🎯 Meta Diária: R$ {meta_val:,.2f} | Vendido: R$ {fat_hoje:,.2f}</h3></div>", unsafe_allow_html=True)
    st.progress(min(fat_hoje / meta_val, 1.0) if meta_val > 0 else 0)

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
                if st.button("Concluir", key=f"f_{v['id']}"):
                    st.session_state[f"fin_{v['id']}"] = True
            if st.session_state.get(f"fin_{v['id']}", False):
                with st.expander("Dados:", expanded=True):
                    res = st.selectbox("Resultado:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    vlr = st.number_input("Valor:", min_value=0.0, key=f"v_{v['id']}") if res == "Sucesso" else 0.0
                    it = st.number_input("Itens:", min_value=1, step=1, key=f"i_{v['id']}") if res == "Sucesso" else 0
                    if st.button("Salvar", key=f"gv_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, res, vlr, it, get_now_br().isoformat()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_next_ordem(), v['id'])); st.rerun()

    with c3:
        st.subheader("💤 Fora")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown(f"<div class='vendedor-box'>💤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
            if st.button(f"Entrar: {v['nome']}", key=f"in_{v['id']}"):
                run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (get_next_ordem(), v['id'])); st.rerun()

with t2:
    st.subheader("📅 Relatório por Período")
    # Calendário Corrigido
    data_sel = st.date_input("Escolha a data ou arraste para selecionar um período:", value=date.today())
    
    # Lógica de filtro blindada
    if isinstance(data_sel, date):
        dt_str = data_sel.strftime('%Y-%m-%d')
        df_f = run_db("SELECT * FROM historico WHERE data LIKE ?", (f"{dt_str}%",), is_select=True)
    elif isinstance(data_sel, tuple) and len(data_sel) == 2:
        inicio, fim = data_sel
        df_f = run_db("SELECT * FROM historico WHERE date(data) BETWEEN ? AND ?", (inicio.isoformat(), fim.isoformat()), is_select=True)
    else:
        df_f = run_db("SELECT * FROM historico", is_select=True)

    if not df_f.empty:
        vendas = df_f[df_f['evento'] == 'Sucesso']
        c1, c2, c3 = st.columns(3)
        c1.metric("Vendido no Período", f"R$ {vendas['valor'].sum():,.2f}")
        c2.metric("Atendimentos", len(df_f))
        c3.metric("Conversão", f"{(len(vendas)/len(df_f)*100):.1f}%" if len(df_f)>0 else "0%")

        fig = px.bar(vendas.groupby('vendedor')['valor'].sum().reset_index(), x='vendedor', y='valor', title="Desempenho por Vendedor", template="seaborn")
        st.plotly_chart(fig, use_container_width=True)

        if st.session_state.user['is_admin']:
            st.markdown("### 📝 Editar Registros")
            edt = st.data_editor(df_f, hide_index=True, use_container_width=True)
            if st.button("Salvar Edições"):
                for _, r in edt.iterrows():
                    run_db("UPDATE historico SET vendedor=?, evento=?, valor=?, itens=? WHERE id=?", (r['vendedor'], r['evento'], r['valor'], r['itens'], r['id']))
                st.success("Atualizado!"); st.rerun()
    else:
        st.info("Nenhum dado encontrado para esta seleção.")

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("⚙️ Configurações")
        m = st.number_input("Meta Diária:", value=meta_val)
        if st.button("Salvar Meta"):
            run_db("UPDATE config SET valor = ? WHERE chave = 'meta_loja'", (m,))
            st.success("Meta salva!")
        
        st.divider()
        n = st.text_input("Novo Vendedor:")
        if st.button("Adicionar"):
            if n:
                login = n.lower().replace(" ", ".")
                check = run_db("SELECT * FROM usuarios WHERE login = ?", (login,), is_select=True)
                if check.empty:
                    run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (n.title(), login, 'Fora', 0))
                    st.rerun()
                else: st.error("Vendedor já existe!")
        
        for _, r in run_db("SELECT * FROM usuarios", is_select=True).iterrows():
            c1, c2 = st.columns([3, 1])
            c1.write(f"👤 {r['nome']}")
            if c2.button("Remover", key=f"rem_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
