import os
import sqlite3
from urllib.parse import quote
import base64

import streamlit as st

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Loja Yago", layout="wide", page_icon="🛒")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "loja.db")

WHATSAPP_NUMERO  = "5565993157477"
EMAIL_CONTATO    = "Yagoyr78@gmail.com"
TELEFONE_CONTATO = "(65) 99315-7477"


# =========================
# HELPERS
# =========================
def caminho_imagem(nome):
    return os.path.join(BASE_DIR, "assets", nome)

def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def img_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


# =========================
# PRODUTOS
# =========================
PRODUTOS = [
    {
        "id": 1,
        "nome": "Cappuccino 260 ml",
        "preco": 10.00,
        "imagem": caminho_imagem("cappuccino_260ml.png"),
        "descricao": "Bebida pronta para consumo. Gelada, cremosa e deliciosa.",
        "tag": "Bebida",
    },
    {
        "id": 2,
        "nome": "Barra de Proteína",
        "preco": 12.00,
        "imagem": caminho_imagem("barra_proteina.png"),
        "descricao": "Alta em proteína, ideal para o dia a dia ativo.",
        "tag": "Proteína",
    },
    {
        "id": 3,
        "nome": "Cappuccino em Pó",
        "preco": 6.00,
        "imagem": caminho_imagem("cappuccino_po.png"),
        "descricao": "Mistura especial para preparo de cappuccino cremoso.",
        "tag": "Bebida",
    },
    {
        "id": 4,
        "nome": "Iogurte Proteico",
        "preco": 10.00,
        "imagem": caminho_imagem("iogurte_proteico.png"),
        "descricao": "Rico em proteínas, sabor suave e textura cremosa.",
        "tag": "Proteína",
    },
]


