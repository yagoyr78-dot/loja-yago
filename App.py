import os
import sqlite3
from urllib.parse import quote
import base64
import io

import streamlit as st
import qrcode
from PIL import Image

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Loja Yago", layout="wide", page_icon="🛒")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "loja.db")

WHATSAPP_NUMERO  = st.secrets["WHATSAPP_NUMERO"]
EMAIL_CONTATO    = st.secrets["EMAIL_CONTATO"]
TELEFONE_CONTATO = st.secrets["TELEFONE_CONTATO"]
ADMIN_SENHA      = st.secrets["ADMIN_SENHA"]
PIX_CHAVE        = st.secrets["PIX_CHAVE"]
PIX_NOME         = st.secrets["PIX_NOME"]
PIX_CIDADE       = st.secrets["PIX_CIDADE"]


# =========================
# HELPERS
# =========================
def caminho_imagem(nome):
    return os.path.join(BASE_DIR, "assets", nome)

def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gerar_pix_payload(chave, nome, cidade, valor):
    def crc16(data):
        crc = 0xFFFF
        for byte in data.encode("utf-8"):
            crc ^= byte << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
                crc &= 0xFFFF
        return crc

    def f(id, v):
        return f"{id}{len(v):02d}{v}"

    gui = f("00", "br.gov.bcb.pix") + f("01", chave)
    valor_str = f"{valor:.2f}"
    payload = (
        f("00", "01") +
        f("26", gui) +
        f("52", "0000") +
        f("53", "986") +
        f("54", valor_str) +
        f("58", "BR") +
        f("59", nome[:25]) +
        f("60", cidade[:15]) +
        f("62", f("05", "***"))
        + "6304"
    )
    return payload + f"{crc16(payload):04X}"

