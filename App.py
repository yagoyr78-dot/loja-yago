import os
import sqlite3
from urllib.parse import quote

import pandas as pd
import streamlit as st

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Loja Yago", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "loja.db")

WHATSAPP_NUMERO = "5565993157477"
EMAIL_CONTATO = "Yagoyr78@gmail.com"
TELEFONE_CONTATO = "65 993157477"


# =========================
# FUNÇÕES AUXILIARES
# =========================
def caminho_imagem(nome_arquivo):
    return os.path.join(BASE_DIR, "assets", nome_arquivo)


def formatar_real(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# =========================
# PRODUTOS
# =========================
PRODUTOS = [
    {
        "id": 1,
        "nome": "Cappuccino 260 ml",
        "preco": 10.00,
        "imagem": caminho_imagem("cappuccino_260ml.png"),
        "descricao": "Bebida pronta para consumo.",
    },
    {
        "id": 2,
        "nome": "Barra de Proteína",
        "preco": 12.00,
        "imagem": caminho_imagem("barra_proteina.png"),
        "descricao": "Barra proteica para o dia a dia.",
    },
    {
        "id": 3,
        "nome": "Cappuccino em Pó",
        "preco": 6.00,
        "imagem": caminho_imagem("cappuccino_po.png"),
        "descricao": "Mistura para preparo de cappuccino.",
    },
    {
        "id": 4,
        "nome": "Iogurte Proteico",
        "preco": 10.00,
        "imagem": caminho_imagem("iogurte_proteico.png"),
        "descricao": "Bebida proteica pronta para consumo.",
    },
]


# =========================
# BANCO DE DADOS
# =========================
def conectar():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


conn = conectar()
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_nome TEXT NOT NULL,
    produto_nome TEXT NOT NULL,
    quantidade INTEGER NOT NULL,
    valor_unitario REAL NOT NULL,
    valor_total REAL NOT NULL
)
""")
conn.commit()


# =========================
# FUNÇÕES DE DADOS
# =========================
def salvar_pedido(nome, itens):
    for item in itens:
        total = item["quantidade"] * item["preco"]
        cursor.execute("""
            INSERT INTO pedidos (
                cliente_nome,
                produto_nome,
                quantidade,
                valor_unitario,
                valor_total
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            nome,
            item["nome"],
            item["quantidade"],
            item["preco"],
            total
        ))
    conn.commit()


def deletar_pedido(pedido_id):
    cursor.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))
    conn.commit()


def limpar_todos_pedidos():
    cursor.execute("DELETE FROM pedidos")
    conn.commit()


def carregar_vendas():
    return pd.read_sql_query("SELECT * FROM pedidos ORDER BY id DESC", conn)


def top_produtos():
    df = carregar_vendas()
    if df.empty:
        return pd.DataFrame(columns=["produto_nome", "quantidade"])
    return (
        df.groupby("produto_nome", as_index=False)["quantidade"]
        .sum()
        .sort_values("quantidade", ascending=False)
        .head(3)
    )


def top_clientes():
    df = carregar_vendas()
    if df.empty:
        return pd.DataFrame(columns=["cliente_nome", "valor_total"])
    return (
        df.groupby("cliente_nome", as_index=False)["valor_total"]
        .sum()
        .sort_values("valor_total", ascending=False)
        .head(3)
    )


def gerar_whatsapp(nome, itens):
    linhas = [f"Pedido - {nome}", ""]
    total_geral = 0

    for item in itens:
        subtotal = item["quantidade"] * item["preco"]
        total_geral += subtotal
        linhas.append(
            f"{item['nome']} - {item['quantidade']}x - {formatar_real(item['preco'])} = {formatar_real(subtotal)}"
        )

    linhas.append("")
    linhas.append(f"Total: {formatar_real(total_geral)}")

    texto = "\n".join(linhas)
    return f"https://wa.me/{WHATSAPP_NUMERO}?text={quote(texto)}"


# =========================
# CARRINHO
# =========================
if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

if "whatsapp_link" not in st.session_state:
    st.session_state.whatsapp_link = None


def adicionar_ao_carrinho(produto, qtd):
    for item in st.session_state.carrinho:
        if item["id"] == produto["id"]:
            item["quantidade"] += qtd
            return

    st.session_state.carrinho.append({
        "id": produto["id"],
        "nome": produto["nome"],
        "preco": produto["preco"],
        "quantidade": qtd,
    })


def remover_do_carrinho(produto_id):
    st.session_state.carrinho = [
        item for item in st.session_state.carrinho if item["id"] != produto_id
    ]


def total_carrinho():
    return sum(item["preco"] * item["quantidade"] for item in st.session_state.carrinho)


