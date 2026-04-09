import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date, time
import plotly.express as px
import io

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
DB_NAME = 'banco_cuecas_v39_final.db'

def get_now_br():
    return datetime.utcnow() - timedelta(hours=3)

def run_db(query, params=(), is_select=False):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, isolation_level=None)
    try:
        if is_select:
            return pd.read_sql(query, conn, params=params)
        else:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Erro no Banco de Dados: {e}")
        return False
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
                    else: st.error("Login ou senha incorretos.")
    st.stop()

# --- 4. TABS ---
t1, t2, t3 = st.tabs(["📋 OPERAÇÃO", "📊 DESEMPENHO & HISTÓRICO", "⚙️ EQUIPE"])

with t1:
    # Cabeçalho de Meta
    res_meta = run_db("SELECT valor FROM config WHERE chave = 'meta_loja'", is_select=True)
    meta_val = res_meta.iloc[0,0] if not res_meta.empty else 5000.0
    
    hoje_str = get_now_br().strftime('%Y-%m-%d')
    df_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{hoje_str}%'", is_select=True)
    fat_hoje = df_hoje[df_hoje['evento'] == 'Sucesso']['valor'].sum() if not df_hoje.empty else 0
    
    st.markdown(f"""
        <div class="meta-container">
            <h3 style='margin:0;'>🎯 Meta: R$ {meta_val:,.2f} | Vendido Hoje: R$ {fat_hoje:,.2f}</h3>
        </div>
    """, unsafe_allow_html=True)
    st.progress(min(fat_hoje / meta_val, 1.0) if meta_val > 0 else 0)

    # Colunas de Fluxo
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("⏳ Na Fila")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            classe = "vendedor-box primeiro-vez" if i == 0 else "vendedor-box"
            st.markdown(f"<div class='{classe}'>👤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
            col_a, col_p = st.columns(2)
            if col_a.button("Atender", key=f"at_{v['id']}"):
                run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()
            if col_p.button("Pausa/Sair", key=f"ps_{v['id']}"):
                run_db("UPDATE usuarios SET status='Fora', ordem=0 WHERE id=?", (v['id'],)); st.rerun()

    with c2:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            f_key = f"form_aberto_{v['id']}"
            if f_key not in st.session_state: st.session_state[f_key] = False
            
            with st.container(border=True):
                st.write(f"**{v['nome']}**")
                if st.button("Finalizar", key=f"btn_f_{v['id']}"): st.session_state[f_key] = True

            if st.session_state[f_key]:
                with st.expander("📝 Registrar Atendimento", expanded=True):
                    res_at = st.selectbox("Resultado:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    
                    vlr_v, it_v, mot_f = 0.0, 0, res_at
                    if res_at == "Não convertido":
                        mot_f = st.selectbox("Motivo:", ["Preço", "Falta Tamanho", "Só Olhando", "Falta Cor"], key=f"mot_{v['id']}")
                    elif res_at == "Sucesso":
                        vlr_v = st.number_input("Valor R$:", min_value=0.0, key=f"v_{v['id']}")
                        it_v = st.number_input("Itens:", min_value=1, step=1, key=f"i_{v['id']}")
                        mot_f = "Venda"

                    c_b1, c_b2 = st.columns(2)
                    if c_b1.button("✅ SALVAR", key=f"sv_{v['id']}", type="primary"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", 
                               (v['nome'], res_at, mot_f, vlr_v, it_v, get_now_br().isoformat()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_next_ordem(), v['id']))
                        st.session_state[f_key] = False; st.rerun()
                    if c_b2.button("❌ CANCELAR", key=f"cn_{v['id']}"):
                        st.session_state[f_key] = False; st.rerun()

    with c3:
        st.subheader("💤 Fora")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown(f"<div class='vendedor-box'>💤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
            if st.button(f"Voltar p/ Fila: {v['nome']}", key=f"in_{v['id']}"):
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_next_ordem(), v['id'])); st.rerun()

with t2:
    st.subheader("📊 Histórico e Gestão")
    
    if st.session_state.user['is_admin']:
        with st.expander("➕ LANÇAR VENDA MANUAL (RETROATIVA)"):
            c_m1, c_m2, c_m3 = st.columns(3)
            v_m = c_m1.selectbox("Vendedor:", run_db("SELECT nome FROM usuarios", is_select=True))
            d_m = c_m2.date_input("Data da Venda:", value=date.today())
            r_m = c_m3.selectbox("Resultado:", ["Sucesso", "Não convertido", "Troca"], key="manual_r")
            v_vlr = st.number_input("R$:", min_value=0.0) if r_m == "Sucesso" else 0.0
            i_vlr = st.number_input("Itens:", min_value=1, step=1) if r_m == "Sucesso" else 0
            
            if st.button("Gravar Registro Manual"):
                # Hora fixa 12:00 para lançamentos retroativos
                dt_final = datetime.combine(d_m, time(12, 0)).isoformat()
                run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", 
                       (v_m, r_m, r_m, v_vlr, i_vlr, dt_final))
                st.success("Gravado!"); st.rerun()

    st.divider()
    dt_sel = st.date_input("Período:", value=(date.today() - timedelta(days=7), date.today()))
    
    if isinstance(dt_sel, tuple) and len(dt_sel) == 2:
        ini, fim = dt_sel
        df_f = run_db("SELECT * FROM historico WHERE date(data) BETWEEN ? AND ? ORDER BY data DESC", (ini.isoformat(), fim.isoformat()), is_select=True)
        
        if not df_f.empty:
            # Botão Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_f.to_excel(writer, index=False)
            st.download_button("📥 Baixar Planilha Excel", data=output.getvalue(), file_name=f"Relatorio_{ini}_{fim}.xlsx")

            st.plotly_chart(px.bar(df_f[df_f['evento']=='Sucesso'].groupby('vendedor')['valor'].sum().reset_index(), x='vendedor', y='valor', title="Vendas por Vendedor", color='valor'), use_container_width=True)

            if st.session_state.user['is_admin']:
                st.markdown("### 📝 Editor de Histórico (Cuidado ao Deletar)")
                edt = st.data_editor(df_f, hide_index=True, use_container_width=True, num_rows="dynamic")
                if st.button("💾 SALVAR ALTERAÇÕES (Sincronizar Banco)"):
                    run_db("DELETE FROM historico WHERE date(data) BETWEEN ? AND ?", (ini.isoformat(), fim.isoformat()))
                    for _, r in edt.iterrows():
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (r['vendedor'], r['evento'], r['motivo'], r['valor'], r['itens'], r['data']))
                    st.success("Sincronizado!"); st.rerun()

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("⚙️ Configurações")
        meta_n = st.number_input("Meta Diária:", value=float(meta_val))
        if st.button("Salvar Meta"):
            run_db("UPDATE config SET valor = ? WHERE chave = 'meta_loja'", (meta_n,)); st.success("Meta Atualizada!")
        
        st.divider()
        n_vend = st.text_input("Novo Vendedor:")
        if st.button("Cadastrar"):
            if n_vend:
                run_db("INSERT OR IGNORE INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (n_vend.title(), n_vend.lower().replace(" ","."), 'Fora', 0))
                st.rerun()
        
        for _, r in run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True).iterrows():
            c1, c2 = st.columns([4, 1])
            c1.write(f"👤 {r['nome']}")
            if c2.button("Remover", key=f"rm_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