def gerar_qrcode_pix(valor):
    payload = gerar_pix_payload(PIX_CHAVE, PIX_NOME, PIX_CIDADE, valor)
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

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
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_nome     TEXT NOT NULL,
    produto_nome     TEXT NOT NULL,
    quantidade       INTEGER NOT NULL,
    valor_unitario   REAL NOT NULL,
    valor_total      REAL NOT NULL,
    forma_pagamento  TEXT NOT NULL DEFAULT 'agora',
    pago             INTEGER NOT NULL DEFAULT 1,
    custo_unitario   REAL NOT NULL DEFAULT 0,
    data_venda       TEXT DEFAULT (datetime('now','localtime'))
)
""")
# Migração: adiciona colunas se não existirem (banco já existente)
for col, default in [("forma_pagamento", "'agora'"), ("pago", "1"), ("custo_unitario", "0"), ("data_venda", "datetime('now','localtime')")]:
    try:
        cursor.execute(f"ALTER TABLE pedidos ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}")
        conn.commit()
    except Exception:
        pass

# TABELA DE CUSTOS
cursor.execute("""
CREATE TABLE IF NOT EXISTS custos (
    produto_id   INTEGER PRIMARY KEY,
    produto_nome TEXT NOT NULL,
    custo        REAL NOT NULL DEFAULT 0
)
""")
conn.commit()
cursor.execute("SELECT COUNT(*) FROM custos")
if cursor.fetchone()[0] == 0:
    custos_iniciais = [
        (1, "Cappuccino 260 ml", 7.30),
        (2, "Barra de Proteína",  5.14),
        (4, "Iogurte Proteico",   6.00),
    ]
    cursor.executemany("INSERT INTO custos (produto_id, produto_nome, custo) VALUES (?, ?, ?)", custos_iniciais)
    conn.commit()

# TABELA DE ESTOQUE
cursor.execute("""
CREATE TABLE IF NOT EXISTS estoque (
    produto_id   INTEGER PRIMARY KEY,
    produto_nome TEXT NOT NULL,
    quantidade   INTEGER NOT NULL DEFAULT 0
)
""")
conn.commit()

# Estoque inicial — só insere se a tabela estiver vazia
cursor.execute("SELECT COUNT(*) FROM estoque")
if cursor.fetchone()[0] == 0:
    estoques_iniciais = [
        (1, "Cappuccino 260 ml",  11),
        (2, "Barra de Proteína",  19),
        (4, "Iogurte Proteico",    3),
    ]
    cursor.executemany("INSERT INTO estoque (produto_id, produto_nome, quantidade) VALUES (?, ?, ?)", estoques_iniciais)
    conn.commit()

import pandas as pd

def carregar_vendas():
    return pd.read_sql_query("SELECT * FROM pedidos ORDER BY id DESC", conn)

def deletar_pedido(pedido_id):
    cursor.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))
    conn.commit()

def limpar_pedidos():
    cursor.execute("DELETE FROM pedidos")
    conn.commit()

def marcar_pago(pedido_id):
    cursor.execute("UPDATE pedidos SET pago = 1 WHERE id = ?", (pedido_id,))
    conn.commit()

def marcar_pago_cliente(cliente_nome):
    cursor.execute("UPDATE pedidos SET pago = 1 WHERE cliente_nome = ? AND pago = 0", (cliente_nome,))
    conn.commit()

def carregar_custos():
    return {row[0]: row[1] for row in cursor.execute("SELECT produto_id, custo FROM custos").fetchall()}

def definir_custo(produto_id, custo):
    cursor.execute("UPDATE custos SET custo = ? WHERE produto_id = ?", (custo, produto_id))
    conn.commit()

def editar_venda(pedido_id, novo_valor_total):
    cursor.execute("UPDATE pedidos SET valor_total = ? WHERE id = ?", (novo_valor_total, pedido_id))
    conn.commit()

def carregar_estoque():
    return {row[0]: row[1] for row in cursor.execute("SELECT produto_id, quantidade FROM estoque").fetchall()}

def atualizar_estoque(produto_id, delta):
    cursor.execute("UPDATE estoque SET quantidade = MAX(0, quantidade + ?) WHERE produto_id = ?", (delta, produto_id))
    conn.commit()

def definir_estoque(produto_id, quantidade):
    cursor.execute("UPDATE estoque SET quantidade = ? WHERE produto_id = ?", (quantidade, produto_id))
    conn.commit()

def salvar_pedido(nome, itens, forma_pagamento):
    from datetime import datetime
    pago = 1 if forma_pagamento == "agora" else 0
    custos_db = carregar_custos()
    data_agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    for item in itens:
        total = item["quantidade"] * item["preco"]
        custo_unit = custos_db.get(item["id"], 0)
        cursor.execute("""
            INSERT INTO pedidos (cliente_nome, produto_nome, quantidade, valor_unitario, valor_total, forma_pagamento, pago, custo_unitario, data_venda)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nome, item["nome"], item["quantidade"], item["preco"], total, forma_pagamento, pago, custo_unit, data_agora))
        atualizar_estoque(item["id"], -item["quantidade"])
    conn.commit()

