import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Casa das Cuecas", layout="wide", page_icon="🛍️")

# --- CSS CUSTOMIZADO PARA FLUIDEZ ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { border-radius: 8px; height: 3em; transition: all 0.3s ease; }
    .stButton>button:hover { transform: scale(1.02); filter: brightness(1.1); }
    [data-testid="stMetric"] { background-color: #ffffff; padding: 15px; border-radius: 12px; border: 1px solid #eceef1; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .vendedor-card { background: white; padding: 20px; border-radius: 15px; border-left: 5px solid #007bff; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('gestao_loja.db')
    c = conn.cursor()
    # Tabela de Usuários/Vendedores
    c.execute('''CREATE TABLE IF NOT EXISTS vendedores 
                 (id INTEGER PRIMARY KEY, nome TEXT, login TEXT, senha TEXT, status TEXT, ordem INTEGER)''')
    # Tabela de Histórico (Ponto e Vendas)
    c.execute('''CREATE TABLE IF NOT EXISTS historico 
                 (id INTEGER PRIMARY KEY, vendedor TEXT, evento TEXT, valor REAL, data_hora DATETIME)''')
    conn.commit()
    conn.close()

def executar_db(query, params=()):
    conn = sqlite3.connect('gestao_loja.db')
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

def ler_db(query, params=()):
    conn = sqlite3.connect('gestao_loja.db')
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df

# --- LÓGICA DE LIMPEZA (30 DIAS) ---
def limpar_dados_antigos():
    # Remove registros com mais de 30 dias para manter a base leve
    data_limite = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    executar_db("DELETE FROM historico WHERE data_hora < ?", (data_limite,))

# --- INICIALIZAÇÃO ---
init_db()
limpar_dados_antigos()

# --- SIDEBAR (CONTROLE DE ACESSO E PONTO) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3081/3081559.png", width=80)
    st.title("Área do Colaborador")
    
    # Login Simples para demonstração
    user_nome = st.text_input("Seu Nome (Login)")
    
    col_p1, col_p2 = st.columns(2)
    if col_p1.button("🚀 ENTRADA", use_container_width=True):
        executar_db("INSERT INTO historico (vendedor, evento, data_hora) VALUES (?,?,?)", 
                    (user_nome, "ENTRADA", datetime.now()))
        executar_db("UPDATE vendedores SET status = 'Esperando' WHERE nome = ?", (user_nome,))
        st.toast(f"Bem-vindo, {user_nome}!", icon="👋")
        
    if col_p2.button("🏁 SAÍDA", use_container_width=True):
        executar_db("INSERT INTO historico (vendedor, evento, data_hora) VALUES (?,?,?)", 
                    (user_nome, "SAIDA", datetime.now()))
        executar_db("UPDATE vendedores SET status = 'Fora da Loja' WHERE nome = ?", (user_nome,))
        st.toast("Bom descanso!", icon="🌙")

# --- CONTEÚDO PRINCIPAL ---
st.markdown("<h1 style='text-align: center;'>🛍️ Casa das Cuecas - Lista da Vez</h1>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🚀 Operacional", "📊 Inteligência (30d)", "👥 Gestão de Equipe"])

with tab1:
    # KPIs rápidos
    vendas_hoje = ler_db("SELECT SUM(valor) as total FROM historico WHERE evento='VENDA' AND data_hora >= date('now')").iloc[0]['total'] or 0
    atend_hoje = len(ler_db("SELECT id FROM historico WHERE evento='ATENDIMENTO' AND data_hora >= date('now')"))
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Vendas Hoje", f"R$ {vendas_hoje:,.2f}")
    k2.metric("Atendimentos", atend_hoje)
    k3.metric("Status da Fila", "Ativa", delta="Normal")

    st.divider()
    
    # FILA DA VEZ (Cards)
    st.subheader("👥 Vendedores na Fila")
    vendedores = ler_db("SELECT * FROM vendedores WHERE status != 'Fora da Loja' ORDER BY ordem ASC")
    
    if vendedores.empty:
        st.info("Nenhum vendedor em loja no momento.")
    else:
        # Layout em Grid para os Cards
        cols = st.columns(3)
        for idx, row in vendedores.iterrows():
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"### {row['nome']}")
                    st.caption(f"Status: **{row['status']}**")
                    
                    if row['status'] == 'Esperando':
                        if st.button(f"Iniciar Atendimento", key=f"at_{row['id']}", use_container_width=True, type="primary"):
                            executar_db("UPDATE vendedores SET status = 'Em Atendimento' WHERE id = ?", (row['id'],))
                            executar_db("INSERT INTO historico (vendedor, evento, data_hora) VALUES (?,?,?)", 
                                        (row['nome'], "ATENDIMENTO", datetime.now()))
                            st.rerun()
                    
                    elif row['status'] == 'Em Atendimento':
                        vlr = st.number_input("Valor da Venda (se houver)", min_value=0.0, key=f"vlr_{row['id']}")
                        if st.button(f"Finalizar", key=f"fin_{row['id']}", use_container_width=True):
                            # Se teve valor, registra venda, senão, apenas volta pra fila
                            if vlr > 0:
                                executar_db("INSERT INTO historico (vendedor, evento, valor, data_hora) VALUES (?,?,?,?)", 
                                            (row['nome'], "VENDA", vlr, datetime.now()))
                            
                            # Joga o vendedor para o fim da fila (incrementa ordem)
                            max_ordem = ler_db("SELECT MAX(ordem) as m FROM vendedores").iloc[0]['m'] or 0
                            executar_db("UPDATE vendedores SET status = 'Esperando', ordem = ? WHERE id = ?", (max_ordem + 1, row['id']))
                            st.success("Fila atualizada!")
                            st.rerun()

with tab2:
    st.subheader("📊 Performance nos Últimos 30 Dias")
    # Consulta inteligente: Pega apenas os últimos 30 dias para os gráficos
    dados_30d = ler_db("""
        SELECT date(data_hora) as dia, SUM(valor) as total, COUNT(*) as qtd 
        FROM historico 
        WHERE evento = 'VENDA' AND data_hora >= date('now', '-30 days')
        GROUP BY dia
    """)
    
    if not dados_30d.empty:
        st.line_chart(dados_30d.set_index('dia')['total'])
        st.table(dados_30d)
    else:
        st.info("Ainda não há dados acumulados nos últimos 30 dias.")

with tab3:
    st.subheader("⚙️ Configuração de Equipe")
    with st.form("novo_vendedor"):
        nome_nv = st.text_input("Nome do Vendedor")
        login_nv = st.text_input("Login")
        if st.form_submit_button("Cadastrar"):
            executar_db("INSERT INTO vendedores (nome, login, status, ordem) VALUES (?,?,?,?)", 
                        (nome_nv, login_nv, 'Fora da Loja', 0))
            st.success("Cadastrado com sucesso!")
            st.rerun()
            
    st.divider()
    if st.button("Limpar Base de Dados (Manual)"):
        executar_db("DELETE FROM historico")
        st.warning("Histórico reiniciado.")
