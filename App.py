import os
from supabase import create_client
from urllib.parse import quote
import base64
import io
from datetime import date

import streamlit as st
import streamlit.components.v1 as components
import qrcode
from PIL import Image

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Loja Yago", layout="wide", page_icon="🛒")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

def render_imagem_produto(caminho, alt="", bg="transparent", img_h=120):
    # Detecta o formato real do arquivo (ignora extensão — ex: PNG salvo como .jpg)
    try:
        with Image.open(caminho) as _img:
            mime = "image/png" if _img.format == "PNG" else "image/jpeg"
    except Exception:
        ext  = caminho.rsplit(".", 1)[-1].lower()
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"

    b64 = img_base64(caminho)
    if b64:
        img_html = (f'<img src="data:{mime};base64,{b64}" alt="{alt}" '
                    f'style="max-height:{img_h}px;max-width:100%;object-fit:contain;'
                    f'filter:drop-shadow(0 4px 10px rgba(0,0,0,0.07));'
                    f'transition:transform 0.25s ease-out;"'
                    f'onmouseover="this.style.transform=\'scale(1.04)\'"'
                    f'onmouseout="this.style.transform=\'scale(1)\'">')
    else:
        img_html = f'<div style="height:{img_h}px;"></div>'

    html = (
        f'<div style="background:{bg};border-radius:14px;padding:12px;'
        'display:flex;align-items:center;justify-content:center;height:150px;'
        'overflow:hidden;">'
        + img_html + '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# =========================
# PRODUTOS
# =========================
def produto_is_novo(data_criacao_str, dias=7):
    """Retorna True se o produto foi criado há menos de `dias` dias."""
    try:
        criado = date.fromisoformat(data_criacao_str)
        return (date.today() - criado).days <= dias
    except Exception:
        return False

_PRODUTOS_BASE = [
    {
        "id": 5,
        "nome": "Coca Cola",
        "preco": 6.00,
        "imagem": caminho_imagem("Coca_Cola_Branco-removebg-preview.png"),
        "descricao": "Refrigerante gelado. Clássico e refrescante.",
        "tag": "Bebida",
        "criado_em": "2026-03-27",
    },
    {
        "id": 1,
        "nome": "Cappuccino 260 ml",
        "preco": 10.00,
        "imagem": caminho_imagem("cappuccino_260ml.png"),
        "descricao": "Bebida pronta para consumo. Gelada, cremosa e deliciosa.",
        "tag": "Bebida",
        "criado_em": "2026-01-01",
    },
    {
        "id": 2,
        "nome": "Barra de Proteína",
        "preco": 12.00,
        "imagem": caminho_imagem("barra_proteina.png"),
        "descricao": "Alta em proteína, ideal para o dia a dia ativo.",
        "tag": "Proteína",
        "criado_em": "2026-01-01",
    },
    {
        "id": 3,
        "nome": "Cappuccino em Pó",
        "preco": 6.00,
        "imagem": caminho_imagem("cappuccino_po.png"),
        "descricao": "Mistura especial para preparo de cappuccino cremoso.",
        "tag": "Bebida",
        "criado_em": "2026-01-01",
    },
    {
        "id": 4,
        "nome": "Iogurte Proteico",
        "preco": 10.00,
        "imagem": caminho_imagem("iogurte_proteico.png"),
        "descricao": "Rico em proteínas, sabor suave e textura cremosa.",
        "tag": "Proteína",
        "criado_em": "2026-01-01",
    },
]


# =========================
# BANCO DE DADOS (Supabase)
# =========================
@st.cache_resource
def get_sb():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

sb = get_sb()

def _init_db():
    # Custos — só insere se a tabela estiver vazia, nunca sobrescreve custos editados
    if not sb.table("custos").select("produto_id").execute().data:
        sb.table("custos").insert([
            {"produto_id": 1, "produto_nome": "Cappuccino 260 ml", "custo": 7.30},
            {"produto_id": 2, "produto_nome": "Barra de Proteína",  "custo": 5.14},
            {"produto_id": 4, "produto_nome": "Iogurte Proteico",   "custo": 6.00},
            {"produto_id": 5, "produto_nome": "Coca Cola",           "custo": 4.00},
        ]).execute()
    # Estoque — só insere se a tabela estiver vazia, nunca sobrescreve quantidades editadas
    if not sb.table("estoque").select("produto_id").execute().data:
        sb.table("estoque").insert([
            {"produto_id": 1, "produto_nome": "Cappuccino 260 ml", "quantidade": 11},
            {"produto_id": 2, "produto_nome": "Barra de Proteína",  "quantidade": 19},
            {"produto_id": 4, "produto_nome": "Iogurte Proteico",   "quantidade": 3},
            {"produto_id": 5, "produto_nome": "Coca Cola",           "quantidade": 20},
        ]).execute()
    # Preços — só insere se a tabela estiver vazia, nunca sobrescreve preços editados
    if not sb.table("precos").select("produto_id").execute().data:
        sb.table("precos").insert([
            {"produto_id": p["id"], "produto_nome": p["nome"], "preco": p["preco"]}
            for p in _PRODUTOS_BASE
        ]).execute()

if "_db_initialized" not in st.session_state:
    _init_db()
    st.session_state["_db_initialized"] = True

import pandas as pd

def carregar_vendas():
    data = sb.table("pedidos").select("*").order("id", desc=True).execute().data
    cols = ["id","cliente_nome","produto_nome","quantidade","valor_unitario",
            "valor_total","forma_pagamento","pago","custo_unitario","data_venda","origem","observacao","telefone"]
    df = pd.DataFrame(data) if data else pd.DataFrame(columns=cols)
    if not df.empty:
        df["pago"]           = pd.to_numeric(df.get("pago"),           errors="coerce").fillna(1).astype(int)
        df["quantidade"]     = pd.to_numeric(df.get("quantidade"),     errors="coerce").fillna(0).astype(int)
        df["valor_total"]    = pd.to_numeric(df.get("valor_total"),    errors="coerce").fillna(0.0).astype(float)
        df["valor_unitario"] = pd.to_numeric(df.get("valor_unitario"), errors="coerce").fillna(0.0).astype(float)
        df["custo_unitario"] = pd.to_numeric(df.get("custo_unitario"), errors="coerce").fillna(0.0).astype(float)
    return df

def deletar_pedido(pedido_id):
    sb.table("pedidos").delete().eq("id", pedido_id).execute()

def limpar_pedidos():
    sb.table("pedidos").delete().neq("id", 0).execute()

def marcar_pago(pedido_id):
    sb.table("pedidos").update({"pago": 1}).eq("id", int(pedido_id)).execute()

def marcar_pago_cliente(cliente_nome):
    sb.table("pedidos").update({"pago": 1}).eq("cliente_nome", cliente_nome).eq("pago", 0).execute()

def carregar_custos():
    data = sb.table("custos").select("produto_id,custo").execute().data
    return {row["produto_id"]: row["custo"] for row in data}

def definir_custo(produto_id, custo):
    sb.table("custos").update({"custo": custo}).eq("produto_id", produto_id).execute()

def editar_venda(pedido_id, novo_valor_total):
    sb.table("pedidos").update({"valor_total": novo_valor_total}).eq("id", int(pedido_id)).execute()

def carregar_estoque():
    data = sb.table("estoque").select("produto_id,quantidade").execute().data
    return {row["produto_id"]: row["quantidade"] for row in data}

def atualizar_estoque(produto_id, delta):
    atual = sb.table("estoque").select("quantidade").eq("produto_id", produto_id).execute().data
    if atual:
        sb.table("estoque").update({"quantidade": max(0, atual[0]["quantidade"] + delta)}).eq("produto_id", produto_id).execute()

def definir_estoque(produto_id, quantidade):
    sb.table("estoque").update({"quantidade": quantidade}).eq("produto_id", produto_id).execute()

def carregar_precos():
    data = sb.table("precos").select("produto_id,preco").execute().data
    return {row["produto_id"]: row["preco"] for row in data}

def definir_preco(produto_id, preco):
    sb.table("precos").update({"preco": float(preco)}).eq("produto_id", int(produto_id)).execute()

def salvar_pedido(nome, itens, forma_pagamento):
    from datetime import datetime
    pago = 1 if forma_pagamento == "agora" else 0
    custos_db  = carregar_custos()
    estoque_db = carregar_estoque()
    data_agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    for item in itens:
        total      = item["quantidade"] * item["preco"]
        custo_unit = custos_db.get(item["id"], 0.0)
        sb.table("pedidos").insert({
            "cliente_nome":    nome,
            "produto_nome":    item["nome"],
            "quantidade":      int(item["quantidade"]),
            "valor_unitario":  float(item["preco"]),
            "valor_total":     float(total),
            "forma_pagamento": forma_pagamento,
            "pago":            int(pago),
            "custo_unitario":  float(custo_unit),
            "data_venda":      data_agora,
            "origem":          "site",
            "observacao":      "",
        }).execute()
        if item["id"] in estoque_db:
            new_qty = max(0, estoque_db[item["id"]] - item["quantidade"])
            sb.table("estoque").update({"quantidade": new_qty}).eq("produto_id", item["id"]).execute()

def salvar_venda_manual(cliente_nome, produto_nome, produto_id,
                         quantidade, valor_unitario, custo_unitario,
                         pago, data_venda, observacao, telefone=""):
    valor_total     = quantidade * valor_unitario
    forma_pagamento = "agora" if pago else "depois"
    estoque_db      = carregar_estoque()
    sb.table("pedidos").insert({
        "cliente_nome":    cliente_nome,
        "produto_nome":    produto_nome,
        "quantidade":      int(quantidade),
        "valor_unitario":  float(valor_unitario),
        "valor_total":     float(valor_total),
        "forma_pagamento": forma_pagamento,
        "pago":            int(pago),
        "custo_unitario":  float(custo_unitario),
        "data_venda":      data_venda,
        "origem":          "manual",
        "observacao":      observacao,
        "telefone":        telefone.strip() if telefone else "",
    }).execute()
    if produto_id is not None and produto_id in estoque_db:
        new_qty = max(0, estoque_db[produto_id] - quantidade)
        sb.table("estoque").update({"quantidade": new_qty}).eq("produto_id", produto_id).execute()

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


# Computa PRODUTOS com preços do banco (atualizado a cada rerun)
_precos_db = carregar_precos()
PRODUTOS = [{**p, "preco": _precos_db.get(p["id"], p["preco"])} for p in _PRODUTOS_BASE]


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
if "nome_editando" not in st.session_state:
    st.session_state.nome_editando = not bool(st.query_params.get("nome", "").strip())

# Nome do cliente disponível em todo o app (sidebar + Meus Pedidos)
nome_persistido = st.query_params.get("nome", "").strip()
# Telefone persistido via URL param ?tel= (usado em Meus Pedidos para vendas manuais)
tel_persistido  = st.query_params.get("tel", "").strip()

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

/* ── CARD DE PRODUTO ── */

/* ── CARD ── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 18px !important;
    border: 1px solid #eaeef3 !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.05) !important;
    background: #ffffff !important;
    overflow: hidden !important;
    transition: box-shadow 0.25s ease-out, transform 0.25s ease-out !important;
    padding: 0 !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: 0 8px 24px rgba(0,0,0,0.10) !important;
    transform: translateY(-3px) !important;
}

/* Remove padding excessivo dos blocos internos */
[data-testid="stVerticalBlockBorderWrapper"] > div > div {
    padding: 0 !important;
}

/* ── INFO DO PRODUTO ── */
.pc-info {
    padding: 16px 14px 10px 6px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    height: 100%;
}
.pc-toprow {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 3px;
}
.pc-tag {
    font-size: 0.62rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    background: #f1f5f9;
    padding: 2px 9px;
    border-radius: 20px;
}
.pc-nome {
    font-size: 1.08rem;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.28;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    margin-bottom: 1px;
    letter-spacing: -0.2px;
}
.pc-desc {
    font-size: 0.76rem;
    color: #7c8fa1;
    line-height: 1.45;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    margin-bottom: 5px;
}
.pc-preco {
    font-size: 1.42rem;
    font-weight: 800;
    color: #111827;
    letter-spacing: -0.6px;
    margin-top: 1px;
}

/* ── BADGES DE ESTOQUE ── */
.pc-badge-ok, .pc-badge-alerta, .pc-badge-esgotado {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 700;
    padding: 3px 11px;
    border-radius: 99px;
    letter-spacing: 0.2px;
}
.pc-badge-ok       { background: #dcfce7; color: #15803d; }
.pc-badge-alerta   { background: #fef9c3; color: #92400e; }
.pc-badge-esgotado { background: #fee2e2; color: #991b1b; }

/* ── BOTÃO PRIMÁRIO ── */
[data-testid="stBaseButton-primary"] button,
button[kind="primary"],
[data-testid="stBaseButton-primary"] {
    background: #ef4444 !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.2px !important;
    transition: background 0.2s ease, transform 0.2s ease !important;
}
[data-testid="stBaseButton-primary"]:hover {
    background: #dc2626 !important;
    transform: scale(1.02) !important;
}

/* Number input — moderno e integrado */
[data-testid="stNumberInput"] {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
[data-testid="stNumberInput"] input {
    text-align: center !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    border-radius: 10px !important;
    border-color: #e2e8f0 !important;
    background: #f8fafc !important;
    color: #0f172a !important;
    padding: 6px 4px !important;
}
[data-testid="stNumberInput"] button {
    border-radius: 8px !important;
    border-color: #e2e8f0 !important;
    background: #f1f5f9 !important;
    color: #475569 !important;
    font-weight: 700 !important;
}
/* Área abaixo do card (qty + botão) */
.pc-actions {
    padding: 0 10px 10px 10px;
}

/* SIDEBAR CART */
[data-testid="stSidebar"] {
    background: white;
    border-right: 1px solid #e2e8f0;
}

/* Campo "Seu nome" — destaque obrigatório */
[data-testid="stSidebar"] [data-testid="stTextInput"] input {
    background: #f8fafc !important;
    border: 2px solid #cbd5e1 !important;
    border-radius: 10px !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    color: #0f172a !important;
    padding: 10px 14px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] input::placeholder {
    color: #94a3b8 !important;
    font-weight: 400 !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] input:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
    background: #ffffff !important;
    outline: none !important;
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

/* Imagens dos produtos são renderizadas via HTML/base64 — sem regras conflitantes */

/* Badge NOVO */
.badge-novo {
    display: inline-block;
    background: linear-gradient(135deg, #ef4444, #dc2626);
    color: white;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    padding: 2px 9px;
    border-radius: 20px;
    margin-left: 6px;
    vertical-align: middle;
    box-shadow: 0 2px 6px rgba(239,68,68,0.35);
}

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
    color: #0f172a !important;
}
div[data-testid="stRadio"] > div > label p {
    color: #0f172a !important;
}

/* ═══════════════════════════════════
   RESPONSIVIDADE MOBILE (≤ 640px)
   ═══════════════════════════════════ */
@media (max-width: 640px) {

    /* Página: reduz padding lateral */
    .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        padding-top: 2rem !important;
    }

    /* Hero: compacta banner */
    .hero {
        padding: 26px 18px !important;
        margin-bottom: 20px !important;
    }
    .hero h1 { font-size: 1.45rem !important; }
    .hero p  { font-size: 0.88rem !important; }

    /* ── GRADE EXTERNA: cards passam para 1 coluna ── */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }
    [data-testid="stColumn"] {
        min-width: 100% !important;
        width: 100% !important;
        flex: 1 1 100% !important;
    }

    /* Exceção: colunas DENTRO do card (img|info e qty|btn) ficam lado a lado */
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stColumn"] {
        min-width: 0 !important;
        width: auto !important;
        flex: 1 1 auto !important;
    }

    /* ── CARD: tipografia e espaçamento ── */
    .pc-info  { padding: 12px 10px 8px 4px !important; gap: 3px !important; }
    .pc-nome  { font-size: 0.92rem !important; }
    .pc-desc  { font-size: 0.71rem !important; }
    .pc-preco { font-size: 1.18rem !important; }

    /* ── BOTÃO: touch target confortável ── */
    [data-testid="stBaseButton-primary"] {
        min-height: 46px !important;
        font-size: 0.9rem !important;
    }

    /* ── NUMBER INPUT: maior para toque ── */
    [data-testid="stNumberInput"] input {
        min-height: 42px !important;
        font-size: 1rem !important;
    }
    [data-testid="stNumberInput"] button {
        min-height: 42px !important;
    }

    /* ── CAMPO NOME: confortável no celular ── */
    [data-testid="stSidebar"] [data-testid="stTextInput"] input {
        min-height: 50px !important;
        font-size: 1rem !important;
        padding: 12px 14px !important;
    }

    /* ── SECTION TITLES ── */
    .section-title { font-size: 1.2rem !important; }
    .section-sub   { font-size: 0.82rem !important; margin-bottom: 16px !important; }

    /* ── GAP entre cards ── */
    [data-testid="stVerticalBlockBorderWrapper"] {
        margin-bottom: 10px !important;
    }

    /* ── ADMIN: abas — scroll + contraste no mobile ── */
    [data-testid="stTabBar"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        -webkit-overflow-scrolling: touch !important;
        scrollbar-width: none !important;
        background: #1e3a5f !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 2px !important;
        border-bottom: none !important;
    }
    [data-testid="stTabBar"]::-webkit-scrollbar { display: none !important; }

    /* Aba inativa: texto claro sobre fundo escuro */
    button[data-testid="stTab"] {
        white-space: nowrap !important;
        flex-shrink: 0 !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        padding: 8px 12px !important;
        color: #93c5fd !important;
        background: transparent !important;
        border: none !important;
        border-radius: 8px !important;
        border-bottom: none !important;
    }

    /* Aba ativa: destaque branco */
    button[data-testid="stTab"][aria-selected="true"] {
        background: #ffffff !important;
        color: #0f172a !important;
        font-weight: 700 !important;
    }

    /* ── ADMIN: st.metric legível em 1 coluna ── */
    [data-testid="stMetricLabel"] p  { font-size: 0.7rem !important; }
    [data-testid="stMetricValue"] > div { font-size: 1.15rem !important; font-weight: 800 !important; }
    [data-testid="stMetricDelta"] > div { font-size: 0.7rem !important; }

    /* ── ADMIN: dataframes com scroll horizontal ── */
    [data-testid="stDataFrame"] { overflow-x: auto !important; }

    /* ── LABELS DE FORMULÁRIO: visibilidade completa no mobile ── */

    /* Contêiner do label: nunca escondido */
    [data-testid="stWidgetLabel"] {
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        margin-bottom: 4px !important;
    }

    /* Todo elemento filho do label: cor escura, visível */
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] *,
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] label,
    [data-testid="stWidgetLabel"] span,
    [data-testid="stWidgetLabel"] div {
        color: #1e293b !important;
        opacity: 1 !important;
        visibility: visible !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
    }

    /* Cobre variações de estrutura HTML do Streamlit */
    [data-testid="stTextInput"]   > label,
    [data-testid="stTextInput"]   > div > label,
    [data-testid="stSelectbox"]   > label,
    [data-testid="stSelectbox"]   > div > label,
    [data-testid="stNumberInput"] > label,
    [data-testid="stNumberInput"] > div > label,
    [data-testid="stTextArea"]    > label,
    [data-testid="stTextArea"]    > div > label,
    [data-testid="stDateInput"]   > label,
    [data-testid="stDateInput"]   > div > label,
    [data-testid="stRadio"]       > label,
    [data-testid="stRadio"]       > div > label {
        color: #1e293b !important;
        opacity: 1 !important;
        visibility: visible !important;
        display: block !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        margin-bottom: 4px !important;
    }

    /* Texto digitado nos inputs */
    [data-testid="stTextInput"]   input,
    [data-testid="stNumberInput"] input,
    [data-testid="stTextArea"]    textarea {
        color: #0f172a !important;
        background: #ffffff !important;
        opacity: 1 !important;
    }

    /* Selectbox: texto da opção selecionada */
    [data-baseweb="select"] span,
    [data-baseweb="select"] div {
        color: #0f172a !important;
    }

    /* Caption e subheaders */
    [data-testid="stCaptionContainer"] p,
    [data-testid="stSubheader"] { color: #334155 !important; }

    /* ── RADIO: todos recebem estilo escuro (nav principal) ── */
    div[data-testid="stRadio"] > div {
        background: #1e3a5f !important;
        border-color: #3b82f6 !important;
        width: 100% !important;
        flex-wrap: wrap !important;
        gap: 4px !important;
        padding: 4px !important;
        border-radius: 14px !important;
    }
    div[data-testid="stRadio"] > div > label {
        color: #ffffff !important;
        padding: 11px 8px !important;
        font-size: 0.85rem !important;
        flex: 1 1 calc(50% - 8px) !important;
        min-width: calc(50% - 8px) !important;
        text-align: center !important;
        box-sizing: border-box !important;
        border-radius: 10px !important;
        line-height: 1.2 !important;
    }

    /* ── RADIO dentro de abas: estilo claro, horizontal ── */
    [data-testid="stTabsContent"] div[data-testid="stRadio"] > div {
        background: #f1f5f9 !important;
        border-color: #cbd5e1 !important;
        flex-wrap: nowrap !important;
        width: fit-content !important;
    }
    [data-testid="stTabsContent"] div[data-testid="stRadio"] > div > label {
        color: #0f172a !important;
        flex: 1 1 auto !important;
        min-width: unset !important;
    }

    /* ── RADIO sidebar (Pagar agora / Pagar depois): vertical e visivel ── */
    [data-testid="stSidebar"] div[data-testid="stRadio"] > div {
        background: #f1f5f9 !important;
        border-color: #cbd5e1 !important;
        flex-direction: column !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        gap: 6px !important;
        border-radius: 14px !important;
    }
    [data-testid="stSidebar"] div[data-testid="stRadio"] > div > label {
        color: #0f172a !important;
        background: #ffffff !important;
        border-radius: 10px !important;
        flex: 1 1 100% !important;
        width: 100% !important;
        min-width: 100% !important;
        text-align: center !important;
        padding: 10px 16px !important;
        box-sizing: border-box !important;
    }
    [data-testid="stSidebar"] div[data-testid="stRadio"] > div > label span,
    [data-testid="stSidebar"] div[data-testid="stRadio"] > div > label p {
        color: #0f172a !important;
    }

    /* ── CARDS DE PEDIDO: grid 2×2 no mobile ── */
    .pedido-row {
        display: grid !important;
        grid-template-columns: 1fr 1fr !important;
        gap: 10px 16px !important;
    }
    .pedido-card {
        padding: 12px 14px !important;
    }
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
    # ── JS: ao abrir a página, lê localStorage e injeta o nome na URL (1 reload) ──
    components.html("""
    <script>
    (function() {
        try {
            var saved = localStorage.getItem('loja_yago_nome');
            var params = new URLSearchParams(window.parent.location.search);
            if (saved && !params.has('nome')) {
                params.set('nome', saved);
                window.parent.location.search = params.toString();
            }
        } catch(e) {}
    })();
    </script>
    """, height=0)

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

        # ── Campo nome controlado ──
        if nome_persistido and not st.session_state.nome_editando:
            # Estado travado: exibe nome salvo
            st.markdown(
                f'<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;'
                f'padding:10px 14px;margin-bottom:6px;">'
                f'<div style="font-size:0.7rem;font-weight:700;color:#166534;text-transform:uppercase;'
                f'letter-spacing:0.5px;margin-bottom:3px;">Identificado como</div>'
                f'<div style="font-weight:800;color:#0f172a;font-size:1rem;">👤 {nome_persistido}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            if st.button("✏️ Alterar nome", key="btn_alterar_nome", use_container_width=True):
                st.session_state.nome_editando = True
                st.rerun()
            nome = nome_persistido
        else:
            # Estado de edição: campo livre + botão salvar
            label_txt = "Alterar nome" if nome_persistido else 'Seu nome <span style="color:#ef4444;">*</span>'
            st.markdown(
                f'<p style="font-size:0.85rem;font-weight:700;color:#0f172a;margin-bottom:4px;">{label_txt}</p>',
                unsafe_allow_html=True
            )
            nome_input = st.text_input(
                "Nome", value=nome_persistido,
                placeholder="Digite seu nome completo",
                label_visibility="collapsed", key="nome_input_field"
            )
            if nome_persistido:
                col_s, col_c = st.columns([3, 1])
            else:
                col_s = st.container()
                col_c = None
            with col_s:
                salvar_nome = st.button("Salvar nome", key="btn_salvar_nome",
                                        use_container_width=True, type="primary")
            if col_c:
                with col_c:
                    if st.button("✕", key="btn_cancelar_nome", use_container_width=True):
                        st.session_state.nome_editando = False
                        st.rerun()
            if salvar_nome:
                nome_limpo = (nome_input or "").strip()
                if len(nome_limpo) < 2:
                    st.warning("Nome deve ter pelo menos 2 caracteres.")
                elif not any(c.isalpha() for c in nome_limpo):
                    st.warning("Nome inválido. Use letras.")
                else:
                    st.query_params["nome"] = nome_limpo
                    st.session_state.nome_editando = False
                    components.html(
                        f"<script>try{{localStorage.setItem('loja_yago_nome',{repr(nome_limpo)})}}catch(e){{}}</script>",
                        height=0
                    )
                    st.rerun()
            nome = (nome_input or "").strip()

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
                estoque_atual_check = carregar_estoque()
                sem_estoque = []
                for item in st.session_state.carrinho:
                    qtd_disp = estoque_atual_check.get(item["id"], None)
                    if qtd_disp is not None and item["quantidade"] > qtd_disp:
                        sem_estoque.append(f"{item['nome']} (disponível: {qtd_disp})")
                if sem_estoque:
                    st.error("Estoque insuficiente: " + ", ".join(sem_estoque))
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
pagina = st.radio("", ["Produtos", "Meus Pedidos", "Contato", "Admin"], horizontal=True)


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
            is_novo     = produto_is_novo(p.get("criado_em", "2000-01-01"))

            # Badge de estoque em HTML
            if sem_estoque:
                badge_est = '<span class="pc-badge-esgotado">Esgotado</span>'
            elif qtd_estoque is not None and qtd_estoque <= 3:
                badge_est = f'<span class="pc-badge-alerta">Últimas {qtd_estoque} un.</span>'
            elif qtd_estoque is not None:
                badge_est = f'<span class="pc-badge-ok">Em estoque: {qtd_estoque}</span>'
            else:
                badge_est = ''

            badge_novo = '<span class="badge-novo">NOVO</span>' if is_novo else ""

            with st.container(border=True):
                # ── Linha superior: imagem | info (tudo HTML estático) ──
                col_img, col_info = st.columns([1, 1.4])
                with col_img:
                    img_bg = "#f1f3f5" if p["id"] == 5 else "transparent"
                    # Ajuste fino de tamanho por produto para equilíbrio visual
                    img_h = {
                        5: 138,   # Coca-Cola — maior
                        4: 132,   # Iogurte Proteico — maior
                        2: 108,   # Barra de Proteína — equilibrada
                        3: 114,   # Cappuccino em Pó — contido
                        1: 122,   # Cappuccino 260ml — padrão
                    }.get(p["id"], 120)
                    render_imagem_produto(p["imagem"], p["nome"], bg=img_bg, img_h=img_h)
                with col_info:
                    info_html = (
                        '<div class="pc-info">'
                        '<div class="pc-toprow">'
                        f'<span class="pc-tag">{p["tag"]}</span>{badge_novo}'
                        '</div>'
                        f'<div class="pc-nome">{p["nome"]}</div>'
                        f'<div class="pc-desc">{p["descricao"]}</div>'
                        f'<div class="pc-preco">{brl(p["preco"])}</div>'
                        f'<div style="margin-top:4px;">{badge_est}</div>'
                        '</div>'
                    )
                    st.markdown(info_html, unsafe_allow_html=True)

                # ── Linha inferior: quantidade + botão ──
                col_qtd, col_btn = st.columns([1, 2.5])
                with col_qtd:
                    max_qtd = qtd_estoque if qtd_estoque is not None else 99
                    qtd = st.number_input(
                        "Qtd", min_value=1, max_value=max(1, max_qtd),
                        step=1, value=1, key=f"qtd_{p['id']}",
                        label_visibility="collapsed", disabled=sem_estoque
                    )
                with col_btn:
                    if sem_estoque:
                        st.button("Esgotado", key=f"btn_{p['id']}", use_container_width=True, disabled=True)
                    else:
                        if st.button("Adicionar ao carrinho", key=f"btn_{p['id']}",
                                     use_container_width=True, type="primary"):
                            adicionar(p, int(qtd))
                            st.success(f"{p['nome']} adicionado!")
                            st.rerun()


# =========================
# PÁGINA MEUS PEDIDOS
# =========================
elif pagina == "Meus Pedidos":

    st.markdown('<div class="section-title">Meus Pedidos</div>', unsafe_allow_html=True)

    if not nome_persistido and not tel_persistido:
        # Mostrar formulário de identificação por telefone
        st.markdown("""
        <div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:14px;
        padding:24px;text-align:center;margin-top:16px;margin-bottom:16px;">
            <div style="font-size:2rem;margin-bottom:10px;">👤</div>
            <div style="font-weight:700;font-size:1rem;color:#92400e;margin-bottom:6px;">
                Identifique-se para ver seus pedidos
            </div>
            <div style="color:#78350f;font-size:0.88rem;">
                Digite seu número de telefone para acessar seus pedidos.
            </div>
        </div>
        """, unsafe_allow_html=True)
        col_tel_in, col_tel_btn = st.columns([3, 1])
        with col_tel_in:
            tel_input = st.text_input("Número de telefone (apenas números)", key="tel_identificacao",
                                      placeholder="Ex: 65999990000", label_visibility="collapsed")
        with col_tel_btn:
            if st.button("Entrar", type="primary", use_container_width=True, key="btn_identificar_tel"):
                tel_limpo = "".join(filter(str.isdigit, tel_input))
                if len(tel_limpo) >= 8:
                    st.query_params["tel"] = tel_limpo
                    st.rerun()
                else:
                    st.error("Informe um número de telefone válido.")
    else:
        df_todos = carregar_vendas()

        # Determina nome para exibição e filtro
        if nome_persistido:
            # Pedidos via site (identificado pelo nome)
            if df_todos.empty:
                df_cli = pd.DataFrame()
            else:
                df_cli = df_todos[
                    df_todos["cliente_nome"].str.strip().str.lower() == nome_persistido.lower()
                ].copy()
            nome_exibicao = nome_persistido
        else:
            # Pedidos via telefone (identificado pelo número)
            tel_limpo = "".join(filter(str.isdigit, tel_persistido))
            if df_todos.empty or "telefone" not in df_todos.columns:
                df_cli = pd.DataFrame()
            else:
                df_cli = df_todos[
                    df_todos["telefone"].fillna("").apply(lambda t: "".join(filter(str.isdigit, str(t)))) == tel_limpo
                ].copy()
            nome_exibicao = df_cli["cliente_nome"].iloc[0] if not df_cli.empty else tel_persistido
            # Botão para sair (limpar identificação)
            if st.button("Sair / Trocar número", key="btn_sair_tel"):
                del st.query_params["tel"]
                st.rerun()

        if df_cli.empty:
            st.markdown(f"""
            <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:14px;
            padding:24px;text-align:center;margin-top:16px;">
                <div style="font-size:2rem;margin-bottom:10px;">📦</div>
                <div style="font-weight:700;font-size:1rem;color:#0369a1;margin-bottom:6px;">
                    Olá, {nome_exibicao}!
                </div>
                <div style="color:#0c4a6e;font-size:0.88rem;">
                    Você ainda não tem pedidos registrados.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # ── Resumo do cliente ──
            total_pedidos  = len(df_cli)
            total_pago     = df_cli[df_cli["pago"] == 1]["valor_total"].sum()
            total_pendente = df_cli[df_cli["pago"] == 0]["valor_total"].sum()

            st.markdown(
                f'<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:12px;'
                f'padding:14px 18px;margin-bottom:20px;font-size:0.95rem;color:#0c4a6e;">'
                f'Olá, <b>{nome_exibicao}</b>! Aqui estão todas as suas compras.'
                f'</div>',
                unsafe_allow_html=True
            )

            st.markdown(
                f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px;">'
                f'<div style="flex:1;min-width:90px;background:#f8fafc;border:1px solid #e2e8f0;'
                f'border-radius:10px;padding:12px 14px;">'
                f'<div style="font-size:0.72rem;color:#64748b;font-weight:600;margin-bottom:4px;">Pedidos</div>'
                f'<div style="font-size:1.4rem;font-weight:800;color:#0f172a;">{total_pedidos}</div>'
                f'</div>'
                f'<div style="flex:1;min-width:90px;background:#f0fdf4;border:1px solid #86efac;'
                f'border-radius:10px;padding:12px 14px;">'
                f'<div style="font-size:0.72rem;color:#166534;font-weight:600;margin-bottom:4px;">Total pago</div>'
                f'<div style="font-size:1.4rem;font-weight:800;color:#15803d;">{brl(total_pago)}</div>'
                f'</div>'
                f'<div style="flex:1;min-width:90px;background:#fffbeb;border:1px solid #fcd34d;'
                f'border-radius:10px;padding:12px 14px;">'
                f'<div style="font-size:0.72rem;color:#92400e;font-weight:600;margin-bottom:4px;">Pendente</div>'
                f'<div style="font-size:1.4rem;font-weight:800;color:#d97706;">{brl(total_pendente)}</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )

            st.divider()

            # ── Lista de pedidos (mais recente primeiro) ──
            for _, row in df_cli.iterrows():
                pago_val   = int(row["pago"]) if "pago" in row else 1
                data_txt   = str(row["data_venda"])[:16] if row.get("data_venda") else "—"
                status_cor = "#22c55e" if pago_val else "#f59e0b"
                status_txt = "✅ Pago" if pago_val else "⏳ Pendente"
                borda_cor  = "#86efac" if pago_val else "#fcd34d"

                st.markdown(
                    f'<div style="background:white;border:1px solid {borda_cor};'
                    f'border-left:5px solid {borda_cor};border-radius:12px;'
                    f'padding:14px 16px;margin-bottom:10px;">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'align-items:flex-start;margin-bottom:10px;gap:8px;">'
                    f'<span style="font-weight:700;color:#0f172a;font-size:0.95rem;line-height:1.3;">'
                    f'{row["produto_nome"]}</span>'
                    f'<span style="font-weight:700;color:{status_cor};font-size:0.82rem;'
                    f'white-space:nowrap;">{status_txt}</span>'
                    f'</div>'
                    f'<table style="width:100%;border-collapse:collapse;">'
                    f'<tr>'
                    f'<td style="color:#64748b;font-size:0.78rem;padding:3px 0;">Quantidade</td>'
                    f'<td style="color:#64748b;font-size:0.78rem;padding:3px 0;">Valor unitário</td>'
                    f'</tr>'
                    f'<tr>'
                    f'<td style="font-weight:700;color:#0f172a;padding-bottom:8px;">'
                    f'{int(row["quantidade"])}x</td>'
                    f'<td style="font-weight:700;color:#0f172a;padding-bottom:8px;">'
                    f'{brl(row["valor_unitario"])}</td>'
                    f'</tr>'
                    f'<tr style="border-top:1px solid #e2e8f0;">'
                    f'<td style="font-weight:700;color:#64748b;font-size:0.78rem;padding-top:8px;">'
                    f'Total</td>'
                    f'<td style="font-weight:700;color:#64748b;font-size:0.78rem;padding-top:8px;">'
                    f'Data</td>'
                    f'</tr>'
                    f'<tr>'
                    f'<td style="font-weight:800;color:#0f172a;font-size:1.05rem;">'
                    f'{brl(row["valor_total"])}</td>'
                    f'<td style="font-weight:600;color:#475569;font-size:0.85rem;">'
                    f'{data_txt}</td>'
                    f'</tr>'
                    f'</table>'
                    f'</div>',
                    unsafe_allow_html=True
                )


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

        st.markdown(
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:4px;">'
            f'<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:12px 14px;">'
            f'<div style="font-size:0.68rem;color:#166534;font-weight:700;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:4px;">Receita (pago)</div>'
            f'<div style="font-size:1.3rem;font-weight:800;color:#15803d;">{brl(faturamento)}</div></div>'
            f'<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:10px;padding:12px 14px;">'
            f'<div style="font-size:0.68rem;color:#92400e;font-weight:700;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:4px;">A Receber</div>'
            f'<div style="font-size:1.3rem;font-weight:800;color:#d97706;">{brl(a_receber_top)}</div></div>'
            f'<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:12px 14px;">'
            f'<div style="font-size:0.68rem;color:#1e40af;font-weight:700;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:4px;">Clientes</div>'
            f'<div style="font-size:1.3rem;font-weight:800;color:#1d4ed8;">{num_clientes}</div></div>'
            f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;">'
            f'<div style="font-size:0.68rem;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:4px;">Pedidos</div>'
            f'<div style="font-size:1.3rem;font-weight:800;color:#0f172a;">{num_pedidos}</div></div>'
            '</div>',
            unsafe_allow_html=True
        )

        st.divider()

        aba_visao, aba_financeiro, aba_cobranca, aba_estoque, aba_precos, aba_lancar, aba_pedidos = st.tabs(
            ["Visao Geral", "Financeiro", "Cobrar Clientes", "Estoque", "Preços", "Lançar Venda", "Todos os Pedidos"]
        )

        if True:

            # ── ABA 1: VISÃO GERAL ──
            with aba_visao:
                if df.empty:
                    st.info("Nenhum pedido registrado ainda.")
                else:
                    MESES_PT = {
                        1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",
                        5:"Maio",6:"Junho",7:"Julho",8:"Agosto",
                        9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro",
                    }

                    # Parseia data_venda (formato "DD/MM/YYYY HH:MM" ou vazio)
                    df_v = df.copy()
                    df_v["_dt"] = pd.to_datetime(
                        df_v["data_venda"], format="%d/%m/%Y %H:%M", errors="coerce"
                    )
                    df_v["_periodo"] = df_v["_dt"].dt.to_period("M")

                    periodos_validos = (
                        df_v["_periodo"].dropna().unique()
                    )
                    periodos_ord = sorted(periodos_validos, reverse=True)

                    def fmt_mes(p):
                        return f"{MESES_PT[p.month]}/{p.year}"

                    opcoes_str  = [fmt_mes(p) for p in periodos_ord]
                    periodo_hoje = pd.Period(date.today(), freq="M")
                    idx_default  = (
                        periodos_ord.index(periodo_hoje)
                        if periodo_hoje in periodos_ord else 0
                    )

                    col_sel, col_esp = st.columns([2, 3])
                    with col_sel:
                        mes_escolhido = st.selectbox(
                            "Período", opcoes_str,
                            index=idx_default, key="visao_mes_sel"
                        )

                    periodo_sel = periodos_ord[opcoes_str.index(mes_escolhido)]
                    df_mes      = df_v[df_v["_periodo"] == periodo_sel]

                    # ── Métricas do mês ──
                    df_mes_pago = df_mes[df_mes["pago"] == 1]
                    rec_mes  = df_mes_pago["valor_total"].sum()
                    ped_mes  = len(df_mes)
                    cli_mes  = df_mes["cliente_nome"].nunique()
                    a_rec_mes = df_mes[df_mes["pago"] == 0]["valor_total"].sum()

                    cm1, cm2, cm3, cm4 = st.columns(4)
                    cm1.metric("Receita do mês",   brl(rec_mes))
                    cm2.metric("A receber",         brl(a_rec_mes))
                    cm3.metric("Pedidos no mês",    ped_mes)
                    cm4.metric("Clientes no mês",   cli_mes)

                    st.divider()

                    if df_mes.empty:
                        st.info(f"Nenhum pedido registrado em {mes_escolhido}.")
                    else:
                        col_tp, col_tc = st.columns(2)

                        with col_tp:
                            st.subheader(f"Top Produtos — {mes_escolhido}")
                            top_prod = (
                                df_mes.groupby("produto_nome", as_index=False)
                                .agg(Qtd=("quantidade", "sum"), Faturamento=("valor_total", "sum"))
                                .sort_values("Qtd", ascending=False)
                                .head(5)
                            )
                            top_prod["Faturamento"] = top_prod["Faturamento"].apply(brl)
                            top_prod.rename(columns={"produto_nome": "Produto"}, inplace=True)
                            st.dataframe(top_prod, use_container_width=True, hide_index=True)

                        with col_tc:
                            st.subheader(f"Top Clientes — {mes_escolhido}")
                            top_cli = (
                                df_mes.groupby("cliente_nome", as_index=False)
                                .agg(Total=("valor_total", "sum"), Pedidos=("id", "count"))
                                .sort_values("Total", ascending=False)
                                .head(5)
                            )
                            top_cli["Total"] = top_cli["Total"].apply(brl)
                            top_cli.rename(columns={"cliente_nome": "Cliente"}, inplace=True)
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
                    cor_lucro_bg  = "#f0fdf4" if lucro >= 0 else "#fef2f2"
                    cor_lucro_brd = "#86efac" if lucro >= 0 else "#fca5a5"
                    cor_lucro_txt = "#15803d" if lucro >= 0 else "#dc2626"
                    cor_lucro_lbl = "#166534" if lucro >= 0 else "#991b1b"
                    st.markdown(
                        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:4px;">'
                        f'<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:12px 14px;">'
                        f'<div style="font-size:0.68rem;color:#166534;font-weight:700;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:4px;">Receita (pago)</div>'
                        f'<div style="font-size:1.3rem;font-weight:800;color:#15803d;">{brl(receita)}</div></div>'
                        f'<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:10px;padding:12px 14px;">'
                        f'<div style="font-size:0.68rem;color:#92400e;font-weight:700;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:4px;">Gastos</div>'
                        f'<div style="font-size:1.3rem;font-weight:800;color:#d97706;">{brl(custo_total)}</div></div>'
                        f'<div style="background:{cor_lucro_bg};border:1px solid {cor_lucro_brd};border-radius:10px;padding:12px 14px;">'
                        f'<div style="font-size:0.68rem;color:{cor_lucro_lbl};font-weight:700;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:4px;">{lucro_label} · {margem:.1f}%</div>'
                        f'<div style="font-size:1.3rem;font-weight:800;color:{cor_lucro_txt};">{brl(abs(lucro))}</div></div>'
                        f'<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:12px 14px;">'
                        f'<div style="font-size:0.68rem;color:#1e40af;font-weight:700;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:4px;">A Receber</div>'
                        f'<div style="font-size:1.3rem;font-weight:800;color:#1d4ed8;">{brl(a_receber)}</div></div>'
                        '</div>',
                        unsafe_allow_html=True
                    )

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
                df_pagar = df[df["pago"] == 0].copy() if "pago" in df.columns else pd.DataFrame()

                if df_pagar.empty:
                    st.success("Nenhum valor pendente. Todos os clientes estao em dia!")
                else:
                    total_pendente = df_pagar["valor_total"].sum()
                    num_pendente   = df_pagar["cliente_nome"].nunique()
                    cp1, cp2 = st.columns(2)
                    cp1.metric("Total a receber", brl(total_pendente))
                    cp2.metric("Clientes devedores", num_pendente)
                    st.divider()

                    clientes_pendentes = sorted(df_pagar["cliente_nome"].unique().tolist())

                    for cliente in clientes_pendentes:
                        pedidos_cli = df_pagar[df_pagar["cliente_nome"] == cliente]
                        total_cli   = pedidos_cli["valor_total"].sum()

                        # Lista de itens com data
                        itens_html = ""
                        for _, row in pedidos_cli.iterrows():
                            data_p = str(row["data_venda"])[:16] if "data_venda" in row and row["data_venda"] else "—"
                            itens_html += f"""
                            <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #f1f5f9;">
                                <span style="color:#374151;">{row['produto_nome']} <b>x{int(row['quantidade'])}</b></span>
                                <span style="color:#6b7280;font-size:0.82rem;">{data_p}</span>
                                <span style="font-weight:700;color:#0f172a;">{brl(row['valor_total'])}</span>
                            </div>"""

                        col_cli, col_btn_pago = st.columns([4, 1])
                        with col_cli:
                            st.markdown(f"""
                            <div style="background:white;border:1px solid #e2e8f0;border-left:5px solid #f59e0b;
                            border-radius:12px;padding:16px 18px;margin-bottom:8px;">
                                <div style="font-weight:800;font-size:1rem;color:#0f172a;margin-bottom:8px;">
                                    {cliente}
                                </div>
                                {itens_html}
                                <div style="font-weight:800;font-size:1.1rem;color:#d97706;margin-top:10px;">
                                    Total a receber: {brl(total_cli)}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_btn_pago:
                            st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                            if st.button("Marcar pago", key=f"pago_{cliente}", use_container_width=True, type="primary"):
                                marcar_pago_cliente(cliente)
                                st.success(f"{cliente} marcado como pago!")
                                st.rerun()

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

            # ── ABA 5: PREÇOS ──
            with aba_precos:
                st.subheader("Editar Preços de Venda")
                st.caption("Altere o preço de cada produto. O novo valor é refletido imediatamente nos cards.")
                precos_atuais = carregar_precos()

                col_ph1, col_ph2, col_ph3 = st.columns([2.5, 1.5, 1.5])
                col_ph1.markdown("**Produto**")
                col_ph2.markdown("**Preço atual (R$)**")

                for p in _PRODUTOS_BASE:
                    preco_atual = precos_atuais.get(p["id"], p["preco"])
                    col_pn, col_pv, col_pb = st.columns([2.5, 1.5, 1.5])
                    with col_pn:
                        st.markdown(
                            f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;'
                            f'padding:10px 14px;margin-bottom:4px;">'
                            f'<div style="font-weight:700;color:#0f172a;">{p["nome"]}</div>'
                            f'<div style="font-size:0.8rem;color:#64748b;">Preço base: R$ {p["preco"]:.2f}</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    with col_pv:
                        novo_preco = st.number_input(
                            "Preço", min_value=0.01, step=0.50,
                            value=float(preco_atual),
                            key=f"preco_{p['id']}",
                            label_visibility="collapsed",
                            format="%.2f"
                        )
                    with col_pb:
                        st.markdown("<div style='margin-top:4px;'></div>", unsafe_allow_html=True)
                        if st.button("Salvar", key=f"upd_preco_{p['id']}", use_container_width=True, type="primary"):
                            definir_preco(p["id"], novo_preco)
                            st.success(f"{p['nome']}: preço atualizado para R$ {novo_preco:.2f}")
                            st.rerun()

            # ── ABA: LANÇAR VENDA ──
            with aba_lancar:
                st.subheader("Lançar Venda Manual")
                st.caption("Registre uma venda feita fora do site. Ela afeta estoque, financeiro, cobrança e histórico.")

                precos_lancar = carregar_precos()
                custos_lancar = carregar_custos()

                opcoes_produto = [p["nome"] for p in PRODUTOS] + ["Produto personalizado"]

                col_cli_nome, col_cli_tel = st.columns([3, 2])
                with col_cli_nome:
                    cliente_manual = st.text_input("Nome do cliente *", key="manual_cliente",
                                                   placeholder="Ex: João Silva")
                with col_cli_tel:
                    telefone_manual = st.text_input("Telefone do cliente", key="manual_telefone",
                                                    placeholder="Ex: 65999990000",
                                                    help="Opcional. Permite o cliente ver os pedidos em 'Meus Pedidos' pelo telefone.")
                produto_sel = st.selectbox("Produto *", opcoes_produto, key="manual_produto")

                if produto_sel == "Produto personalizado":
                    produto_nome_manual = st.text_input("Nome do produto *", key="manual_produto_nome",
                                                         placeholder="Ex: Água mineral")
                    produto_id_manual   = None
                    preco_sug           = 1.0
                    custo_sug           = 0.0
                else:
                    produto_obj         = next((p for p in PRODUTOS if p["nome"] == produto_sel), None)
                    produto_nome_manual = produto_sel
                    produto_id_manual   = produto_obj["id"] if produto_obj else None
                    preco_sug           = float(precos_lancar.get(produto_id_manual, produto_obj["preco"] if produto_obj else 1.0))
                    custo_sug           = float(custos_lancar.get(produto_id_manual, 0.0))

                col_qtd, col_preco, col_custo = st.columns(3)
                with col_qtd:
                    qtd_manual = st.number_input("Quantidade *", min_value=1, step=1, value=1, key="manual_qtd")
                with col_preco:
                    _k = produto_sel.replace(" ", "_")
                    preco_manual = st.number_input("Preço (R$) *", min_value=0.01, step=0.50,
                                                    value=preco_sug, key=f"manual_preco_{_k}", format="%.2f")
                with col_custo:
                    custo_manual = st.number_input("Custo (R$)", min_value=0.0, step=0.50,
                                                    value=custo_sug, key=f"manual_custo_{_k}", format="%.2f")

                col_status, col_data = st.columns(2)
                with col_status:
                    status_manual = st.radio("Pagamento *", ["Pago", "Pendente"],
                                             horizontal=True, key="manual_status")
                with col_data:
                    data_manual = st.date_input("Data da venda *", value=date.today(),
                                                 format="DD/MM/YYYY", key="manual_data")

                obs_manual = st.text_area("Observação (opcional)",
                                          placeholder="Ex: Venda feita pessoalmente no trabalho",
                                          key="manual_obs", height=70)

                # Preview
                total_prev  = int(qtd_manual) * float(preco_manual)
                custo_prev  = int(qtd_manual) * float(custo_manual)
                lucro_prev  = total_prev - custo_prev
                cor_lucro_p = "#22c55e" if lucro_prev >= 0 else "#ef4444"
                cor_status  = "#22c55e" if status_manual == "Pago" else "#f59e0b"
                st.markdown(
                    '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px;margin:10px 0;">'
                    '<div style="font-weight:700;color:#0f172a;margin-bottom:10px;">Resumo da venda</div>'
                    '<div style="display:flex;gap:24px;flex-wrap:wrap;">'
                    f'<div><div style="color:#64748b;font-size:0.78rem;">Total</div><b style="color:#0f172a;">{brl(total_prev)}</b></div>'
                    f'<div><div style="color:#64748b;font-size:0.78rem;">Custo total</div><b style="color:#f59e0b;">{brl(custo_prev)}</b></div>'
                    f'<div><div style="color:#64748b;font-size:0.78rem;">Lucro estimado</div><b style="color:{cor_lucro_p};">{brl(lucro_prev)}</b></div>'
                    f'<div><div style="color:#64748b;font-size:0.78rem;">Status</div><b style="color:{cor_status};">{status_manual}</b></div>'
                    '</div></div>',
                    unsafe_allow_html=True
                )

                if st.button("Registrar venda", type="primary", use_container_width=True, key="btn_lancar_venda"):
                    erros_lancar = []
                    nome_cli = cliente_manual.strip()
                    if len(nome_cli) < 2:
                        erros_lancar.append("Nome do cliente deve ter pelo menos 2 caracteres.")
                    if produto_sel == "Produto personalizado" and not produto_nome_manual.strip():
                        erros_lancar.append("Informe o nome do produto personalizado.")
                    if erros_lancar:
                        for e in erros_lancar:
                            st.error(e)
                    else:
                        data_str  = data_manual.strftime("%d/%m/%Y %H:%M")
                        pago_int  = 1 if status_manual == "Pago" else 0
                        salvar_venda_manual(
                            cliente_nome    = nome_cli,
                            produto_nome    = produto_nome_manual.strip(),
                            produto_id      = produto_id_manual,
                            quantidade      = int(qtd_manual),
                            valor_unitario  = float(preco_manual),
                            custo_unitario  = float(custo_manual),
                            pago            = pago_int,
                            data_venda      = data_str,
                            observacao      = obs_manual.strip(),
                            telefone        = telefone_manual.strip(),
                        )
                        st.success(
                            f"Venda registrada: {produto_nome_manual} x{qtd_manual} "
                            f"para {nome_cli} — {brl(total_prev)} ({status_manual})"
                        )
                        st.rerun()

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
                    origem_val = str(row.get("origem", "site") or "site")
                    origem_badge = (
                        '<span style="background:#fef3c7;color:#92400e;font-size:0.68rem;'
                        'font-weight:700;padding:2px 7px;border-radius:20px;margin-left:4px;">manual</span>'
                        if origem_val == "manual" else ""
                    )
                    col_info, col_acoes = st.columns([3, 1])
                    with col_info:
                        st.markdown(
                            f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;'
                            f'padding:10px 14px;margin-bottom:2px;">'
                            f'<div style="font-weight:700;color:#0f172a;font-size:0.88rem;">'
                            f'{row["cliente_nome"]}{origem_badge}</div>'
                            f'<div style="color:#475569;font-size:0.8rem;margin:2px 0;">'
                            f'{row["produto_nome"]} · {int(row["quantidade"])}x · {brl(row["valor_unitario"])}</div>'
                            f'<div style="display:flex;gap:10px;align-items:center;margin-top:4px;flex-wrap:wrap;">'
                            f'<span style="font-size:0.75rem;color:#64748b;">{data_txt}</span>'
                            f'<span style="font-size:0.75rem;font-weight:700;color:{status_cor};">{status_txt}</span>'
                            f'<span style="font-size:0.95rem;font-weight:800;color:#0f172a;">{brl(float(row["valor_total"]))}</span>'
                            f'</div></div>',
                            unsafe_allow_html=True
                        )
                    with col_acoes:
                        novo_total = st.number_input(
                            "Valor", min_value=0.0, step=0.01,
                            value=float(row["valor_total"]),
                            key=f"edit_val_{row['id']}",
                            label_visibility="collapsed", format="%.2f"
                        )
                        if novo_total != float(row["valor_total"]):
                            if st.button("Salvar", key=f"save_{row['id']}", type="primary", use_container_width=True):
                                editar_venda(int(row["id"]), novo_total)
                                st.rerun()
                        else:
                            st.markdown(f'<div style="color:{status_cor};font-weight:700;font-size:0.78rem;text-align:center;padding:4px 0;">{status_txt}</div>', unsafe_allow_html=True)
                        if st.button("Excluir", key=f"del_{row['id']}", use_container_width=True):
                            deletar_pedido(int(row["id"]))
                            st.rerun()