# =========================
# BANCO DE DADOS
# =========================
def conectar():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn   = conectar()
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS pedidos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_nome   TEXT NOT NULL,
    produto_nome   TEXT NOT NULL,
    quantidade     INTEGER NOT NULL,
    valor_unitario REAL NOT NULL,
    valor_total    REAL NOT NULL
)
""")
conn.commit()

def salvar_pedido(nome, itens):
    for item in itens:
        total = item["quantidade"] * item["preco"]
        cursor.execute("""
            INSERT INTO pedidos (cliente_nome, produto_nome, quantidade, valor_unitario, valor_total)
            VALUES (?, ?, ?, ?, ?)
        """, (nome, item["nome"], item["quantidade"], item["preco"], total))
    conn.commit()

def gerar_whatsapp(nome, itens):
    linhas = [f"Olá! Gostaria de fazer um pedido.", f"Nome: {nome}", ""]
    total_geral = 0
    for item in itens:
        subtotal = item["quantidade"] * item["preco"]
        total_geral += subtotal
        linhas.append(f"• {item['nome']} x{item['quantidade']} — {brl(subtotal)}")
    linhas += ["", f"*Total: {brl(total_geral)}*"]
    texto = "\n".join(linhas)
    return f"https://wa.me/{WHATSAPP_NUMERO}?text={quote(texto)}"


# =========================
# CARRINHO (session state)
# =========================
if "carrinho" not in st.session_state:
    st.session_state.carrinho = []
if "whatsapp_link" not in st.session_state:
    st.session_state.whatsapp_link = None
if "pedido_enviado" not in st.session_state:
    st.session_state.pedido_enviado = False

def adicionar(produto, qtd):
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

def remover(pid):
    st.session_state.carrinho = [i for i in st.session_state.carrinho if i["id"] != pid]

def total_carrinho():
    return sum(i["preco"] * i["quantidade"] for i in st.session_state.carrinho)

def qtd_total_carrinho():
    return sum(i["quantidade"] for i in st.session_state.carrinho)


# =========================
# CSS
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* { font-family: 'Inter', sans-serif; }

[data-testid="stApp"] {
    background-color: #f8f9fa;
}
.block-container {
    padding-top: 0 !important;
    padding-bottom: 2rem;
    max-width: 1200px;
}

/* HEADER */
.header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
    padding: 20px 36px;
    border-radius: 0 0 24px 24px;
    margin-bottom: 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.header-logo {
    font-size: 1.7rem;
    font-weight: 800;
    color: white;
    letter-spacing: -0.5px;
}
.header-logo span {
    color: #60a5fa;
}
.header-sub {
    color: #94a3b8;
    font-size: 0.85rem;
    margin-top: 2px;
}
.header-cart-badge {
    background: #ef4444;
    color: white;
    border-radius: 50%;
    width: 22px;
    height: 22px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
    margin-left: 6px;
}

/* HERO BANNER */
.hero {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #1d4ed8 100%);
    padding: 48px 40px;
    border-radius: 20px;
    color: white;
    margin-bottom: 36px;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 300px; height: 300px;
    background: rgba(96,165,250,0.12);
    border-radius: 50%;
}
.hero h1 {
    font-size: 2.2rem;
    font-weight: 800;
    margin-bottom: 10px;
    color: white !important;
}
.hero p {
    color: #94a3b8;
    font-size: 1.05rem;
    max-width: 500px;
}
.hero-badge {
    display: inline-block;
    background: rgba(96,165,250,0.2);
    color: #60a5fa;
    border: 1px solid rgba(96,165,250,0.3);
    padding: 4px 14px;
    border-radius: 50px;
    font-size: 0.8rem;
    font-weight: 600;
    margin-bottom: 14px;
    letter-spacing: 0.5px;
}

/* PRODUCT CARD */
.produto-card {
    background: white;
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;
    transition: transform 0.2s, box-shadow 0.2s;
    margin-bottom: 24px;
    height: 100%;
}
.produto-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.12);
}
.produto-img-wrap {
    background: #f1f5f9;
    padding: 24px;
    text-align: center;
    height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.produto-img-wrap img {
    max-height: 160px;
    max-width: 100%;
    object-fit: contain;
}
.produto-body {
    padding: 20px;
}
.produto-tag {
    display: inline-block;
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 50px;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.produto-nome {
    font-size: 1.1rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 6px;
}
.produto-desc {
    font-size: 0.85rem;
    color: #64748b;
    margin-bottom: 14px;
    line-height: 1.5;
}
.produto-preco {
    font-size: 1.4rem;
    font-weight: 800;
    color: #0f172a;
}

/* SIDEBAR CART */
[data-testid="stSidebar"] {
    background: white;
    border-right: 1px solid #e2e8f0;
}
.cart-titulo {
    font-size: 1.2rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 2px solid #f1f5f9;
}
.cart-item {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 10px;
}
.cart-item-nome {
    font-weight: 600;
    font-size: 0.9rem;
    color: #0f172a;
}
.cart-item-preco {
    font-size: 0.85rem;
    color: #64748b;
    margin-top: 2px;
}
.cart-total-box {
    background: #f1f5f9;
    border-radius: 12px;
    padding: 14px;
    margin: 16px 0;
    text-align: center;
}
.cart-total-label {
    font-size: 0.8rem;
    color: #64748b;
    font-weight: 500;
}
.cart-total-valor {
    font-size: 1.5rem;
    font-weight: 800;
    color: #0f172a;
}
.btn-whatsapp {
    display: block;
    background: #25D366;
    color: white !important;
    text-align: center;
    padding: 14px;
    border-radius: 12px;
    font-weight: 700;
    font-size: 1rem;
    text-decoration: none !important;
    margin-top: 10px;
    letter-spacing: 0.2px;
}
.btn-whatsapp:hover {
    background: #128C7E;
}

/* SECTION TITLE */
.section-title {
    font-size: 1.5rem;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 4px;
}
.section-sub {
    font-size: 0.9rem;
    color: #64748b;
    margin-bottom: 24px;
}

/* CONTATO CARD */
.contato-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 16px;
}
.contato-icon {
    font-size: 1.8rem;
    width: 52px;
    height: 52px;
    background: #eff6ff;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.contato-label {
    font-size: 0.75rem;
    color: #64748b;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.contato-valor {
    font-size: 1rem;
    font-weight: 700;
    color: #0f172a;
}

h1, h2, h3 { color: #0f172a; }

div[data-testid="stRadio"] > label { display: none; }
div[data-testid="stRadio"] > div {
    display: flex;
    gap: 8px;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 50px;
    padding: 4px;
    width: fit-content;
}
div[data-testid="stRadio"] > div > label {
    border-radius: 50px !important;
    padding: 6px 20px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
}
</style>
""", unsafe_allow_html=True)


# =========================
# HEADER
# =========================
qtd_badge = f'<span class="header-cart-badge">{qtd_total_carrinho()}</span>' if qtd_total_carrinho() > 0 else ""
st.markdown(f"""
<div class="header">
    <div>
        <div class="header-logo">Loja <span>Yago</span></div>
        <div class="header-sub">Produtos selecionados com qualidade</div>
    </div>
    <div style="color:white;font-size:1.4rem;">
        Carrinho {qtd_badge}
    </div>
</div>
""", unsafe_allow_html=True)