def gerar_whatsapp(nome, itens, forma_pagamento="agora"):
    pagamento_txt = "Pagamento na hora" if forma_pagamento == "agora" else "Pagar depois (proximo mes)"
    linhas = [f"Ola! Gostaria de fazer um pedido.", f"Nome: {nome}", f"Pagamento: {pagamento_txt}", ""]
    total_geral = 0
    for item in itens:
        subtotal = item["quantidade"] * item["preco"]
        total_geral += subtotal
        linhas.append(f"- {item['nome']} x{item['quantidade']} - {brl(subtotal)}")
    linhas += ["", f"Total: {brl(total_geral)}"]
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
if "admin_logado" not in st.session_state:
    st.session_state.admin_logado = False

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
    padding-top: 3.5rem !important;
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

        forma = st.radio(
            "Forma de pagamento",
            ["Pagar agora", "Pagar depois"],
            horizontal=True,
            key="forma_pagamento"
        )
        forma_val = "agora" if forma == "Pagar agora" else "depois"

        if forma_val == "agora":
            st.markdown(f"""
            <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:12px;
            padding:14px;margin:10px 0;text-align:center;">
                <div style="font-size:0.75rem;font-weight:700;color:#166534;text-transform:uppercase;
                letter-spacing:0.5px;margin-bottom:6px;">Chave PIX</div>
                <div style="font-size:1rem;font-weight:800;color:#15803d;
                background:white;border-radius:8px;padding:8px;letter-spacing:1px;">
                    {PIX_CHAVE}
                </div>
            </div>
            """, unsafe_allow_html=True)
            qr_buf = gerar_qrcode_pix(total_carrinho())
            st.image(qr_buf, caption=f"QR Code PIX — {brl(total_carrinho())}", use_container_width=True)

        if st.button("Confirmar pedido", type="primary", use_container_width=True):
            if not nome.strip():
                st.warning("Por favor, informe seu nome.")
            else:
                salvar_pedido(nome, st.session_state.carrinho, forma_val)
                st.session_state.whatsapp_link = gerar_whatsapp(nome, st.session_state.carrinho, forma_val)
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
pagina = st.radio("", ["Produtos", "Contato", "Admin"], horizontal=True)


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
    estoque_atual = carregar_estoque()

    for i, p in enumerate(PRODUTOS):
        with cols[i % 2]:
            qtd_estoque = estoque_atual.get(p["id"], None)
            sem_estoque = qtd_estoque is not None and qtd_estoque == 0

            with st.container(border=True):
                col_img, col_info = st.columns([1, 1.4])
                with col_img:
                    if os.path.exists(p["imagem"]):
                        st.image(p["imagem"], width=180)
                with col_info:
                    st.caption(p["tag"])
                    st.subheader(p["nome"], divider=False)
                    st.caption(p["descricao"])
                    st.markdown(f"**{brl(p['preco'])}**")
                    if sem_estoque:
                        st.error("Esgotado", icon="🚫")
                    elif qtd_estoque is not None and qtd_estoque <= 3:
                        st.warning(f"Últimas {qtd_estoque} unidades")
                    elif qtd_estoque is not None:
                        st.success(f"Em estoque: {qtd_estoque}")

                col_qtd, col_btn = st.columns([1, 2])
                with col_qtd:
                    max_qtd = qtd_estoque if qtd_estoque is not None else 99
                    qtd = st.number_input("Qtd", min_value=1, max_value=max(1, max_qtd), step=1, value=1, key=f"qtd_{p['id']}", label_visibility="collapsed", disabled=sem_estoque)
                with col_btn:
                    if sem_estoque:
                        st.button("Esgotado", key=f"btn_{p['id']}", use_container_width=True, disabled=True)
                    else:
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


