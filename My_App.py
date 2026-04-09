import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO E ESTILO ---
st.set_page_config(page_title="Casa das Cuecas - Lista da Vez", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .vendedor-card { 
        padding: 15px; border-radius: 12px; background: white; 
        margin-bottom: 12px; border-left: 6px solid #dee2e6;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .proximo-da-vez { border-left-color: #28a745; background-color: #f0fff4; border: 1px solid #c6f6d5; }
    .stButton>button { border-radius: 8px; font-weight: 600; transition: 0.2s; }
    .metric-box { background: white; padding: 20px; border-radius: 10px; border: 1px solid #edf2f7; }
    </style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS (ROBUSTO) ---
DB_NAME = 'lista_vtex_final.db'

def executar(query, params=()):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

def consultar(query, params=()):
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql(query, conn, params=params)

def inicializar():
    executar('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, ordem INTEGER, inicio_atendimento TEXT)''')
    executar('''CREATE TABLE IF NOT EXISTS historico 
                 (id INTEGER PRIMARY KEY, vendedor TEXT, evento TEXT, motivo TEXT, valor REAL, data_hora TEXT)''')

inicializar()

# --- SEGURANÇA E LOGIN ---
if 'auth' not in st.session_state:
    st.session_state.auth = {"logado": False, "admin": False, "user": ""}

if not st.session_state.auth["logado"]:
    st.markdown("<h2 style='text-align: center;'>🔐 Acesso ao Sistema</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            u = st.text_input("Usuário/Login:").strip().lower()
            p = st.text_input("Senha (Admin):", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                if u == "admin" and p == "admin@123":
                    st.session_state.auth = {"logado": True, "admin": True, "user": "Administrador"}
                    st.rerun()
                else:
                    user_db = consultar("SELECT * FROM usuarios WHERE login = ?", (u,))
                    if not user_db.empty:
                        st.session_state.auth = {"logado": True, "admin": False, "user": user_db.iloc[0]['nome']}
                        st.rerun()
                    else:
                        st.error("Login inválido.")
    st.stop()

# --- MANUTENÇÃO (30 DIAS) ---
data_limite = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
executar("DELETE FROM historico WHERE data_hora < ?", (data_limite,))

# --- FUNÇÃO AUXILIAR DE FILA ---
def get_max_ordem():
    with sqlite3.connect(DB_NAME) as conn:
        res = conn.execute("SELECT MAX(ordem) FROM usuarios").fetchone()[0]
        return res if res is not None else 0

# --- INTERFACE PRINCIPAL ---
st.title(f"🛍️ Casa das Cuecas - {st.session_state.auth['user']}")

t1, t2, t3, t4 = st.tabs(["📋 Lista da Vez", "🏆 Ranking", "🎯 Minhas Metas", "⚙️ Gestão"])

# --- ABA 1: OPERACIONAL (LISTA DA VEZ) ---
with t1:
    vendedores = consultar("SELECT * FROM usuarios ORDER BY ordem ASC")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.subheader("⏳ Esperando")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            is_first = (i == 0)
            style = "proximo-da-vez" if is_first else ""
            with st.container():
                st.markdown(f"<div class='vendedor-card {style}'><b>{v['nome']}</b><br><small>{i+1}º da vez</small></div>", unsafe_allow_html=True)
                
                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button("Atender", key=f"at_{v['id']}"):
                    if not is_first:
                        st.session_state[f"furo_{v['id']}"] = True
                    else:
                        executar("UPDATE usuarios SET status='Atendendo', inicio_atendimento=? WHERE id=?", (datetime.now().isoformat(), v['id']))
                        st.rerun()
                if col_btn2.button("Sair", key=f"out_{v['id']}"):
                    st.session_state[f"sair_{v['id']}"] = True

            # Justificativa Furar Fila
            if st.session_state.get(f"furo_{v['id']}", False):
                with st.expander("❗ Justificar Atendimento Fora da Vez", expanded=True):
                    mot = st.selectbox("Motivo:", ["Preferência do cliente", "Operacional", "Retorno cliente"], key=f"mot_f_{v['id']}")
                    if st.button("Confirmar", key=f"c_f_{v['id']}"):
                        executar("UPDATE usuarios SET status='Atendendo', inicio_atendimento=? WHERE id=?", (datetime.now().isoformat(), v['id']))
                        executar("INSERT INTO historico (vendedor, evento, motivo, data_hora) VALUES (?,?,?,?)", (v['nome'], "Furo Fila", mot, datetime.now().isoformat()))
                        st.session_state[f"furo_{v['id']}"] = False
                        st.rerun()

    with c2:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container(border=True):
                st.markdown(f"**{v['nome']}**")
                if st.button("Finalizar Atendimento", key=f"fin_{v['id']}", use_container_width=True):
                    st.session_state[f"fim_{v['id']}"] = True
            
            if st.session_state.get(f"fim_{v['id']}", False):
                with st.expander("🏁 Resultado do Atendimento", expanded=True):
                    res = st.selectbox("O que aconteceu?", ["Sucesso (Venda)", "Não convertido", "Troca", "Outros"], key=f"res_{v['id']}")
                    vlr = 0.0
                    if res == "Sucesso (Venda)":
                        vlr = st.number_input("Valor total R$:", min_value=0.0)
                    mot_nc = st.text_input("Observação/Motivo:") if res != "Sucesso (Venda)" else ""
                    
                    if st.button("Salvar e Ir para o Fim da Fila", key=f"save_{v['id']}"):
                        executar("INSERT INTO historico (vendedor, evento, motivo, valor, data_hora) VALUES (?,?,?,?,?)",
                                (v['nome'], res, mot_nc, vlr, datetime.now().isoformat()))
                        executar("UPDATE usuarios SET status='Esperando', ordem=?, inicio_atendimento=NULL WHERE id=?", (get_max_ordem() + 1, v['id']))
                        st.session_state[f"fim_{v['id']}"] = False
                        st.rerun()

    with c3:
        st.subheader("💤 Fora da Loja")
        fora = vendedores[vendedores['status'] == 'Fora da Loja']
        for _, v in fora.iterrows():
            if st.button(f"Entrar: {v['nome']}", key=f"in_{v['id']}", use_container_width=True):
                executar("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_max_ordem() + 1, v['id']))
                st.rerun()

# --- ABA 2: RANKING ---
with t2:
    st.subheader("🏆 Melhores do Mês (Últimos 30 dias)")
    dados = consultar("SELECT vendedor, SUM(valor) as total, COUNT(*) as atendimentos FROM historico WHERE evento='Sucesso (Venda)' GROUP BY vendedor ORDER BY total DESC")
    if not dados.empty:
        c_r1, c_r2 = st.columns([1, 2])
        c_r1.dataframe(dados)
        c_r2.bar_chart(dados.set_index('vendedor')['total'])
    else:
        st.info("Sem vendas registradas.")

# --- ABA 3: METAS ---
with t3:
    if st.session_state.auth['user'] != "Administrador":
        v_nome = st.session_state.auth['user']
        meu_hist = consultar("SELECT * FROM historico WHERE vendedor = ?", (v_nome,))
        if not meu_hist.empty:
            total_vendas = meu_hist['valor'].sum()
            qtd_vendas = len(meu_hist[meu_hist['evento'] == 'Sucesso (Venda)'])
            taxa_conv = (qtd_vendas / len(meu_hist)) * 100
            
            st.markdown(f"### Performance: {v_nome}")
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Vendido", f"R$ {total_vendas:,.2f}")
            m2.metric("Taxa de Conversão", f"{taxa_conv:.1f}%")
            m3.metric("Ticket Médio", f"R$ {(total_vendas/qtd_vendas if qtd_vendas > 0 else 0):,.2f}")
        else:
            st.info("Nenhum dado encontrado para sua conta.")
    else:
        st.write("Aba de metas individuais disponível apenas para vendedores.")

# --- ABA 4: GESTÃO (ADMIN) ---
with t4:
    if st.session_state.auth['admin']:
        st.subheader("Adicionar Vendedor")
        novo_v = st.text_input("Nome Completo:")
        if st.button("Cadastrar"):
            if novo_v:
                login = novo_v.lower().replace(" ", ".")
                try:
                    executar("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (novo_v.title(), login, 'Fora da Loja', 999))
                    st.success(f"Vendedor {novo_v} cadastrado! Login: {login}")
                except:
                    st.error("Login já existe.")
        
        st.divider()
        if st.button("🔥 Limpar Todos os Dados"):
            executar("DELETE FROM usuarios")
            executar("DELETE FROM historico")
            st.rerun()
    else:
        st.warning("Acesso restrito ao administrador.")

with st.sidebar:
    if st.button("Deslogar"):
        st.session_state.auth = {"logado": False, "admin": False, "user": ""}
        st.rerun()
