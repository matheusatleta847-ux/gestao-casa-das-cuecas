import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date, time
import plotly.express as px
import io

# --- 1. CONFIGURAÇÃO E CSS ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    :root { --card-bg: rgba(128, 128, 128, 0.1); --card-border: rgba(128, 128, 128, 0.2); }
    .vendedor-box, .metric-card { 
        padding: 16px; border-radius: 10px; border: 1px solid var(--card-border); 
        margin-bottom: 12px; background-color: var(--card-bg) !important; color: inherit !important; 
    }
    .meta-container { background: var(--card-bg); padding: 20px; border-radius: 15px; border: 1px solid var(--card-border); margin-bottom: 20px; text-align: center; }
    .primeiro-vez { border: 2px solid #22C55E !important; background-color: rgba(34, 197, 94, 0.15) !important; }
    .btn-pausa { color: #FFA500 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE DADOS ---
DB_NAME = 'banco_cuecas_v38.db'

def get_now_br():
    return datetime.utcnow() - timedelta(hours=3)

def run_db(query, params=(), is_select=False):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, isolation_level=None)
    try:
        if is_select: return pd.read_sql(query, conn, params=params)
        else:
            conn.execute(query, params); conn.commit()
            return True
    except Exception as e:
        st.error(f"Erro no Banco: {e}"); return False
    finally: conn.close()

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
    st.markdown("<h2 style='text-align: center;'>🔐 Login Casa das Cuecas</h2>", unsafe_allow_html=True)
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
                    else: st.error("Acesso negado.")
    st.stop()

# --- 4. TABS ---
t1, t2, t3 = st.tabs(["📋 OPERAÇÃO", "📊 DESEMPENHO & HISTÓRICO", "⚙️ EQUIPE"])

with t1:
    hoje_str = get_now_br().strftime('%Y-%m-%d')
    df_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{hoje_str}%'", is_select=True)
    meta_val = run_db("SELECT valor FROM config WHERE chave = 'meta_loja'", is_select=True).iloc[0,0]
    fat_hoje = df_hoje[df_hoje['evento'] == 'Sucesso']['valor'].sum()
    
    st.markdown(f"<div class='meta-container'><h3>🎯 Meta Hoje: R$ {meta_val:,.2f} | Vendido: R$ {fat_hoje:,.2f}</h3></div>", unsafe_allow_html=True)
    st.progress(min(fat_hoje / meta_val, 1.0) if meta_val > 0 else 0)

    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("⏳ Na Fila")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            with st.container():
                classe = "vendedor-box primeiro-vez" if i == 0 else "vendedor-box"
                st.markdown(f"<div class='{classe}'>👤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button("Atender", key=f"at_{v['id']}"):
                    run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()
                # BOTÃO PULA FILA (PAUSA)
                if col_btn2.button("Pausa/Sair", key=f"ps_{v['id']}"):
                    run_db("UPDATE usuarios SET status='Fora', ordem=0 WHERE id=?", (v['id'],)); st.rerun()

    with c2:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            f_key = f"form_{v['id']}"
            if f_key not in st.session_state: st.session_state[f_key] = False
            
            with st.container(border=True):
                st.write(f"Vendedor: **{v['nome']}**")
                if st.button("Concluir Atendimento", key=f"btn_f_{v['id']}"): st.session_state[f_key] = True

            if st.session_state[f_key]:
                with st.expander("📝 Detalhes", expanded=True):
                    res = st.selectbox("Resultado:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    vlr_in, it_in, mot_fin = 0.0, 0, res
                    
                    if res == "Não convertido":
                        mot_fin = st.selectbox("Motivo:", ["Preço", "Falta Tamanho", "Falta Cor", "Só Olhando"], key=f"mot_{v['id']}")
                    elif res == "Sucesso":
                        vlr_in = st.number_input("Valor R$:", min_value=0.0, key=f"v_{v['id']}")
                        it_in = st.number_input("Itens:", min_value=1, step=1, key=f"i_{v['id']}")
                        mot_fin = "Venda"

                    if st.button("GRAVAR", key=f"sv_{v['id']}", type="primary"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", 
                               (v['nome'], res, mot_fin, vlr_in, it_in, get_now_br().isoformat()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_next_ordem(), v['id']))
                        st.session_state[f_key] = False; st.rerun()

    with c3:
        st.subheader("💤 Fora")
        fora = vendedores[vendedores['status'] == 'Fora']
        for _, v in fora.iterrows():
            st.markdown(f"<div class='vendedor-box'>💤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
            if st.button(f"Voltar para Fila: {v['nome']}", key=f"in_{v['id']}"):
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_next_ordem(), v['id'])); st.rerun()

with t2:
    st.subheader("📊 Histórico & Excel")
    range_dt = st.date_input("Período:", value=(date.today() - timedelta(days=7), date.today()))
    
    if isinstance(range_dt, tuple) and len(range_dt) == 2:
        ini, fim = range_dt
        df_f = run_db("SELECT * FROM historico WHERE date(data) BETWEEN ? AND ? ORDER BY data DESC", (ini.isoformat(), fim.isoformat()), is_select=True)
        
        if not df_f.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_f.to_excel(writer, index=False)
            st.download_button("📥 Exportar Excel", data=buffer.getvalue(), file_name="Vendas.xlsx")

            if st.session_state.user['is_admin']:
                edt = st.data_editor(df_f, hide_index=True, use_container_width=True, num_rows="dynamic")
                if st.button("💾 Salvar Edições"):
                    run_db("DELETE FROM historico WHERE date(data) BETWEEN ? AND ?", (ini.isoformat(), fim.isoformat()))
                    for _, r in edt.iterrows():
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (r['vendedor'], r['evento'], r['motivo'], r['valor'], r['itens'], r['data']))
                    st.success("Sincronizado!"); st.rerun()