# =========================
# SIDEBAR - CARRINHO
# =========================
with st.sidebar:
    st.markdown('<div class="cart-titulo">Meu Carrinho</div>', unsafe_allow_html=True)

    if st.session_state.carrinho:
        for item in st.session_state.carrinho:
            subtotal = item["preco"] * item["quantidade"]
            st.markdown(f"""
            <div class="cart-item">
                <div class="cart-item-nome">{item['nome']}</div>
                <div class="cart-item-preco">{item['quantidade']}x — {brl(subtotal)}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Remover", key=f"rem_{item['id']}"):
                remover(item["id"])
                st.session_state.whatsapp_link = None
                st.session_state.pedido_enviado = False
                st.rerun()

        st.markdown(f"""
        <div class="cart-total-box">
            <div class="cart-total-label">Total do pedido</div>
            <div class="cart-total-valor">{brl(total_carrinho())}</div>
        </div>
        """, unsafe_allow_html=True)

        nome = st.text_input("Seu nome", placeholder="Digite seu nome completo")

        if st.button("Confirmar pedido", type="primary", use_container_width=True):
            if not nome.strip():
                st.warning("Por favor, informe seu nome.")
            else:
                salvar_pedido(nome, st.session_state.carrinho)
                st.session_state.whatsapp_link = gerar_whatsapp(nome, st.session_state.carrinho)
                st.session_state.carrinho = []
                st.session_state.pedido_enviado = True
                st.rerun()

        if st.session_state.pedido_enviado and st.session_state.whatsapp_link:
            st.success("Pedido confirmado!")
            st.markdown(
                f'<a href="{st.session_state.whatsapp_link}" target="_blank" class="btn-whatsapp">Enviar pelo WhatsApp</a>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown("""
        <div style="text-align:center;padding:40px 0;color:#94a3b8;">
            <div style="font-size:2.5rem;margin-bottom:10px;">🛒</div>
            <div style="font-weight:600;font-size:0.95rem;">Carrinho vazio</div>
            <div style="font-size:0.8rem;margin-top:4px;">Adicione produtos para começar</div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.pedido_enviado and st.session_state.whatsapp_link:
            st.success("Pedido confirmado!")
            st.markdown(
                f'<a href="{st.session_state.whatsapp_link}" target="_blank" class="btn-whatsapp">Enviar pelo WhatsApp</a>',
                unsafe_allow_html=True,
            )


# =========================
# MENU
# =========================
pagina = st.radio("", ["Produtos", "Contato"], horizontal=True)


# =========================
# PÁGINA PRODUTOS
# =========================
if pagina == "Produtos":

    st.markdown("""
    <div class="hero">
        <div class="hero-badge">Entrega na sua mesa</div>
        <h1>Produtos frescos e selecionados</h1>
        <p>Cappuccinos, barras de proteína e iogurtes — qualidade garantida direto para você.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">Nossos Produtos</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Escolha os produtos e adicione ao carrinho</div>', unsafe_allow_html=True)

    cols = st.columns(2, gap="large")

    for i, p in enumerate(PRODUTOS):
        with cols[i % 2]:
            img_b64 = img_base64(p["imagem"])
            img_html = f'<img src="data:image/png;base64,{img_b64}" />' if img_b64 else '<div style="color:#94a3b8;font-size:2rem;">Sem imagem</div>'

            st.markdown(f"""
            <div class="produto-card">
                <div class="produto-img-wrap">{img_html}</div>
                <div class="produto-body">
                    <div class="produto-tag">{p['tag']}</div>
                    <div class="produto-nome">{p['nome']}</div>
                    <div class="produto-desc">{p['descricao']}</div>
                    <div class="produto-preco">{brl(p['preco'])}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_qtd, col_btn = st.columns([1, 2])
            with col_qtd:
                qtd = st.number_input("Qtd", min_value=1, step=1, value=1, key=f"qtd_{p['id']}", label_visibility="collapsed")
            with col_btn:
                if st.button("Adicionar ao carrinho", key=f"btn_{p['id']}", use_container_width=True, type="primary"):
                    adicionar(p, int(qtd))
                    st.success(f"{p['nome']} adicionado!")
                    st.rerun()


# =========================
# PÁGINA CONTATO
# =========================
elif pagina == "Contato":

    st.markdown('<div class="section-title">Fale conosco</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Estamos à disposição para atender você</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="contato-card">
        <div class="contato-icon">📱</div>
        <div>
            <div class="contato-label">WhatsApp</div>
            <div class="contato-valor">{TELEFONE_CONTATO}</div>
        </div>
    </div>
    <div class="contato-card">
        <div class="contato-icon">✉️</div>
        <div>
            <div class="contato-label">E-mail</div>
            <div class="contato-valor">{EMAIL_CONTATO}</div>
        </div>
    </div>
    <div class="contato-card">
        <div class="contato-icon">⏰</div>
        <div>
            <div class="contato-label">Horário de atendimento</div>
            <div class="contato-valor">Segunda a Sexta, 8h às 18h</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
    <a href="https://wa.me/{WHATSAPP_NUMERO}" target="_blank" class="btn-whatsapp" style="max-width:320px;margin:0 auto;display:block;">
        Falar no WhatsApp
    </a>
    """, unsafe_allow_html=True)
