"""Componentes visuais reutilizáveis do dashboard."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent / "assets"

# Paleta consistente entre CSS e gráficos Plotly
COLORS = {
    "accent": "#5b4cca",
    "accent_2": "#22d3ee",
    "ok": "#22C55E",
    "warn": "#F59E0B",
    "err": "#EF4444",
    "muted": "#8B93A7",
    "grid": "rgba(255,255,255,0.06)",
}
STATUS_COLORS = {"sucesso": COLORS["ok"], "falha": COLORS["err"], "incompleto": COLORS["warn"]}
AUTOMATION_COLORS = {"admissao": "#2EE91D", "ferias": "#0097D2", "rescisao": "#F59E0B"}


def inject_css() -> None:
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="app-header">
            <div class="logo">📊</div>
            <div><h1>{title}</h1></div>
        </div>
        <p class="app-subtitle">{subtitle}</p>
        """,
        unsafe_allow_html=True,
    )


def kpi_cards(cards: list[dict]) -> None:
    """cards: lista de {label, value, foot, tone}. tone: ''|'ok'|'warn'|'err'."""
    html = ['<div class="kpi-grid">']
    for c in cards:
        tone = c.get("tone", "")
        html.append(
            f"""<div class="kpi-card {tone}">
                <div class="kpi-label">{c['label']}</div>
                <div class="kpi-value">{c['value']}</div>
                <div class="kpi-foot">{c.get('foot', '')}</div>
            </div>"""
        )
    html.append("</div>")
    st.markdown("\n".join(html), unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def status_badge(status: str) -> str:
    return f'<span class="badge badge-{status}">{status}</span>'


def style_fig(fig, height: int = 320, hovermode: str | None = None):
    """Aplica o tema escuro padrão aos gráficos Plotly.

    hovermode: ex. 'x unified' para juntar todas as séries do dia num tooltip só.
    """
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E8EAF1", size=12, family="Space Grotesk, Inter, sans-serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode=hovermode or "closest",
        barcornerradius=7,                 # barras com cantos arredondados
        bargap=0.28,
        hoverlabel=dict(
            bgcolor="rgba(13,16,24,0.96)",   # combina com o fundo do tema
            bordercolor=COLORS["accent"],
            font=dict(color="#E8EAF1", size=13, family="Space Grotesk, sans-serif"),
            align="left",
            namelength=-1,
        ),
        transition=dict(duration=450, easing="cubic-in-out"),
    )
    fig.update_xaxes(gridcolor=COLORS["grid"], zeroline=False, showline=False, ticks="")
    fig.update_yaxes(gridcolor=COLORS["grid"], zeroline=False, showline=False, ticks="")
    return fig
