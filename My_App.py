import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date, time
import plotly.express as px
import io

# --- 1. CONFIGURAÇÃO E INTERFACE ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide")

st.markdown("""
    <style>
    .metric-card { 
        padding: 15px; border-radius: 10px; border: 1px solid rgba(128,128,128,0.2); 
        background: rgba(128,128,128,0.05); text-align: center;
    }
    .vendedor-box { 
        padding: 12px; border-radius: 8px; margin-bottom: 10px; 
        background: rgba(128,128,128,0.1); border: 1px solid rgba(128,128,128,0.2);
    }
    .primeiro { border: 2px solid #22C55E !important; background: rgba(34,197,94,0.1) !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. ENGINE DE DADOS ---
DB_NAME = 'sistema_elite_v42.db'

def run_db(query, params=(), is_select=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        if is_select: return pd.read_sql(query, conn, params=params)
        conn.execute(query, params)
        conn.commit()

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
def calcular_indicadores(df):
    if df.empty: return 0.0, 0.0, 0.0, 0.0
    vendas = df[df['evento'] == 'Sucesso']
    total_fat = vendas['valor'].sum()
    total_atend = len(df[df['evento'].isin(['Sucesso', 'Não convertido'])])
    
    pa = vendas['itens'].sum() / len(vendas) if not vendas.empty else 0
    tm = total_fat / len(vendas) if not vendas.empty else 0
    conv = (len(vendas) / total_atend * 100) if total_atend > 0 else 0
    return total_fat, pa, tm, conv

# --- 4. LOGIN ---
if 'user' not in st.session_state: st.session_state.user = None

if not st.session_state.user:
    with st.columns([1,1,1])[1]:
        st.title("🔐 Acesso")
        u = st.text_input("Usuário").lower()
        p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "admin123": 
                st.session_state.user = {"nome":"Admin", "role":"admin"}
                st.rerun()
            else: st.error("Dados inválidos")
    st.stop()

tab1, tab2, tab3 = st.tabs(["🛒 Operação", "📈 Desempenho", "⚙️ Equipe & Metas"])

with tab1:
    meta_loja = run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0]
    hoje = get_now().strftime('%Y-%m-%d')
    df_hoje = run_db(f"SELECT * FROM historico WHERE data LIKE '{hoje}%'", is_select=True)
    fat_h, pa_h, tm_h, conv_h = calcular_indicadores(df_hoje)

    st.subheader(f"🎯 Meta: R$ {meta_loja:,.2f} | Realizado: R$ {fat_h:,.2f}")
    st.progress(min(fat_h/meta_loja, 1.0) if meta_loja > 0 else 0.0)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Faturamento", f"R$ {fat_h:,.2f}")
    c2.metric("P.A.", f"{pa_h:.2f}")
    c3.metric("Ticket Médio", f"R$ {tm_h:,.2f}")
    c4.metric("Conversão", f"{conv_h:.1f}%")

    st.divider()
    col_fila, col_acao, col_pausa = st.columns(3)
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)

    with col_fila:
        st.write("### ⏳ Fila de Vez")
        fila = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for idx, v in fila.iterrows():
            estilo = "vendedor-box primeiro" if idx == 0 else "vendedor-box"
            st.markdown(f"<div class='{estilo}'><b>{v['nome']}</b></div>", unsafe_allow_html=True)
            col_b1, col_b2 = st.columns(2)
            if col_b1.button("Atender", key=f"at_{v['id']}"):
                run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],)); st.rerun()
            if col_b2.button("☕ Pausa", key=f"ps_{v['id']}"):
                run_db("UPDATE usuarios SET status='Pausa', ordem=0 WHERE id=?", (v['id'],)); st.rerun()

    with col_acao:
        st.write("### 🚀 Em Atendimento")
        atendendo = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atendendo.iterrows():
            with st.expander(f"Finalizar: {v['nome']}", expanded=True):
                res = st.selectbox("Resultado", ["Sucesso", "Não convertido", "Troca"], key=f"r_{v['id']}")
                vlr, it, mot = 0.0, 0, res
                if res == "Sucesso":
                    vlr = st.number_input("Valor R$", min_value=0.0, key=f"v_{v['id']}")
                    it = st.number_input("Peças", min_value=1, step=1, key=f"i_{v['id']}")
                elif res == "Não convertido":
                    mot = st.selectbox("Motivo", ["Preço", "Tamanho", "Cor", "Só olhando"], key=f"m_{v['id']}")
                
                c_f1, c_f2 = st.columns(2)
                if c_f1.button("✅ Final de Fila", key=f"ff_{v['id']}"):
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, mot, vlr, it, get_now().isoformat()))
                    run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id']))
                    st.rerun()
                if c_f2.button("⚡ Furar Fila", key=f"fur_{v['id']}"):
                    run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, f"{mot} (Fura-Fila)", vlr, it, get_now().isoformat()))
                    run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_min_ordem(), v['id']))
                    st.rerun()

    with col_pausa:
        st.write("### ☕ Em Intervalo")
        pausados = vendedores[vendedores['status'] == 'Pausa']
        for _, v in pausados.iterrows():
            st.warning(f"{v['nome']} em pausa")
            if st.button(f"Voltar p/ Fila: {v['nome']}", key=f"ret_{v['id']}"):
                run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem(), v['id'])); st.rerun()

with tab2:
    st.write("### 📊 Gestão de Resultados")
    
    # --- NOVO: LANÇAMENTO MANUAL DIRETO ---
    with st.expander("➕ Inserir Venda Manualmente (Sem Fila)"):
        with st.form("manual_entry"):
            c_m1, c_m2, c_m3 = st.columns(3)
            v_man = c_m1.selectbox("Vendedor", run_db("SELECT nome FROM usuarios", is_select=True))
            d_man = c_m2.date_input("Data", value=date.today())
            res_man = c_m3.selectbox("Tipo", ["Sucesso", "Não convertido", "Troca"])
            
            v_vlr = st.number_input("Valor R$", min_value=0.0) if res_man == "Sucesso" else 0.0
            v_it = st.number_input("Itens", min_value=0, step=1) if res_man == "Sucesso" else 0
            
            if st.form_submit_button("Gravar no Histórico"):
                data_f = datetime.combine(d_man, time(12, 0)).isoformat()
                run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v_man, res_man, res_man, v_vlr, v_it, data_f))
                st.success("Gravado com sucesso!"); st.rerun()

    st.divider()
    dt_ini = st.date_input("Início", value=date.today() - timedelta(days=7))
    dt_fim = st.date_input("Fim", value=date.today())
    
    df_filt = run_db("SELECT * FROM historico WHERE date(data) BETWEEN ? AND ?", (dt_ini.isoformat(), dt_fim.isoformat()), is_select=True)
    
    if not df_filt.empty:
        f_p, pa_p, tm_p, c_p = calcular_indicadores(df_filt)
        st.write(f"**Métricas do Período:** Fat: R$ {f_p:,.2f} | PA: {pa_p:.2f} | Ticket: R$ {tm_p:,.2f} | Conv: {c_p:.1f}%")
        
        st.write("#### 📝 Planilha de Registros (Edite ou Adicione Linhas)")
        df_edit = st.data_editor(df_filt, num_rows="dynamic", hide_index=True, key="editor_hist_final")
        
        if st.button("💾 Salvar Alterações na Planilha"):
            run_db("DELETE FROM historico WHERE date(data) BETWEEN ? AND ?", (dt_ini.isoformat(), dt_fim.isoformat()))
            for _, r in df_edit.iterrows():
                run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (r['vendedor'], r['evento'], r['motivo'], r['valor'], r['itens'], r['data']))
            st.success("Banco de dados atualizado!"); st.rerun()
            
        try:
            towrite = io.BytesIO()
            df_filt.to_excel(towrite, index=False, engine='xlsxwriter')
            st.download_button("📥 Baixar Planilha Excel", data=towrite.getvalue(), file_name="relatorio_casa_cuecas.xlsx")
        except:
            st.info("Nota: Requer 'xlsxwriter' para exportar Excel.")

with tab3:
    st.write("### ⚙️ Configurações de Equipe")
    with st.form("add_v"):
        n_v = st.text_input("Nome do Vendedor")
        if st.form_submit_button("Cadastrar Novo"):
            run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (n_v, n_v.lower(), 'Esperando', get_max_ordem()))
            st.rerun()
    
    st.divider()
    st.write("### 🎯 Meta Diária")
    meta_loja = run_db("SELECT valor FROM config WHERE chave='meta_loja'", is_select=True).iloc[0,0]
    n_meta = st.number_input("Ajustar Meta R$", value=float(meta_loja))
    if st.button("Salvar Meta"):
        run_db("UPDATE config SET valor=? WHERE chave='meta_loja'", (n_meta,))
        st.success("Meta atualizada!")

    st.divider()
    st.write("### 👥 Gestão de Vendedores")
    equipe = run_db("SELECT * FROM usuarios", is_select=True)
    for _, r in equipe.iterrows():
        c_v1, c_v2 = st.columns([4,1])
        c_v1.write(f"👤 {r['nome']}")
        if c_v2.button("Remover", key=f"rem_{r['id']}"):
            run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