# =========================
# PÁGINA ADMIN
# =========================
elif pagina == "Admin":

    if not st.session_state.admin_logado:
        st.markdown('<div class="section-title">Acesso Restrito</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Insira a senha para acessar o painel administrativo</div>', unsafe_allow_html=True)

        col_login, _ = st.columns([1, 2])
        with col_login:
            senha = st.text_input("Senha", type="password", placeholder="Digite a senha")
            if st.button("Entrar", type="primary", use_container_width=True):
                if senha == ADMIN_SENHA:
                    st.session_state.admin_logado = True
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
    else:
        col_titulo, col_sair = st.columns([4, 1])
        with col_titulo:
            st.markdown('<div class="section-title">Painel Administrativo</div>', unsafe_allow_html=True)
        with col_sair:
            if st.button("Sair", use_container_width=True):
                st.session_state.admin_logado = False
                st.rerun()

        df = carregar_vendas()

        # MÉTRICAS
        df_pagos       = df[df["pago"] == 1] if not df.empty and "pago" in df.columns else df
        faturamento    = df_pagos["valor_total"].sum() if not df_pagos.empty else 0
        a_receber_top  = df[df["pago"] == 0]["valor_total"].sum() if not df.empty and "pago" in df.columns else 0
        itens_vendidos = int(df["quantidade"].sum()) if not df.empty else 0
        num_clientes   = int(df["cliente_nome"].nunique()) if not df.empty else 0
        num_pedidos    = len(df) if not df.empty else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Receita (pago)", brl(faturamento))
        c2.metric("A Receber",      brl(a_receber_top))
        c3.metric("Clientes",       num_clientes)
        c4.metric("Pedidos",           num_pedidos)

        st.divider()

        aba_visao, aba_financeiro, aba_cobranca, aba_estoque, aba_pedidos = st.tabs(["Visao Geral", "Financeiro", "Cobrar Clientes", "Estoque", "Todos os Pedidos"])

        if True:

            # ── ABA 1: VISÃO GERAL ──
            with aba_visao:
                if df.empty:
                    st.info("Nenhum pedido registrado ainda.")
                else:
                    col_tp, col_tc = st.columns(2)
                    with col_tp:
                        st.subheader("Top Produtos")
                        top_prod = (
                            df.groupby("produto_nome", as_index=False)["quantidade"]
                            .sum().sort_values("quantidade", ascending=False).head(5)
                        )
                        top_prod.columns = ["Produto", "Qtd Vendida"]
                        st.dataframe(top_prod, use_container_width=True, hide_index=True)
                    with col_tc:
                        st.subheader("Top Clientes")
                        top_cli = (
                            df.groupby("cliente_nome", as_index=False)["valor_total"]
                            .sum().sort_values("valor_total", ascending=False).head(5)
                        )
                        top_cli["valor_total"] = top_cli["valor_total"].apply(brl)
                        top_cli.columns = ["Cliente", "Total Gasto"]
                        st.dataframe(top_cli, use_container_width=True, hide_index=True)

            # ── ABA 2: FINANCEIRO ──
            with aba_financeiro:
                if df.empty:
                    st.info("Nenhum pedido registrado ainda.")
                else:
                    df_pago   = df[df["pago"] == 1]
                    df_pendente = df[df["pago"] == 0]

                    receita       = df_pago["valor_total"].sum()
                    custo_total   = (df_pago["custo_unitario"] * df_pago["quantidade"]).sum() if "custo_unitario" in df_pago.columns and not df_pago.empty else 0
                    lucro         = receita - custo_total
                    margem        = (lucro / receita * 100) if receita > 0 else 0
                    a_receber     = df_pendente["valor_total"].sum()
                    lucro_label   = "Lucro" if lucro >= 0 else "Prejuizo"
                    cor_lucro     = "#22c55e" if lucro >= 0 else "#ef4444"

                    # ── Cards de métricas ──
                    cf1, cf2, cf3, cf4 = st.columns(4)
                    cf1.metric("Receita (pago)", brl(receita))
                    cf2.metric("Gastos", brl(custo_total))
                    cf3.metric(lucro_label, brl(abs(lucro)), delta=f"{margem:.1f}% margem", delta_color="normal" if lucro >= 0 else "inverse")
                    cf4.metric("A Receber", brl(a_receber))

                    st.divider()

                    # ── Gráfico visual de barras ──
                    st.subheader("Resumo Financeiro")
                    barras = [
                        ("Receita",    receita,     "#22c55e"),
                        ("Gastos",     custo_total, "#f59e0b"),
                        (lucro_label,  abs(lucro),  cor_lucro),
                        ("A Receber",  a_receber,   "#3b82f6"),
                    ]
                    max_val = max(v for _, v, _ in barras) or 1
                    for label, valor, cor in barras:
                        pct = valor / max_val * 100
                        st.markdown(f"""
                        <div style="margin-bottom:14px;">
                            <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
                                <span style="font-weight:700;color:#0f172a;font-size:0.95rem;">{label}</span>
                                <span style="font-weight:800;color:{cor};font-size:0.95rem;">{brl(valor)}</span>
                            </div>
                            <div style="background:#e2e8f0;border-radius:8px;height:24px;overflow:hidden;">
                                <div style="width:{pct:.1f}%;background:{cor};height:100%;border-radius:8px;"></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    st.divider()

                    # ── Margem por produto ──
                    st.subheader("Margem por Produto")
                    custos_db_fin = carregar_custos()
                    for p in PRODUTOS:
                        if p["id"] not in custos_db_fin:
                            continue
                        custo_p   = custos_db_fin[p["id"]]
                        margem_p  = p["preco"] - custo_p
                        mpct      = (margem_p / p["preco"] * 100) if p["preco"] > 0 else 0
                        cor_m     = "#22c55e" if margem_p >= 0 else "#ef4444"
                        pct_bar   = max(0, min(100, mpct))
                        st.markdown(f"""
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;margin-bottom:10px;">
                            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                                <span style="font-weight:700;color:#0f172a;">{p['nome']}</span>
                                <span style="color:#64748b;font-size:0.88rem;">
                                    Venda <b>{brl(p['preco'])}</b> &nbsp;|&nbsp; Custo <b>{brl(custo_p)}</b> &nbsp;|&nbsp;
                                    <span style="color:{cor_m};font-weight:700;">Margem {brl(margem_p)} ({mpct:.0f}%)</span>
                                </span>
                            </div>
                            <div style="background:#e2e8f0;border-radius:6px;height:8px;overflow:hidden;">
                                <div style="width:{pct_bar:.1f}%;background:{cor_m};height:100%;border-radius:6px;"></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)


            # ── ABA 3: COBRANÇAS POR CLIENTE ──
            with aba_cobranca:
                df_pagar = df[df["pago"] == 0] if "pago" in df.columns else pd.DataFrame()

                if df_pagar.empty:
                    st.success("Nenhum valor pendente. Todos os clientes estao em dia!")
                else:
                    total_pendente = df_pagar["valor_total"].sum()
                    st.markdown(f"""
                    <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;
                    padding:16px 20px;margin-bottom:20px;">
                        <div style="font-size:0.8rem;color:#9a3412;font-weight:600;text-transform:uppercase;">
                            Total a receber
                        </div>
                        <div style="font-size:1.8rem;font-weight:800;color:#9a3412;">{brl(total_pendente)}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    clientes_pendentes = df_pagar["cliente_nome"].unique()
                    cliente_sel = st.selectbox("Filtrar por cliente", ["Todos"] + sorted(clientes_pendentes.tolist()))

                    df_filtrado = df_pagar if cliente_sel == "Todos" else df_pagar[df_pagar["cliente_nome"] == cliente_sel]

                    for cliente in (clientes_pendentes if cliente_sel == "Todos" else [cliente_sel]):
                        pedidos_cli = df_filtrado[df_filtrado["cliente_nome"] == cliente]
                        total_cli = pedidos_cli["valor_total"].sum()

                        col_cli, col_btn_pago = st.columns([4, 1])
                        with col_cli:
                            st.markdown(f"""
                            <div style="background:white;border:1px solid #e2e8f0;border-left:5px solid #f59e0b;
                            border-radius:12px;padding:14px 18px;margin-bottom:4px;">
                                <div style="font-weight:700;font-size:1rem;color:#0f172a;">{cliente}</div>
                                <div style="color:#64748b;font-size:0.85rem;margin-top:4px;">
                                    {len(pedidos_cli)} item(ns) pendente(s)
                                </div>
                                <div style="font-weight:800;font-size:1.1rem;color:#d97706;margin-top:6px;">
                                    A receber: {brl(total_cli)}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_btn_pago:
                            st.markdown("<div style='margin-top:18px;'></div>", unsafe_allow_html=True)
                            if st.button("Marcar pago", key=f"pago_{cliente}", use_container_width=True, type="primary"):
                                marcar_pago_cliente(cliente)
                                st.success(f"{cliente} marcado como pago!")
                                st.rerun()

                        with st.expander(f"Ver itens de {cliente}"):
                            for _, row in pedidos_cli.iterrows():
                                st.markdown(f"- **{row['produto_nome']}** x{int(row['quantidade'])} — {brl(row['valor_total'])}")

            # ── ABA 3: ESTOQUE ──
            with aba_estoque:
                st.subheader("Controle de Estoque")
                estoque_db = carregar_estoque()
                custos_db = carregar_custos()
                produtos_com_estoque = [p for p in PRODUTOS if p["id"] in estoque_db]

                st.caption("Qtd = unidades em estoque | Custo = valor pago por unidade na ultima compra")
                col_h1, col_h2, col_h3, col_h4 = st.columns([2.5, 1.2, 1.2, 1.5])
                col_h1.markdown("**Produto**")
                col_h2.markdown("**Qtd**")
                col_h3.markdown("**Custo (R$)**")

                for p in produtos_com_estoque:
                    qtd_atual = estoque_db.get(p["id"], 0)
                    custo_atual = custos_db.get(p["id"], 0.0)
                    if qtd_atual == 0:
                        cor, label = "#fee2e2", "Esgotado"
                    elif qtd_atual <= 3:
                        cor, label = "#fff7ed", f"{qtd_atual} un."
                    else:
                        cor, label = "#f0fdf4", f"{qtd_atual} un."

                    col_nome, col_qtd, col_custo, col_btn = st.columns([2.5, 1.2, 1.2, 1.5])
                    with col_nome:
                        st.markdown(f"""
                        <div style="background:{cor};border-radius:10px;padding:10px 14px;margin-bottom:4px;">
                            <div style="font-weight:700;color:#0f172a;">{p['nome']}</div>
                            <div style="font-size:0.82rem;color:#64748b;">Estoque: <b>{label}</b> | Custo: <b>{brl(custo_atual)}</b></div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_qtd:
                        nova_qtd = st.number_input("Qtd", min_value=0, step=1, value=qtd_atual, key=f"est_{p['id']}", label_visibility="collapsed")
                    with col_custo:
                        novo_custo = st.number_input("Custo", min_value=0.0, step=0.01, value=float(custo_atual), key=f"custo_{p['id']}", label_visibility="collapsed", format="%.2f")
                    with col_btn:
                        st.markdown("<div style='margin-top:4px;'></div>", unsafe_allow_html=True)
                        if st.button("Atualizar", key=f"upd_est_{p['id']}", use_container_width=True):
                            definir_estoque(p["id"], int(nova_qtd))
                            definir_custo(p["id"], float(novo_custo))
                            st.success(f"{p['nome']} atualizado!")
                            st.rerun()

                st.info("Cappuccino em Po nao tem controle de estoque (vendido por dose).")

            # ── ABA 4: TODOS OS PEDIDOS ──
            with aba_pedidos:
                if df.empty:
                    st.info("Nenhum pedido registrado ainda.")
                else:
                    col_ped, col_limpar = st.columns([4, 1])
                    with col_ped:
                        st.subheader("Todos os Pedidos")
                    with col_limpar:
                        if st.button("Limpar tudo", use_container_width=True):
                            limpar_pedidos()
                            st.success("Todos os pedidos removidos.")
                            st.rerun()

                for _, row in df.iterrows():
                    pago_col   = int(row["pago"]) if "pago" in row else 1
                    status_cor = "#22c55e" if pago_col else "#f59e0b"
                    status_txt = "Pago" if pago_col else "Pendente"
                    data_txt   = str(row["data_venda"])[:16] if "data_venda" in row and row["data_venda"] else "—"
                    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1.6, 2, 0.6, 1.0, 1.4, 1.1, 0.9, 0.9])
                    col1.write(row["cliente_nome"])
                    col2.write(row["produto_nome"])
                    col3.write(int(row["quantidade"]))
                    col4.write(brl(row["valor_unitario"]))
                    col5.caption(data_txt)
                    novo_total = col6.number_input(
                        "Valor", min_value=0.0, step=0.01,
                        value=float(row["valor_total"]),
                        key=f"edit_val_{row['id']}",
                        label_visibility="collapsed", format="%.2f"
                    )
                    if novo_total != float(row["valor_total"]):
                        if col7.button("Salvar", key=f"save_{row['id']}", type="primary"):
                            editar_venda(int(row["id"]), novo_total)
                            st.rerun()
                    else:
                        col7.markdown(f'<span style="color:{status_cor};font-weight:700;">{status_txt}</span>', unsafe_allow_html=True)
                    if col8.button("Excluir", key=f"del_{row['id']}"):
                        deletar_pedido(int(row["id"]))
                        st.rerun()
