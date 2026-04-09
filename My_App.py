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

# --- 2. MOTOR DE DADOS ---
DB_NAME = 'banco_cuecas_v32.db'

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

# --- 3. LOGIN ---
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

# --- 4. FUNÇÃO PARA CARDS DE MÉTRICAS ---
def metricas_card(df):
    vendas = df[df['evento'] == 'Sucesso']
    atendimentos = len(df[df['evento'].isin(['Sucesso', 'Não convertido'])])
    
    faturamento = vendas['valor'].sum() if not vendas.empty else 0
    pa = (vendas['itens'].sum() / len(vendas)) if not vendas.empty else 0
    ticket = (faturamento / len(vendas)) if not vendas.empty else 0
    conv = (len(vendas) / atendimentos * 100) if atendimentos > 0 else 0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f'<div class="metric-card">Faturamento<br><b>R$ {faturamento:,.2f}</b></div>', unsafe_allow_html=True)
    m2.markdown(f'<div class="metric-card">Conversão<br><b>{conv:.1f}%</b></div>', unsafe_allow_html=True)
    m3.markdown(f'<div class="metric-card">P.A. (Peças)<br><b>{pa:.2f}</b></div>', unsafe_allow_html=True)
    m4.markdown(f'<div class="metric-card">Ticket Médio<br><b>R$ {ticket:,.2f}</b></div>', unsafe_allow_html=True)

# --- 5. TABS ---
t1, t2, t3 = st.tabs(["📋 OPERAÇÃO", "📊 DESEMPENHO & HISTÓRICO", "⚙️ EQUIPE"])

with t1:
    hoje_str = get_now_br().strftime('%Y-%m-%d')
    df_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{hoje_str}%'", is_select=True)
    meta_val = run_db("SELECT valor FROM config WHERE chave = 'meta_loja'", is_select=True).iloc[0,0]
    
    # Progresso de Meta
    fat_hoje = df_hoje[df_hoje['evento'] == 'Sucesso']['valor'].sum()
    st.markdown(f"<div class='meta-container'><h3>🎯 Meta Hoje: R$ {meta_val:,.2f} | Falta: R$ {max(meta_val-fat_hoje, 0):,.2f}</h3></div>", unsafe_allow_html=True)
    st.progress(min(fat_hoje / meta_val, 1.0) if meta_val > 0 else 0)

    # Métricas do Dia
    metricas_card(df_hoje)

    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("⏳ Na Fila")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            classe = "vendedor-box primeiro-vez" if i == 0 else "vendedor-box"
            st.markdown(f"<div class='{classe}'>👤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
            if st.button("Atender", key=f"at_{v['id']}"):
                run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()

    with c2:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            f_key = f"form_{v['id']}"
            if f_key not in st.session_state: st.session_state[f_key] = False
            with st.container(border=True):
                st.write(f"Vendedor: **{v['nome']}**")
                if st.button("Concluir", key=f"btn_f_{v['id']}"): st.session_state[f_key] = True

            if st.session_state[f_key]:
                with st.expander("📝 Detalhes", expanded=True):
                    res_at = st.selectbox("Resultado:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    if res_at == "Não convertido":
                        motivo_v = st.selectbox("Motivo:", ["Preço", "Falta Tamanho", "Só Olhando"], key=f"m_{v['id']}")
                        vlr_v, it_v = 0.0, 0
                    elif res_at == "Troca":
                        motivo_v = "Troca"; vlr_v, it_v = 0.0, 0
                    else:
                        motivo_v = "Venda"; vlr_v = st.number_input("Valor:", min_value=0.0, key=f"v_{v['id']}"); it_v = st.number_input("Itens:", min_value=1, step=1, key=f"i_{v['id']}")

                    if st.button("SALVAR", key=f"sv_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res_at, motivo_v, vlr_v, it_v, get_now_br().isoformat()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_next_ordem(), v['id']))
                        st.session_state[f_key] = False; st.rerun()

    with c3:
        st.subheader("💤 Fora")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown(f"<div class='vendedor-box'>💤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
            if st.button(f"Entrar: {v['nome']}", key=f"in_{v['id']}"):
                run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (get_next_ordem(), v['id'])); st.rerun()

with t2:
    st.subheader("📅 Relatórios e Edição")
    # Filtro de Data com Intervalo (Range)
    data_sel = st.date_input("Selecione o período:", value=(date.today() - timedelta(days=7), date.today()))
    
    if isinstance(data_sel, tuple) and len(data_sel) == 2:
        inicio, fim = data_sel
        df_f = run_db("SELECT * FROM historico WHERE date(data) BETWEEN ? AND ? ORDER BY data DESC", (inicio.isoformat(), fim.isoformat()), is_select=True)
    else:
        df_f = run_db("SELECT * FROM historico ORDER BY data DESC", is_select=True)

    if not df_f.empty:
        metricas_card(df_f)
        
        c_gr1, c_gr2 = st.columns(2)
        with c_gr1:
            st.plotly_chart(px.bar(df_f[df_f['evento']=='Sucesso'].groupby('vendedor')['valor'].sum().reset_index(), x='vendedor', y='valor', title="Vendas no Período", template="seaborn"), use_container_width=True)
        with c_gr2:
            st.plotly_chart(px.pie(df_f[df_f['evento']=='Não convertido'].groupby('motivo').size().reset_index(name='qtd'), values='qtd', names='motivo', title="Motivos de Perda", hole=0.4), use_container_width=True)

        if st.session_state.user['is_admin']:
            st.markdown("### 📝 Editor de Histórico (Adicionar/Remover)")
            # Adicionando opção de deletar na tabela
            edt = st.data_editor(df_f, hide_index=True, use_container_width=True, num_rows="dynamic")
            
            if st.button("💾 ATUALIZAR BANCO DE DADOS"):
                # Sincronização brutal: deleta o que não está no editor e insere o novo/editado
                # Para simplificar e garantir 100% de precisão:
                run_db("DELETE FROM historico WHERE id IN (SELECT id FROM historico WHERE date(data) BETWEEN ? AND ?)", (inicio.isoformat(), fim.isoformat()))
                for _, r in edt.iterrows():
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (r['vendedor'], r['evento'], r['motivo'], r['valor'], r['itens'], r['data']))
                st.success("Histórico Sincronizado!"); st.rerun()
    else: st.info("Sem dados no período.")

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("⚙️ Configurações")
        m_aj = st.number_input("Meta Diária:", value=float(meta_val))
        if st.button("Salvar Meta"):
            run_db("UPDATE config SET valor = ? WHERE chave = 'meta_loja'", (m_aj,)); st.rerun()
        st.divider()
        n_v = st.text_input("Novo Vendedor:")
        if st.button("Cadastrar"):
            if n_v: run_db("INSERT OR IGNORE INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (n_v.title(), n_v.lower().replace(" ","."), 'Fora', 0)); st.rerun()
        for _, r in run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True).iterrows():
            c1, c2 = st.columns([4, 1])
            c1.write(f"👤 {r['nome']}")
            if c2.button("Remover", key=f"rm_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
