import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import plotly.express as px

# --- 1. CONFIGURAÇÃO PREMIUM & CSS DINÂMICO (CORREÇÃO VISIBILIDADE) ---
st.set_page_config(page_title="PRO-Vez Elite | Casa das Cuecas", layout="wide", page_icon="🛍️")

# CSS Ajustado para garantir contraste em Dark/Light Mode
st.markdown("""
    <style>
    /* Cores que se adaptam ao tema do Streamlit automaticamente */
    
    /* 1. Estilo Principal para Fundo e Texto Padrão */
    body, [data-testid="stAppViewContainer"] {
        color: inherit; /* Respeita a cor do tema */
        background-color: inherit; /* Respeita o fundo do tema */
    }

    /* 2. Estilo dos Cards (Métricas e Vendedores) */
    .vendedor-box, .metric-card { 
        padding: 16px; 
        border-radius: 10px; 
        border: 1px solid rgba(128, 128, 128, 0.2); 
        margin-bottom: 12px;
        transition: 0.3s;
        
        /* CORREÇÃO CHAVE: Fundo e Texto Adaptáveis */
        background-color: rgba(128, 128, 128, 0.1) !important; /* Fundo transparente/cinza suave */
        color: inherit !important; /* Fonte herda cor do tema (preta no claro, branca no escuro) */
    }

    /* 3. Estilo Específico para Primeiro da Fila (Destaque Verde) */
    .primeiro-vez { 
        border: 2px solid #22C55E !important; 
        background-color: rgba(34, 197, 94, 0.15) !important; 
        box-shadow: 0 4px 10px rgba(34,197,94,0.15); 
    }

    /* 4. Estilo dos Cards de Métricas (Destaque Azul no topo) */
    .metric-card {
        border-top: 4px solid #3B82F6 !important;
        margin-top: 5px;
    }

    /* 5. Correção de Texto das Abas (Menu) */
    .stTabs [data-baseweb="tab-list"] {
        color: inherit !important;
    }

    /* 6. Garantir legibilidade de negrito/b dentro dos cards */
    .vendedor-box b, .metric-card b, .vendedor-box span, .metric-card span {
        color: inherit !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE DADOS ---
DB_NAME = 'gestao_elite_v19.db'

# Função para obter o horário de Brasília (UTC-3)
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

init_db()

# --- 3. FUNÇÃO DE ORDEM BLINDADA ---
def get_next_ordem():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.execute("SELECT MAX(ordem) FROM usuarios")
        res = cursor.fetchone()[0]
        try:
            if res is None: return 1
            return int(res) + 1
        except (ValueError, TypeError):
            return 1

# --- 4. ACESSO ---
if 'user' not in st.session_state: st.session_state.user = None
if not st.session_state.user:
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>🔐 Login PRO-Vez Elite</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.form("login"):
            u = st.text_input("Usuário:").strip().lower()
            p = st.text_input("Senha Admin:", type="password")
            if st.form_submit_button("Entrar no Sistema"):
                if u == "admin" and p == "admin@123":
                    st.session_state.user = {"nome": "Admin", "is_admin": True}; st.rerun()
                else:
                    res = run_db("SELECT * FROM usuarios WHERE login = ?", (u,), True)
                    if not res.empty: 
                        st.session_state.user = {"nome": res.iloc[0]['nome'], "is_admin": False}
                        st.rerun()
                    else: st.error("Login inválido.")
    st.stop()

# --- 5. KPIs DE INTELIGÊNCIA ---
dados_raw = run_db("SELECT * FROM historico", is_select=True)

vendas_sucesso = dados_raw[dados_raw['evento'] == 'Sucesso']
nao_convertidos = dados_raw[dados_raw['evento'] == 'Não convertido']
oportunidades = len(vendas_sucesso) + len(nao_convertidos)

faturamento = vendas_sucesso['valor'].sum() if not vendas_sucesso.empty else 0
pa_medio = (vendas_sucesso['itens'].sum() / len(vendas_sucesso)) if not vendas_sucesso.empty else 0
conversao = (len(vendas_sucesso) / oportunidades * 100) if oportunidades > 0 else 0

# Cards de Métricas (Faturamento, Conversão, P.A., Trocas)
k1, k2, k3, k4 = st.columns(4)
k1.markdown(f'<div class="metric-card">Faturamento Mensal<br><b>R$ {faturamento:,.2f}</b></div>', unsafe_allow_html=True)
k2.markdown(f'<div class="metric-card">Conversão Real<br><b>{conversao:.1f}%</b></div>', unsafe_allow_html=True)
k3.markdown(f'<div class="metric-card">P.A. (Itens/Venda)<br><b>{pa_medio:.2f}</b></div>', unsafe_allow_html=True)
k4.markdown(f'<div class="metric-card">Total Trocas<br><b>{len(dados_raw[dados_raw["evento"] == "Troca"])}</b></div>', unsafe_allow_html=True)

# --- 6. OPERAÇÃO ---
st.markdown("<br>", unsafe_allow_html=True) # Espaçador
t1, t2, t3 = st.tabs(["📋 OPERAÇÃO (FILA)", "📊 DESEMPENHO", "⚙️ EQUIPE"])

with t1:
    vendedores = run_db("SELECT * FROM usuarios ORDER BY ordem ASC", is_select=True)
    c_fila, c_atend, c_fora = st.columns(3)

    with c_fila:
        st.subheader("⏳ Na Fila")
        esp = vendedores[vendedores['status'] == 'Esperando'].reset_index(drop=True)
        for i, v in esp.iterrows():
            classe = "vendedor-box primeiro-vez" if i == 0 else "vendedor-box"
            with st.container():
                st.markdown(f"<div class='{classe}'>👤 <b>{v['nome']}</b><br><small>{i+1}º da Vez</small></div>", unsafe_allow_html=True)
                col1, col2 = st.columns(2)
                if col1.button("Atender", key=f"at_{v['id']}", type="primary"):
                    run_db("UPDATE usuarios SET status='Atendendo' WHERE id=?", (v['id'],))
                    st.rerun()
                if col2.button("Sair/Pausa", key=f"out_{v['id']}"):
                    st.session_state[f"modal_{v['id']}"] = True
            
            if st.session_state.get(f"modal_{v['id']}", False):
                with st.expander("Motivo da Saída:", expanded=True):
                    mot = st.selectbox("Selecione:", ["Almoço", "Banheiro", "Lanche", "Finalizar dia"], key=f"sel_{v['id']}")
                    if st.button("Confirmar", key=f"ok_{v['id']}"):
                        ev = "FINAL DE DIA" if mot == "Finalizar dia" else "SAÍDA (PAUSA)"
                        run_db("UPDATE usuarios SET status='Fora', motivo_pausa=? WHERE id=?", (mot, v['id']))
                        # Auditoria Invisível (Fuso SP)
                        run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", 
                               (v['nome'], ev, mot, get_now_br().isoformat()))
                        st.session_state[f"modal_{v['id']}"] = False; st.rerun()

    with c_atend:
        st.subheader("🚀 Atendendo")
        atend = vendedores[vendedores['status'] == 'Atendendo']
        for _, v in atend.iterrows():
            with st.container(border=True):
                st.write(f"Vendedor: **{v['nome']}**")
                if st.button("Finalizar Atendimento", key=f"fin_{v['id']}", type="primary"):
                    st.session_state[f"f_{v['id']}"] = True
            
            if st.session_state.get(f"f_{v['id']}", False):
                with st.expander("Dados da Venda:", expanded=True):
                    res = st.selectbox("Status:", ["Sucesso", "Não convertido", "Troca"], key=f"res_{v['id']}")
                    perda = ""
                    if res == "Não convertido":
                        perda = st.selectbox("Motivo Perda:", ["Preço", "Falta Tamanho", "Só olhando", "Falta Cor"], key=f"p_{v['id']}")
                    vlr = st.number_input("Valor R$:", min_value=0.0, key=f"v_{v['id']}") if res == "Sucesso" else 0.0
                    it = st.number_input("Itens:", min_value=1, step=1, key=f"i_{v['id']}") if res == "Sucesso" else 0
                    if st.button("Gravar Registro", key=f"sv_{v['id']}"):
                        run_db("INSERT INTO historico (vendedor, evento, motivo, valor, itens, data) VALUES (?,?,?,?,?,?)", 
                               (v['nome'], res, perda if perda else res, vlr, it, get_now_br().isoformat()))
                        run_db("UPDATE usuarios SET status='Esperando', ordem=? WHERE id=?", (get_next_ordem(), v['id']))
                        st.session_state[f"f_{v['id']}"] = False; st.rerun()

    with c_fora:
        st.subheader("💤 Fora da Loja")
        for _, v in vendedores[vendedores['status'] == 'Fora'].iterrows():
            with st.container():
                # Card adaptável
                st.markdown(f"<div class='vendedor-box'>💤 <b>{v['nome']}</b><br><small>Status: {v['motivo_pausa']}</small></div>", unsafe_allow_html=True)
                if st.button(f"Entrar / Retornar: {v['nome']}", key=f"ret_{v['id']}"):
                    ev = "INÍCIO DE DIA" if v['motivo_pausa'] in ["Finalizar dia", None] else "RETORNO (PAUSA)"
                    # Auditoria Invisível (Fuso SP)
                    run_db("INSERT INTO historico (vendedor, evento, motivo, data) VALUES (?,?,?,?)", 
                           (v['nome'], ev, v['motivo_pausa'], get_now_br().isoformat()))
                    run_db("UPDATE usuarios SET status='Esperando', ordem=?, motivo_pausa=NULL WHERE id=?", (get_next_ordem(), v['id']))
                    st.rerun()

# --- ABA DESEMPENHO (MÉTROPLES PLOTLY ADAPTÁVEIS) ---
with t2:
    if not dados_raw.empty:
        c1, c2 = st.columns(2)
        
        with c1:
            # Gráfico de Faturamento Interativo (Usando template do tema)
            df_fat = vendas_sucesso.groupby('vendedor')['valor'].sum().reset_index()
            fig1 = px.bar(df_fat, x='vendedor', y='valor', title="Faturamento por Vendedor (R$)", 
                          color='valor', color_continuous_scale='Greens', template="seaborn") # Seaborn adapta bem a fundos escuros
            st.plotly_chart(fig1, use_container_width=True)

        with c2:
            # Gráfico de Motivos de Perda
            df_perda = dados_raw[dados_raw['evento'] == 'Não convertido'].groupby('motivo').size().reset_index(name='qtd')
            fig2 = px.pie(df_perda, values='qtd', names='motivo', title="Por que estamos perdendo vendas?", 
                         hole=0.4, template="seaborn")
            st.plotly_chart(fig2, use_container_width=True)
        
        st.divider()
        # Auditoria Invisível: Exportação Excel XLSX
        buffer = io.BytesIO()
        df_export = run_db("SELECT vendedor, evento, motivo, valor, itens, data FROM historico ORDER BY data DESC", is_select=True)
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Auditoria_Casa_Cuecas')
        st.download_button("📥 Baixar Excel Completo (.xlsx)", data=buffer.getvalue(), 
                         file_name=f"Auditoria_Elite_{get_now_br().strftime('%d_%m_%Y')}.xlsx",
                         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else: st.info("Sem dados suficientes para dashboards.")

# --- ABA EQUIPE ---
with t3:
    if st.session_state.user['is_admin']:
        st.subheader("⚙️ Gestão de Equipe")
        with st.container(border=True):
            n_nv = st.text_input("Nome do Novo Vendedor:")
            if st.button("Cadastrar na Equipe"):
                if n_nv:
                    l_nv = n_nv.lower().replace(" ", ".")
                    try:
                        run_db("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", 
                               (n_nv.title(), l_nv, 'Fora', 0))
                        st.success(f"{n_nv} cadastrado!"); st.rerun()
                    except: st.error("Login já existe.")
        equipe = run_db("SELECT * FROM usuarios ORDER BY nome ASC", is_select=True)
        for _, r in equipe.iterrows():
            c_n, c_e = st.columns([3, 1])
            c_n.write(f"👤 **{r['nome']}**")
            if c_e.button("Remover", key=f"del_{r['id']}"):
                run_db("DELETE FROM usuarios WHERE id=?", (r['id'],)); st.rerun()
    else: st.warning("Área restrita ao Administrador.")
