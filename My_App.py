import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import io
import hashlib
import re

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Fila VIP - Casa das Cuecas", layout="wide", page_icon="🛍️")

# --- 2. BANCO DE DADOS E SEGURANÇA ---
def init_db():
    conn = sqlite3.connect('sistema.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS vendedoras 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, status TEXT, 
                  ordem INTEGER, inicio_status TEXT, motivo_pausa TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS historico 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, vendedor TEXT, 
                  evento TEXT, motivo TEXT, valor_venda REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, login TEXT UNIQUE, senha TEXT, 
                  nome_completo TEXT, nascimento TEXT, telefone TEXT, email TEXT)''')
    
    c.execute("SELECT COUNT(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        h = hashlib.sha256("Admin@123".encode()).hexdigest()
        c.execute("INSERT INTO usuarios (login, senha, nome_completo) VALUES (?, ?, ?)", 
                 ("admin", h, "Administrador"))
    conn.commit()
    conn.close()

init_db()

def validar_senha(senha):
    if len(senha) < 6: return False, "Mínimo 6 caracteres."
    if not re.search(r"[A-Z]", senha): return False, "Deve ter 1 letra MAIÚSCULA."
    if not re.search(r"[0-9]", senha): return False, "Deve ter 1 NÚMERO."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", senha): return False, "Deve ter 1 caractere especial (@, #, etc)."
    if any(seq in senha for seq in ["123", "234", "345", "456", "567", "678", "789"]):
        return False, "Não use sequências numéricas (ex: 123)."
    return True, ""

def executar_db(query, params=(), fetch=False):
    conn = sqlite3.connect('sistema.db')
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if fetch:
            res = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            return pd.DataFrame(res, columns=cols)
        conn.commit()
    finally:
        conn.close()

def mover_vendedor(v_id, novo_status, justificativa=None):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    res_v = executar_db("SELECT nome FROM vendedoras WHERE id = ?", (v_id,), fetch=True)
    if not res_v.empty:
        nome_v = res_v.iloc[0, 0]
        if justificativa:
            evento_log = "Fura-Fila" if novo_status == "Atendimento" else "Pausa"
            executar_db("INSERT INTO historico (data_hora, vendedor, evento, motivo, valor_venda) VALUES (?,?,?,?,?)",
                        (agora, nome_v, evento_log, justificativa, 0.0))
        if novo_status == 'Esperando':
            r_ordem = executar_db("SELECT MAX(ordem) FROM vendedoras WHERE status = 'Esperando'", fetch=True)
            prox = int(r_ordem.iloc[0, 0] if r_ordem.iloc[0, 0] is not None else 0) + 1
            executar_db("UPDATE vendedoras SET status=?, ordem=?, inicio_status=?, motivo_pausa=NULL WHERE id=?", 
                        (novo_status, prox, agora, v_id))
        else:
            executar_db("UPDATE vendedoras SET status=?, ordem=0, inicio_status=?, motivo_pausa=? WHERE id=?", 
                        (novo_status, agora, justificativa, v_id))

def calcular_tempo(inicio_str):
    if not inicio_str: return "00:00"
    try:
        inicio = datetime.strptime(inicio_str, "%Y-%m-%d %H:%M:%S")
        decorrido = datetime.now() - inicio
        mins, segs = divmod(decorrido.seconds, 60)
        return f"{mins:02d}:{segs:02d}"
    except: return "00:00"

# --- 3. TELA DE ACESSO (LOGIN / CADASTRO) ---
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.markdown("<h2 style='text-align: center; padding: 20px;'>🔐 Casa das Cuecas - Acesso</h2>", unsafe_allow_html=True)
    t_login, t_novo = st.tabs(["Entrar", "Criar Usuário"])
    
    with t_login:
        u_log = st.text_input("Usuário:")
        p_log = st.text_input("Senha:", type="password")
        manter = st.checkbox("Manter-me conectado", value=True)
        if st.button("Entrar", use_container_width=True):
            h_log = hashlib.sha256(p_log.encode()).hexdigest()
            res = executar_db("SELECT * FROM usuarios WHERE login=? AND senha=?", (u_log, h_log), fetch=True)
            if not res.empty:
                st.session_state['autenticado'] = True
                st.session_state['usuario_nome'] = u_log
                st.rerun()
            else: st.error("Usuário ou senha inválidos.")

    with t_novo:
        with st.form("form_cad"):
            c_u = st.text_input("Login desejado:")
            c_s = st.text_input("Senha Forte:", type="password", help="Maiúscula, Número, Símbolo.")
            c_n = st.text_input("Nome Completo:")
            # Calendário padrão Brasil
            c_d = st.date_input("Data de Nascimento:", format="DD/MM/YYYY")
            c_t = st.text_input("Telefone:")
            c_e = st.text_input("E-mail:")
            if st.form_submit_button("Finalizar Cadastro"):
                ok, msg = validar_senha(c_s)
                if not ok: st.error(msg)
                elif c_u and c_n:
                    h_cad = hashlib.sha256(c_s.encode()).hexdigest()
                    try:
                        executar_db("INSERT INTO usuarios (login, senha, nome_completo, nascimento, telefone, email) VALUES (?,?,?,?,?,?)", 
                                  (c_u, h_cad, c_n, str(c_d), c_t, c_e))
                        st.success("Conta criada! Vá em 'Entrar'.")
                    except: st.error("Login já existe.")
    st.stop()

# --- 4. CSS ORIGINAL ---
st.markdown("""
<style>
    :root { --card-bg: #ffffff; --card-border: #e2e8f0; --text-main: #0f172a; --text-sub: #64748b; }
    @media (prefers-color-scheme: dark) {
        :root { --card-bg: #1e293b; --card-border: #334155; --text-main: #f1f5f9; --text-sub: #94a3b8; }
    }
    .barra-header {
        background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%);
        color: white; height: 60px; display: flex; align-items: center; justify-content: center;
        font-weight: 700; border-radius: 12px; margin-bottom: 20px; font-size: 0.85rem; text-transform: uppercase;
    }
    .timer-badge { color: #e11d48; font-family: 'Courier New', monospace; font-weight: 800; font-size: 1.2rem; }
    .card-vendedor {
        background-color: var(--card-bg); border: 1px solid var(--card-border); 
        padding: 18px; border-radius: 16px; min-height: 100px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    .v-nome { font-weight: 700; color: var(--text-main); font-size: 1.1rem; margin: 0; }
    .ranking-item {
        background-color: var(--card-bg); padding: 12px 18px; border-radius: 12px;
        border-left: 6px solid #0f172a; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; color: var(--text-main);
    }
</style>
""", unsafe_allow_html=True)

# --- 5. INTERFACE OPERACIONAL ---
st.sidebar.write(f"👤 Logado: **{st.session_state['usuario_nome']}**")
if st.sidebar.button("Sair"):
    st.session_state['autenticado'] = False
    st.rerun()

st.markdown("<h2 style='text-align: center; padding: 10px 0;'>🛍️ Gestão Casa das Cuecas</h2>", unsafe_allow_html=True)
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Operacional", "📊 Inteligência", "👥 Equipe", "🔐 Segurança"])

with tab1:
    dados = executar_db("SELECT * FROM vendedoras", fetch=True)
    col1, col2, col3 = st.columns(3)

    # --- FORA DE OPERAÇÃO ---
    with col1:
        st.markdown('<div class="barra-header">FORA DE OPERAÇÃO</div>', unsafe_allow_html=True)
        for _, v in dados[dados['status'] == 'Fora da loja'].iterrows():
            st.markdown(f'<div style="text-align:right;"><span class="timer-badge">{calcular_tempo(v["inicio_status"])}</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card-vendedor"><p class="v-nome">{v["nome"]}</p><p style="color:gray; font-size:0.8rem;">📍 {v["motivo_pausa"]}</p></div>', unsafe_allow_html=True)
            if st.button(f"Retornar: {v['nome']}", key=f"ret_{v['id']}", use_container_width=True):
                mover_vendedor(v['id'], 'Esperando'); st.rerun()

    # --- FILA DE ESPERA ---
    with col2:
        st.markdown('<div class="barra-header">FILA DE ESPERA</div>', unsafe_allow_html=True)
        v_fila = dados[dados['status'] == 'Esperando'].sort_values('ordem').reset_index(drop=True)
        for i, v in v_fila.iterrows():
            st.markdown(f'<div class="card-vendedor"><p class="v-nome">{i+1}º {v["nome"]}</p></div>', unsafe_allow_html=True)
            ca, cb = st.columns(2)
            if ca.button("Atender", key=f"at_{v['id']}", use_container_width=True):
                if i == 0: mover_vendedor(v['id'], 'Atendimento'); st.rerun()
                else: st.session_state[f"just_at_{v['id']}"] = True
            if cb.button("Pausa", key=f"ps_{v['id']}", use_container_width=True):
                st.session_state[f"pop_ps_{v['id']}"] = True

            if st.session_state.get(f"just_at_{v['id']}", False):
                with st.form(key=f"f_j_{v['id']}"):
                    mot = st.selectbox("Justificativa (Fura-Fila):", ["Preferência do cliente", "Operacional", "Retorno cliente"])
                    if st.form_submit_button("Confirmar Atendimento"):
                        mover_vendedor(v['id'], 'Atendimento', mot)
                        st.session_state[f"just_at_{v['id']}"] = False; st.rerun()

            if st.session_state.get(f"pop_ps_{v['id']}", False):
                with st.form(key=f"f_p_{v['id']}"):
                    m = st.selectbox("Motivo:", ["Almoço", "Lanche", "Banheiro", "Tarefa externa", "Finalizar dia"])
                    if st.form_submit_button("Confirmar Pausa"):
                        mover_vendedor(v['id'], "Folga" if m == "Finalizar dia" else "Fora da loja", m)
                        st.session_state[f"pop_ps_{v['id']}"] = False; st.rerun()

    # --- EM ATENDIMENTO ---
    with col3:
        st.markdown('<div class="barra-header">EM ATENDIMENTO</div>', unsafe_allow_html=True)
        for _, v in dados[dados['status'] == 'Atendimento'].iterrows():
            st.markdown(f'<div style="text-align:right;"><span class="timer-badge">{calcular_tempo(v["inicio_status"])}</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card-vendedor"><p class="v-nome">{v["nome"]}</p></div>', unsafe_allow_html=True)
            res = st.selectbox("Resultado:", ["Aguardando...", "Sucesso", "Troca", "Não Convertido"], key=f"res_{v['id']}")
            if res != "Aguardando...":
                with st.form(key=f"f_at_{v['id']}"):
                    vlr, mot_f = 0.0, res
                    if res == "Sucesso": vlr = st.number_input("Valor Venda R$:", min_value=0.0, format="%.2f")
                    elif res == "Não Convertido": mot_f = st.selectbox("Motivo:", ["Preço", "Falta Modelo", "Só Olhando"])
                    if st.form_submit_button("Finalizar"):
                        executar_db("INSERT INTO historico (data_hora, vendedor, evento, motivo, valor_venda) VALUES (?,?,?,?,?)",
                                   (datetime.now().strftime("%Y-%m-%d %H:%M"), v['nome'], res, mot_f, vlr))
                        mover_vendedor(v['id'], 'Esperando'); st.rerun()

with tab2:
    st.markdown("### 📊 Inteligência & Ranking")
    df_rank = executar_db("SELECT data_hora, vendedor, valor_venda FROM historico WHERE evento = 'Sucesso'", fetch=True)
    if not df_rank.empty:
        df_rank['data_hora'] = pd.to_datetime(df_rank['data_hora'])
        r1, r2, r3 = st.columns(3)
        hoje = datetime.now()
        for col, (titulo, dias) in zip([r1, r2, r3], [("Hoje", 1), ("Semana", 7), ("Mês", 30)]):
            with col:
                st.markdown(f"**{titulo}**")
                filtro = df_rank[df_rank['data_hora'] > (hoje - timedelta(days=dias))]
                if not filtro.empty:
                    rank = filtro.groupby('vendedor')['valor_venda'].sum().sort_values(ascending=False)
                    for i, (vend, total) in enumerate(rank.items()):
                        st.markdown(f'<div class="ranking-item"><span>{i+1}º {vend}</span> <b>R$ {total:,.2f}</b></div>', unsafe_allow_html=True)
    
    st.divider()
    df_full = executar_db("SELECT data_hora as 'Data', vendedor as 'Vendedor', evento as 'Evento', motivo as 'Detalhe', valor_venda as 'Valor' FROM historico ORDER BY id DESC", fetch=True)
    st.dataframe(df_full, use_container_width=True, hide_index=True)
    if not df_full.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_full.to_excel(writer, index=False)
        st.download_button("📥 Baixar Relatório Excel", output.getvalue(), "relatorio.xlsx")

with tab3:
    st.markdown("### ⚙️ Gestão de Equipe (Fila)")
    v_full = executar_db("SELECT * FROM vendedoras", fetch=True)
    e1, e2 = st.columns(2)
    with e1:
        with st.expander("➕ Adicionar Vendedora"):
            nome_nv = st.text_input("Nome da Vendedora:")
            if st.button("Salvar na Lista"):
                if nome_nv: executar_db("INSERT OR IGNORE INTO vendedoras (nome, status, ordem) VALUES (?, 'Folga', 999)", (nome_nv,)); st.rerun()
    with e2:
        with st.expander("🗑️ Remover da Lista"):
            if not v_full.empty:
                v_sel = st.selectbox("Escolha quem remover:", v_full['nome'].tolist())
                if st.button("Excluir Permanentemente"):
                    executar_db("DELETE FROM vendedoras WHERE nome = ?", (v_sel,))
                    st.rerun()
    
    st.write("#### 💤 Em Folga")
    for _, f in v_full[v_full['status'] == 'Folga'].iterrows():
        cn, cb = st.columns([4, 1])
        cn.markdown(f'<div class="card-vendedor" style="min-height:50px; padding:10px;">👤 {f["nome"]}</div>', unsafe_allow_html=True)
        if cb.button("Ativar", key=f"in_{f['id']}", use_container_width=True):
            mover_vendedor(f['id'], 'Esperando'); st.rerun()

with tab4:
    st.subheader("🔐 Gestão de Acessos ao Sistema")
    usuarios_db = executar_db("SELECT login, nome_completo, telefone, email FROM usuarios", fetch=True)
    st.dataframe(usuarios_db, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        with st.expander("🔄 Alterar Minha Senha"):
            u_atual = st.session_state['usuario_nome']
            s_velha = st.text_input("Senha Atual:", type="password")
            s_nova = st.text_input("Nova Senha Forte:", type="password")
            if st.button("Confirmar Alteração"):
                ok_s, msg_s = validar_senha(s_nova)
                if not ok_s: st.error(msg_s)
                else:
                    h_velha = hashlib.sha256(s_velha.encode()).hexdigest()
                    if not executar_db("SELECT * FROM usuarios WHERE login=? AND senha=?", (u_atual, h_velha), fetch=True).empty:
                        executar_db("UPDATE usuarios SET senha=? WHERE login=?", (hashlib.sha256(s_nova.encode()).hexdigest(), u_atual))
                        st.success("Sua senha foi alterada!")
                    else: st.error("Senha atual incorreta.")

    with col_b:
        with st.expander("🗑️ Excluir Usuários"):
            outros = [u for u in usuarios_db['login'].tolist() if u != st.session_state['usuario_nome']]
            if outros:
                u_del = st.selectbox("Escolha qual acesso remover:", outros)
                confirm = st.checkbox(f"Confirmo que {u_del} não terá mais acesso.")
                if st.button("Excluir Acesso"):
                    if confirm:
                        executar_db("DELETE FROM usuarios WHERE login=?", (u_del,))
                        st.success(f"Usuário {u_del} removido.")
                        st.rerun()
            else:
                st.info("Você é o único usuário cadastrado.")