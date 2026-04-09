import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO E ESTILO ---
st.set_page_config(page_title="Lista da Vez - Casa das Cuecas", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6; }
    .vendedor-card { padding: 15px; border-radius: 10px; border-left: 5px solid #2e7d32; background: white; margin-bottom: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    .status-badge { font-size: 0.8em; padding: 3px 8px; border-radius: 5px; color: white; }
    .esperando { background-color: #007bff; }
    .atendimento { background-color: #ffc107; color: black; }
    .fora { background-color: #6c757d; }
    .proximo { border: 2px solid #2e7d32; background-color: #e8f5e9; }
    </style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS ---
def executar(query, params=()):
    with sqlite3.connect('lista_vez_v2.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

def inicializar():
    executar('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, status TEXT, ordem INTEGER, inicio_atendimento DATETIME)''')
    executar('''CREATE TABLE IF NOT EXISTS historico 
                 (id INTEGER PRIMARY KEY, vendedor TEXT, evento TEXT, motivo TEXT, valor REAL, data_hora DATETIME)''')

inicializar()

# --- CONTROLE DE ACESSO ---
if 'usuario_ativo' not in st.session_state:
    st.session_state.usuario_ativo = None
    st.session_state.is_admin = False

if not st.session_state.usuario_ativo:
    st.title("🔐 Lista da Vez - Acesso")
    with st.form("login"):
        u = st.text_input("Login ou Nome:")
        p = st.text_input("Senha (Admin):", type="password")
        if st.form_submit_button("Entrar"):
            if u == "admin" and p == "admin@123":
                st.session_state.usuario_ativo = "Administrador"
                st.session_state.is_admin = True
                st.rerun()
            else:
                with sqlite3.connect('lista_vez_v2.db') as conn:
                    user = pd.read_sql("SELECT * FROM usuarios WHERE login = ?", conn, params=(u.lower(),))
                if not user.empty:
                    st.session_state.usuario_ativo = user.iloc[0]['nome']
                    st.rerun()
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.header(f"🏪 Loja: Casa das Cuecas | Usuário: {st.session_state.usuario_ativo}")

tab1, tab2, tab3, tab4 = st.tabs(["📋 Lista da Vez", "📊 Rankings & Campanhas", "🎯 Metas Individuais", "⚙️ Admin"])

with tab1:
    col_esp, col_atend, col_fora = st.columns(3)

    # Buscar dados
    with sqlite3.connect('lista_vez_v2.db') as conn:
        df_vendedores = pd.read_sql("SELECT * FROM usuarios ORDER BY ordem ASC", conn)

    # 1. COLUNA: ESPERANDO A VEZ
    with col_esp:
        st.subheader("⏳ Esperando a Vez")
        esperando = df_vendedores[df_vendedores['status'] == 'Esperando']
        for i, v in esperando.reset_index(drop=True).iterrows():
            is_primeiro = (i == 0)
            classe_proximo = "proximo" if is_primeiro else ""
            label_vez = "⭐ O PRÓXIMO" if is_primeiro else f"{i+1}º da Fila"
            
            with st.container():
                st.markdown(f"""<div class='vendedor-card {classe_proximo}'>
                    <strong>{v['nome']}</strong><br><small>{label_vez}</small></div>""", unsafe_allow_html=True)
                
                if st.button(f"Iniciar Atendimento", key=f"btn_at_{v['id']}"):
                    if not is_primeiro:
                        st.session_state[f"justificar_{v['id']}"] = True
                    else:
                        executar("UPDATE usuarios SET status = 'Atendendo', inicio_atendimento = ? WHERE id = ?", (datetime.now(), v['id']))
                        st.rerun()
                
                if st.button(f"Sair da Loja", key=f"btn_fora_{v['id']}"):
                    st.session_state[f"sair_loja_{v['id']}"] = True

            # Modal de Justificativa para Furar Fila
            if st.session_state.get(f"justificar_{v['id']}", False):
                with st.expander("⚠️ Por que está saindo da fila de espera?", expanded=True):
                    motivo = st.radio("Selecione:", ["Preferência do cliente", "Operacional", "Retorno cliente"], key=f"mot_{v['id']}")
                    if st.button("Concluir Início", key=f"conf_at_{v['id']}"):
                        executar("UPDATE usuarios SET status = 'Atendendo', inicio_atendimento = ? WHERE id = ?", (datetime.now(), v['id']))
                        executar("INSERT INTO historico (vendedor, evento, motivo, data_hora) VALUES (?,?,?,?)", (v['nome'], "Furo de Fila", motivo, datetime.now()))
                        st.session_state[f"justificar_{v['id']}"] = False
                        st.rerun()

    # 2. COLUNA: EM ATENDIMENTO
    with col_atend:
        st.subheader("🚀 Em Atendimento")
        atendendo = df_vendedores[df_vendedores['status'] == 'Atendendo']
        for _, v in atendendo.iterrows():
            tempo = ""
            if v['inicio_atendimento']:
                delta = datetime.now() - datetime.strptime(v['inicio_atendimento'], "%Y-%m-%d %H:%M:%S.%f")
                tempo = f"{delta.seconds // 60} min"

            with st.container(border=True):
                st.write(f"**{v['nome']}**")
                st.caption(f"⏱️ {tempo}")
                if st.button("Encerrar Atendimento", key=f"enc_{v['id']}"):
                    st.session_state[f"encerrar_{v['id']}"] = True

            if st.session_state.get(f"encerrar_{v['id']}", False):
                with st.expander("🏁 O que aconteceu neste atendimento?", expanded=True):
                    res = st.selectbox("Resultado:", ["Sucesso", "Não convertido", "Troca", "Outros"], key=f"res_{v['id']}")
                    vlr = 0.0
                    motivo_nc = ""
                    
                    if res == "Sucesso":
                        vlr = st.number_input("Valor da Venda:", min_value=0.0)
                    elif res == "Não convertido":
                        motivo_nc = st.selectbox("Motivo:", ["Não encontrou o modelo", "Só olhando", "Preço"])
                    
                    if st.button("Concluir Atendimento", key=f"fin_{v['id']}"):
                        executar("INSERT INTO historico (vendedor, evento, motivo, valor, data_hora) VALUES (?,?,?,?,?)",
                                (v['nome'], res, motivo_nc, vlr, datetime.now()))
                        # Volta para o fim da fila
                        max_o = df_vendedores['ordem'].max() or 0
                        executar("UPDATE usuarios SET status = 'Esperando', ordem = ?, inicio_atendimento = NULL WHERE id = ?", (max_o + 1, v['id']))
                        st.session_state[f"encerrar_{v['id']}"] = False
                        st.rerun()

    # 3. COLUNA: FORA DA LOJA
    with col_fora:
        st.subheader("💤 Fora da Loja")
        fora = df_vendedores[df_vendedores['status'] == 'Fora da Loja']
        for _, v in fora.iterrows():
            if st.button(f"Entrar na Loja: {v['nome']}", key=f"back_{v['id']}"):
                max_o = df_vendedores['ordem'].max() or 0
                executar("UPDATE usuarios SET status = 'Esperando', ordem = ? WHERE id = ?", (max_o + 1, v['id']))
                st.rerun()

        # Modal de Justificativa para Sair da Loja
        for _, v in esperando.iterrows():
            if st.session_state.get(f"sair_loja_{v['id']}", False):
                with st.expander(f"🚪 Por que {v['nome']} vai sair?", expanded=True):
                    mot = st.radio("Motivo:", ["Finalizar dia", "Almoço", "Lanche", "Banheiro", "Tarefas Externas"], key=f"s_m_{v['id']}")
                    if st.button("Confirmar Saída", key=f"s_c_{v['id']}"):
                        executar("UPDATE usuarios SET status = 'Fora da Loja' WHERE id = ?", (v['id'],))
                        executar("INSERT INTO historico (vendedor, evento, motivo, data_hora) VALUES (?,?,?,?)", (v['nome'], "Saída Loja", mot, datetime.now()))
                        st.session_state[f"sair_loja_{v['id']}"] = False
                        st.rerun()

# --- ABA 2: RANKINGS ---
with tab2:
    st.subheader("🏆 Rankings e Campanhas")
    with sqlite3.connect('lista_vez_v2.db') as conn:
        stats = pd.read_sql("""
            SELECT vendedor, SUM(valor) as faturamento, 
            COUNT(CASE WHEN evento='Sucesso' THEN 1 END) as vendas,
            COUNT(*) as total_atend
            FROM historico GROUP BY vendedor ORDER BY faturamento DESC
        """, conn)
    
    if not stats.empty:
        st.dataframe(stats, use_container_width=True)
        st.bar_chart(stats.set_index('vendedor')['faturamento'])
    else:
        st.info("Aguardando dados para gerar ranking.")

# --- ABA 3: METAS ---
with tab3:
    st.subheader("🎯 Seu Desempenho Individual")
    vend_nome = st.session_state.usuario_ativo
    if vend_nome != "Administrador":
        with sqlite3.connect('lista_vez_v2.db') as conn:
            meus_dados = pd.read_sql("SELECT * FROM historico WHERE vendedor = ?", conn, params=(vend_nome,))
        
        if not meus_dados.empty:
            conv = (len(meus_dados[meus_dados['evento']=='Sucesso']) / len(meus_dados)) * 100
            tm = meus_dados[meus_dados['valor'] > 0]['valor'].mean()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Taxa de Conversão", f"{conv:.1f}%")
            c2.metric("Ticket Médio", f"R$ {tm:.2f}")
            c3.metric("Atendimentos", len(meus_dados))
        else:
            st.info("Você ainda não possui atendimentos registrados.")
    else:
        st.warning("Selecione um vendedor na aba Admin para ver as metas.")

# --- ABA 4: ADMIN ---
if st.session_state.is_admin:
    with tab4:
        st.subheader("➕ Novo Vendedor")
        n = st.text_input("Nome:")
        if st.button("Cadastrar"):
            if n:
                login = n.lower().replace(" ", ".")
                executar("INSERT INTO usuarios (nome, login, status, ordem) VALUES (?,?,?,?)", (n, login, 'Fora da Loja', 99))
                st.success(f"Vendedor {n} cadastrado! Login: {login}")

        st.divider()
        if st.button("🔄 Resetar Tudo"):
            executar("DELETE FROM usuarios")
            executar("DELETE FROM historico")
            st.rerun()

with st.sidebar:
    st.divider()
    if st.button("Deslogar"):
        st.session_state.usuario_ativo = None
        st.rerun()
