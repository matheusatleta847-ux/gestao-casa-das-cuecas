import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import io
import plotly.express as px

# --- 1. CONFIGURAÇÃO E CSS ADAPTÁVEL ---
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

# --- 2. MOTOR DE DADOS ---
DB_NAME = 'banco_cuecas_v31.db'

def get_now_br():
    return datetime.utcnow() - timedelta(hours=3)

def run_db(query, params=(), is_select=False):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, isolation_level=None)
    try:
        if is_select: return pd.read_sql(query, conn, params=params)
        else:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
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
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>🔐 Login Casa das Cuecas</h2>", unsafe_allow_html=True)
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
                    if not res.empty: st.session_state.user = {"nome": res.iloc[0]['nome'], "is_admin": False}; st.rerun()
                    else: st.error("Acesso negado.")
    st.stop()

# --- 4. KPIs & PROGRESSO DE META ---
hoje_str = get_now_br().strftime('%Y-%m-%d')
dados_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{hoje_str}%'", is_select=True)
meta_val = run_db("SELECT valor FROM config WHERE chave = 'meta_loja'", is_select=True).iloc[0,0]

vendas_hoje = dados_hoje[dados_hoje['evento'] == 'Sucesso']
fat_hoje = vendas_hoje['valor'].sum() if not vendas_hoje.empty else 0
falta_vender = max(meta_val - fat_hoje, 0)
progresso = min(fat_hoje / meta_val, 1.0) if meta_val > 0 else 0

st.markdown(f"""
    <div class="meta-container">
        <h3 style='margin:0;'>🎯 Meta do Dia: R$ {meta_val:,.2f}</h3>
        <p style='margin:5px 0;'>Vendido: <b>R$ {fat_hoje:,.2f}</b> | Falta: <b style='color:#EF4444;'>R$ {falta_vender:,.2f}</b></p>
    </div>
""", unsafe_allow_html=True)
st.progress(progresso)

# --- 5. TABS ---
t1, t2, t3 = st.tabs(["📋 OPERAÇÃO", "📊 DESEMPENHO", "⚙️ EQUIPE"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("⏳ Na Fila")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            classe = "vendedor-box primeiro-vez" if i == 0 else "vendedor-box"
            st.markdown(f"<div class='{classe}'>👤 <b>{v['nome']}</b><br><small>{i+1}º da Vez</small></div>", unsafe_allow_html=True)
            if st.button("Atender", key=f"at_{v['id']}"):
                run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()

    with c2:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            f_key = f"form_{v['id']}"
            if f_key not in st.session_state: st.session_state[f_key] = False

            with st.container(border=True):
                st.write(f"**{v['nome']}**")
                if st.button("Concluir Atendimento", key=f"btn_f_{v['id']}"):
                    st.session_state[f_key] = True

            if st.session_state[f_key]:
                with st.expander("📝 Detalhes do Fechamento", expanded=True):
                    dt_v = st.date_input("Data:", value=date.today(), key=f"dt_{v['id']}")
                    res_at = st.selectbox("Resultado:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    
                    if res_at == "Não convertido":
                        motivo_v = st.selectbox("Motivo da Perda:", ["Preço", "Falta Tamanho", "Falta Cor", "Só Olhando"], key=f"m_{v['id']}")
                        vlr_v, it_v = 0.0, 0
                    elif res_at == "Troca":
                        motivo_v = "Troca de Mercadoria"; vlr_v, it_v = 0.0, 0
                    else:
                        motivo_v = "Venda Realizada"
                        vlr_v = st.number_input("Valor R$:", min_value=0.0, key=f"v_{v['id']}")
                        it_v = st.number_input("Qtd Itens:", min_value=1, step=1, key=f"i_{v['id']}")

                    c_b1, c_b2 = st.columns(2)
                    if c_b1.button("✅ SALVAR", key=f"sv_{v['id']}", type="primary"):
                        data_iso = datetime.combine(dt_v, datetime.now().time()).isoformat()
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", 
                               (v['nome'], res_at, motivo_v, vlr_v, it_v, data_iso))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_next_ordem(), v['id']))
                        st.session_state[f_key] = False; st.rerun()
                    if c_b2.button("❌ CANCELAR", key=f"cn_{v['id']}"):
                        st.session_state[f_key] = False; st.rerun()

    with c3:
        st.subheader("💤 Fora")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown(f"<div class='vendedor-box'>💤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
            if st.button(f"Entrar: {v['nome']}", key=f"in_{v['id']}"):
                run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (get_next_ordem(), v['id'])); st.rerun()

with t2:
    st.subheader("📊 Gráficos e Auditoria")
    ver_t = st.checkbox("🔓 Ver histórico acumulado")
    q = "SELECT * FROM historico ORDER BY data DESC" if ver_t else f"SELECT * FROM historico WHERE data LIKE '{hoje_str}%' ORDER BY data DESC"
    df_h = run_db(q, is_select=True)

    if not df_h.empty:
        c1, c2 = st.columns(2)
        with c1:
            fig1 = px.bar(df_h[df_h['evento']=='Sucesso'].groupby('vendedor')['valor'].sum().reset_index(), x='vendedor', y='valor', title="Vendas por Vendedor", template="seaborn", color='valor')
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            df_p = df_h[df_h['evento'] == 'Não convertido'].groupby('motivo').size().reset_index(name='qtd')
            if not df_p.empty:
                fig2 = px.pie(df_p, values='qtd', names='motivo', title="Motivos de Perda", hole=0.4)
                st.plotly_chart(fig2, use_container_width=True)
        
        st.markdown("### 📝 Edição de Dados")
        edt = st.data_editor(df_h, hide_index=True, use_container_width=True)
        if st.button("💾 Salvar Alterações"):
            for _, r in edt.iterrows():
                run_db("UPDATE historico SET vendedor=?, evento=?, motivo=?, valor=?, itens=?, data=? WHERE id=?", (r['vendedor'], r['evento'], r['motivo'], r['valor'], r['itens'], r['data'], r['id']))
            st.success("Dados atualizados!"); st.rerun()
    else: st.info("Sem dados para o período.")

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("⚙️ Gestão")
        m_aj = st.number_input("Meta Diária:", value=float(meta_val))
        if st.button("Salvar Meta"):
            run_db("UPDATE config SET valor = ? WHERE chave = 'meta_loja'", (m_aj,)); st.rerun()
        st.divider()
        n_v = st.text_input("Adicionar Vendedor:")
        if st.button("Cadastrar"):
            if n_v: run_db("INSERT OR IGNORE INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (n_v.title(), n_v.lower().replace(" ","."), 'Fora', 0)); st.rerun()
        for _, r in run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True).iterrows():
            c1, c2 = st.columns([4, 1])
            c1.write(f"👤 {r['nome']}")
            if c2.button("Remover", key=f"rm_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