# =========================
# CSS
# =========================
st.markdown("""
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}
[data-testid="stSidebar"] {
    background-color: #f3f4f6;
}
h1, h2, h3 {
    color: #111827;
}
.card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 18px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.04);
}
.hero {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    padding: 36px;
    border-radius: 22px;
    color: white;
    margin-bottom: 24px;
}
.hero h2 {
    color: white;
    margin-bottom: 8px;
}
.preco {
    font-size: 24px;
    font-weight: 700;
    color: #111827;
}
.botao-whatsapp {
    display:inline-block;
    padding:12px 18px;
    background:#25D366;
    color:white !important;
    text-decoration:none;
    border-radius:10px;
    font-weight:600;
}
.linha-pedido {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 12px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)


# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.title("Carrinho")

    if st.session_state.carrinho:
        for item in st.session_state.carrinho:
            st.write(f"**{item['nome']} ({item['quantidade']})**")
            st.write(f"Subtotal: {formatar_real(item['quantidade'] * item['preco'])}")

            if st.button("Remover", key=f"rem_{item['id']}"):
                remover_do_carrinho(item["id"])
                st.rerun()

        st.write(f"**Total: {formatar_real(total_carrinho())}**")

        nome = st.text_input("Seu nome")

        if st.button("Finalizar pedido"):
            if not nome.strip():
                st.warning("Informe seu nome.")
            else:
                salvar_pedido(nome, st.session_state.carrinho)
                st.session_state.whatsapp_link = gerar_whatsapp(nome, st.session_state.carrinho)
                st.session_state.carrinho = []
                st.success("Pedido registrado com sucesso.")
                st.rerun()
    else:
        st.info("Carrinho vazio")

    if st.session_state.whatsapp_link:
        st.markdown(
            f'<a href="{st.session_state.whatsapp_link}" target="_blank" class="botao-whatsapp">Enviar no WhatsApp</a>',
            unsafe_allow_html=True,
        )


# =========================
# MENU
# =========================
pagina = st.radio("", ["Início", "Produtos", "Contato"], horizontal=True)


# =========================
# PÁGINA INÍCIO
# =========================
if pagina == "Início":
    st.markdown("""
    <div class="hero">
        <h2>Loja Yago</h2>
        <p>Cappuccino pronto, cappuccino em pó, barra de proteína e iogurte proteico.</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Top 3 produtos mais vendidos")
    ranking = top_produtos()
    if ranking.empty:
        st.info("Ainda não há vendas registradas.")
    else:
        st.dataframe(ranking, width="stretch", hide_index=True)

    df = carregar_vendas()
    faturamento = df["valor_total"].sum() if not df.empty else 0
    itens_vendidos = df["quantidade"].sum() if not df.empty else 0
    clientes = df["cliente_nome"].nunique() if not df.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Faturamento", formatar_real(faturamento))
    c2.metric("Itens vendidos", int(itens_vendidos))
    c3.metric("Clientes", int(clientes))

    st.subheader("Top 3 clientes")
    clientes_df = top_clientes()
    if clientes_df.empty:
        st.info("Ainda não há compras registradas.")
    else:
        clientes_df["valor_total"] = clientes_df["valor_total"].apply(formatar_real)
        st.dataframe(clientes_df, width="stretch", hide_index=True)

    st.subheader("Pedidos registrados")

    if df.empty:
        st.info("Nenhum pedido registrado.")
    else:
        col_btn1, col_btn2 = st.columns([1, 4])

        with col_btn1:
            if st.button("Limpar todos os pedidos"):
                limpar_todos_pedidos()
                st.success("Todos os pedidos foram removidos.")
                st.rerun()

        st.markdown("---")

        for _, row in df.iterrows():
            col1, col2, col3, col4, col5, col6 = st.columns([2.2, 2.2, 1, 1.2, 1.2, 1.2])

            col1.write(row["cliente_nome"])
            col2.write(row["produto_nome"])
            col3.write(int(row["quantidade"]))
            col4.write(formatar_real(row["valor_unitario"]))
            col5.write(formatar_real(row["valor_total"]))

            if col6.button("Excluir", key=f"del_{row['id']}"):
                deletar_pedido(int(row["id"]))
                st.success("Pedido removido.")
                st.rerun()


# =========================
# PÁGINA PRODUTOS
# =========================
elif pagina == "Produtos":
    st.title("Produtos")

    cols = st.columns(2)

    for i, p in enumerate(PRODUTOS):
        with cols[i % 2]:
            st.markdown('<div class="card">', unsafe_allow_html=True)

            if os.path.exists(p["imagem"]):
                st.image(p["imagem"], width=250)
            else:
                st.warning(f"Imagem não encontrada: {p['imagem']}")

            st.subheader(p["nome"])
            st.write(p["descricao"])
            st.markdown(
                f'<div class="preco">{formatar_real(p["preco"])}</div>',
                unsafe_allow_html=True
            )

            qtd = st.number_input(
                f"Quantidade - {p['nome']}",
                min_value=1,
                step=1,
                value=1,
                key=f"qtd_{p['id']}"
            )

            if st.button(f"Adicionar {p['nome']}", key=f"btn_{p['id']}"):
                adicionar_ao_carrinho(p, int(qtd))
                st.success("Produto adicionado ao carrinho.")

            st.markdown("</div>", unsafe_allow_html=True)


# =========================
# PÁGINA CONTATO
# =========================
else:
    st.title("Contato")
    st.write(f"Email: {EMAIL_CONTATO}")
    st.write(f"Telefone: {TELEFONE_CONTATO}")