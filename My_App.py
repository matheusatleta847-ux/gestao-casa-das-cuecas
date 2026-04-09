import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
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
DB_NAME = 'gestao_elite_v21.db'

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

# --- 4. CALCULOS ---
dados_raw = run_db("SELECT * FROM historico", is_select=True)
meta_atual = run_db("SELECT valor FROM config WHERE chave = 'meta_loja'", is_select=True).iloc[0]['valor']
vendas_sucesso = dados_raw[dados_raw['evento'] == 'Sucesso']
faturamento_total = vendas_sucesso['valor'].sum() if not vendas_sucesso.empty else 0
percentual_meta = min(faturamento_total / meta_atual, 1.0) if meta_atual > 0 else 0

# --- 5. CABEÇALHO ---
st.markdown(f"<div class='meta-container'><h3 style='margin:0;'>🎯 Meta: R$ {meta_atual:,.2f} | Vendido: R$ {faturamento_total:,.2f}</h3></div>", unsafe_allow_html=True)
st.progress(percentual_meta)

# --- 6. INTERFACE ---
t1, t2, t3 = st.tabs(["📋 OPERAÇÃO", "📊 DESEMPENHO & EDIÇÃO", "⚙️ CONFIG"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_fila, c_atend, c_fora = st.columns(3)
    
    with c_fila:
        st.subheader("⏳ Na Fila")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            classe = "vendedor-box primeiro-vez" if i == 0 else "vendedor-box"
            with st.container():
                st.markdown(f"<div class='{classe}'>👤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
                if st.button("Atender", key=f"at_{v['id']}"):
                    run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],))
                    st.rerun()
                if st.button("Pausa", key=f"p_{v['id']}"):
                    st.session_state[f"m_{v['id']}"] = True
                if st.session_state.get(f"m_{v['id']}", False):
                    with st.expander("Motivo:"):
                        m = st.selectbox("Motivo:", ["Almoço", "Banheiro", "Lanche", "Finalizar dia"], key=f"sel_{v['id']}")
                        if st.button("Confirmar", key=f"conf_{v['id']}"):
                            run_db("UPDATE usuarios SET status='Fora', motivo_pausa=? WHERE id=?", (m, v['id']))
                            run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], "SAÍDA", m, 0, 0, get_now_br().isoformat()))
                            st.session_state[f"m_{v['id']}"] = False; st.rerun()

    with c_atend:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container(border=True):
                st.write(f"**{v['nome']}**")
                if st.button("Finalizar", key=f"f_{v['id']}"):
                    st.session_state[f"fin_{v['id']}"] = True
            if st.session_state.get(f"fin_{v['id']}", False):
                with st.expander("Dados:", expanded=True):
                    res = st.selectbox("Resultado:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    vlr = st.number_input("Valor R$:", min_value=0.0, key=f"v_{v['id']}") if res == "Sucesso" else 0.0
                    it = st.number_input("Peças:", min_value=1, step=1, key=f"i_{v['id']}") if res == "Sucesso" else 0
                    if st.button("Gravar", key=f"gv_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", (v['nome'], res, res, vlr, it, get_now_br().isoformat()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_next_ordem(), v['id']))
                        st.session_state[f"fin_{v['id']}"] = False; st.rerun()

    with c_fora:
        st.subheader("💤 Fora")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            st.markdown(f"<div class='vendedor-box'>💤 <b>{v['nome']}</b></div>", unsafe_allow_html=True)
            if st.button(f"Entrar: {v['nome']}", key=f"in_{v['id']}"):
                run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (get_next_ordem(), v['id']))
                st.rerun()

with t2:
    st.subheader("📊 Gráficos & Edição de Histórico")
    if not dados_raw.empty:
        fig1 = px.bar(vendas_sucesso.groupby('vendedor')['valor'].sum().reset_index(), x='vendedor', y='valor', title="Vendas", template="seaborn")
        st.plotly_chart(fig1, use_container_width=True)
        
        # --- SEÇÃO DE EDIÇÃO PARA ADMIN ---
        if st.session_state.user['is_admin']:
            st.divider()
            st.markdown("### 📝 Editar ou Corrigir Valores")
            st.info("Altere os valores na tabela abaixo e clique em 'Salvar Alterações'.")
            
            # Criamos uma cópia editável dos dados
            df_editavel = dados_raw.copy()
            # Widget de tabela editável (st.data_editor)
            edited_df = st.data_editor(
                df_editavel, 
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "valor": st.column_config.NumberColumn("Valor R$", format="R$ %.2f"),
                    "itens": st.column_config.NumberColumn("Qtd Itens"),
                    "evento": st.column_config.SelectboxColumn("Evento", options=["Sucesso", "Não convertido", "Troca", "SAÍDA"])
                },
                hide_index=True,
                use_container_width=True
            )
            
            if st.button("💾 Salvar Alterações no Banco"):
                # Lógica para atualizar linha por linha o que foi mudado
                for index, row in edited_df.iterrows():
                    run_db(
                        "UPDATE historico SET vendedor=?, evento=?, motivo=?, valor=?, itens=? WHERE id=?",
                        (row['vendedor'], row['evento'], row['motivo'], row['valor'], row['itens'], row['id'])
                    )
                st.success("Banco de dados atualizado com sucesso!")
                st.rerun()

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            dados_raw.to_excel(writer, index=False)
        st.download_button("📥 Exportar para Excel", data=buffer.getvalue(), file_name="Auditoria_Loja.xlsx")

with t3:
    if st.session_state.user['is_admin']:
        st.subheader("🎯 Meta")
        nv_meta = st.number_input("Meta (R$):", value=meta_atual)
        if st.button("Atualizar Meta"):
            run_db("UPDATE config SET valor = ? WHERE chave = 'meta_loja'", (nv_meta,))
            st.rerun()
        st.divider()
        n = st.text_input("Vendedor:")
        if st.button("Adicionar"):
            run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (n.title(), n.lower().replace(" ","."), 'Fora', 0))
            st.rerun()
        for _, r in run_db("SELECT * FROM usuarios", is_select=True).iterrows():
            if st.button(f"Remover {r['nome']}", key=f"del_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
