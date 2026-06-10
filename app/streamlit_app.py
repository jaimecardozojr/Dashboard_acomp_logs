"""Dashboard de acompanhamento de logs de automações.

Rodar local:   streamlit run app/streamlit_app.py
Online:         deploy no Streamlit Community Cloud (main file = app/streamlit_app.py)
"""
from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import ui  # noqa: E402
from app.data import add_task_links, filter_runs, filter_tasks, gestta_url, load_runs, load_tasks  # noqa: E402
from log_dashboard.config import load_settings  # noqa: E402

st.set_page_config(
    page_title="Acompanhamento de Automações",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

SETTINGS = load_settings()
LABELS = {a.key: f"{a.emoji} {a.label}" for a in SETTINGS.automations}


def fmt_duration(seconds: float) -> str:
    seconds = int(seconds or 0)
    m, s = divmod(seconds, 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def fmt_minutes(total_min: float) -> str:
    """Formata minutos como '3h 24min' ou, se grande, inclui os dias."""
    total = int(round(total_min or 0))
    h, m = divmod(total, 60)
    d, h = divmod(h, 24)
    if d:
        return f"{d}d {h}h {m:02d}min"
    if h:
        return f"{h}h {m:02d}min"
    return f"{m} min"


def main() -> None:
    ui.inject_css()
    ui.header(
        "Acompanhamento de Automações",
        "Monitoramento diário das automações DP - (admissão, férias e rescisão).",
    )

    df = load_runs()
    if df.empty:
        st.warning(
            "Nenhuma execução encontrada ainda. Rode o robô "
            "(`python scripts/run_collector.py`) para popular os dados."
        )
        st.stop()

    # ------------------------------------------------------------- Sidebar
    with st.sidebar:
        st.markdown("### 🔎 Filtros")
        autos = sorted(df["automation"].unique())
        sel_autos = st.multiselect(
            "Automação", autos, default=autos,
            format_func=lambda k: LABELS.get(k, k),
        )
        statuses = sorted(df["status"].unique())
        sel_status = st.multiselect("Status", statuses, default=statuses)

        min_d, max_d = df["date"].min(), df["date"].max()
        date_range = st.date_input(
            "Período", value=(min_d, max_d), min_value=min_d, max_value=max_d,
        )
        if isinstance(date_range, (list, tuple)) and len(date_range) == 1:
            date_range = (date_range[0], date_range[0])

        st.divider()
        if st.button("🔄 Atualizar dados", width="stretch"):
            st.cache_data.clear()
            st.rerun()
        if st.session_state.get("data_source") == "fallback-local":
            st.warning("Sem credenciais do Google — lendo do CSV local (`data/execucoes.csv`).", icon="💾")
        st.caption("Cache de 5 min. Dados gerados pelo robô a partir dos logs.")

    fdf = filter_runs(df, sel_autos, sel_status, date_range)
    ftasks = filter_tasks(load_tasks(), sel_autos, date_range)

    tab_exec, tab_tarefas = st.tabs(["📈 Execuções", "✅ Tarefas criadas"])
    with tab_exec:
        render_runs(fdf)
    with tab_tarefas:
        render_tasks(ftasks)

    st.caption("Feito com Streamlit · dados gerados pelo robô a partir dos logs · cache de 5 min")


def render_runs(fdf) -> None:
    if fdf.empty:
        st.info("Nenhuma execução para os filtros selecionados.")
        return

    # ---------------------------------------------------------------- KPIs
    total = len(fdf)
    sucesso = int((fdf["status"] == "sucesso").sum())
    falhas = int((fdf["status"] == "falha").sum())
    taxa = (sucesso / total * 100) if total else 0
    tarefas = int(fdf["tasks_generated"].sum())
    # Tempo economizado = tarefas geradas pelo robô × minutos que um assistente
    # gastaria criando cada tarefa manualmente. getattr() protege contra estado
    # antigo do módulo de config em cache (rerun parcial no Streamlit Cloud).
    min_por_tarefa = getattr(SETTINGS, "minutes_saved_per_task", 2)
    economia_min = tarefas * min_por_tarefa
    last_run = fdf["start_dt"].max()

    ui.kpi_cards([
        {"label": "Execuções", "value": f"{total:,}".replace(",", "."),
         "foot": f"última: {last_run:%d/%m %H:%M}"},
        {"label": "Taxa de sucesso", "value": f"{taxa:.1f}%",
         "foot": f"{sucesso} ok · {falhas} falhas",
         "tone": "ok" if taxa >= 95 else ("warn" if taxa >= 80 else "err")},
        {"label": "Falhas", "value": falhas,
         "foot": "tentativas esgotadas", "tone": "err" if falhas else "ok"},
        {"label": "Tarefas geradas", "value": tarefas, "foot": "no período"},
        {"label": "Tempo economizado", "value": fmt_minutes(economia_min),
         "foot": f"{tarefas} tarefas × {min_por_tarefa:g} min", "tone": "ok"},
    ])

    # ------------------------------------------------------------ Gráficos
    ui.section("Execuções por dia")
    by_day = (
        fdf.groupby(["date", "status"]).size().reset_index(name="qtd")
    )
    fig = px.bar(
        by_day, x="date", y="qtd", color="status",
        color_discrete_map=ui.STATUS_COLORS, barmode="stack",
    )
    fig.update_layout(xaxis_title=None, yaxis_title="execuções")
    fig.update_xaxes(hoverformat="%d/%m/%Y")
    for tr in fig.data:
        tr.hovertemplate = f"{tr.name}: <b>%{{y}}</b> execuções<extra></extra>"
    st.plotly_chart(ui.style_fig(fig, 330, hovermode="x unified"), width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        ui.section("Taxa de sucesso por automação")
        agg = fdf.groupby("automation").agg(
            total=("run_id", "count"),
            ok=("status", lambda s: (s == "sucesso").sum()),
        ).reset_index()
        agg["taxa"] = (agg["ok"] / agg["total"] * 100).round(1)
        agg["label"] = agg["automation"].map(lambda k: LABELS.get(k, k))
        figb = px.bar(
            agg.sort_values("taxa"), x="taxa", y="label", orientation="h",
            text="taxa", color="automation", color_discrete_map=ui.AUTOMATION_COLORS,
        )
        figb.update_traces(
            texttemplate="%{text}%", textposition="outside",
            hovertemplate="<b>%{y}</b><br>%{x:.1f}% de sucesso<extra></extra>",
        )
        figb.update_layout(showlegend=False, xaxis_title="% sucesso", yaxis_title=None,
                           xaxis_range=[0, 105])
        st.plotly_chart(ui.style_fig(figb, 280), width="stretch")

    with c2:
        ui.section("Distribuição por horário")
        by_hour = fdf.groupby("hour").size().reset_index(name="qtd")
        figh = px.area(by_hour, x="hour", y="qtd")
        figh.update_traces(
            line_color=ui.COLORS["accent"], fillcolor="rgba(108,92,231,.25)",
            hovertemplate="<b>%{x}h</b><br>%{y} execuções<extra></extra>",
        )
        figh.update_layout(xaxis_title="hora do dia", yaxis_title="execuções",
                           xaxis=dict(dtick=2))
        st.plotly_chart(ui.style_fig(figh, 280, hovermode="x unified"), width="stretch")

    # ----------------------------------------------------- Tabela + erros
    ui.section("Execuções recentes")
    recent = fdf.sort_values("start_dt", ascending=False).head(200).copy()
    recent["Automação"] = recent["automation"].map(lambda k: LABELS.get(k, k))
    recent["Início"] = recent["start_dt"].dt.strftime("%d/%m/%Y %H:%M")
    recent["Duração"] = recent["duration_seconds"].map(fmt_duration)
    view = recent[[
        "Automação", "Início", "status", "Duração", "attempts",
        "tasks_generated", "errors", "warnings",
    ]].rename(columns={
        "status": "Status", "attempts": "Tentativas",
        "tasks_generated": "Tarefas", "errors": "Erros", "warnings": "Avisos",
    })
    st.dataframe(
        view, width="stretch", hide_index=True, height=380,
        column_config={
            "Status": st.column_config.TextColumn(width="small"),
            "Tarefas": st.column_config.NumberColumn(format="%d"),
        },
    )

    fails = fdf[fdf["status"] == "falha"].sort_values("start_dt", ascending=False)
    if not fails.empty:
        ui.section("⚠️ Últimas falhas")
        for _, row in fails.head(10).iterrows():
            label = LABELS.get(row["automation"], row["automation"])
            causa = (row["last_error"] or "causa não identificada").strip()
            resumo = causa if len(causa) <= 70 else causa[:70] + "…"
            with st.expander(
                f"{label} · {row['start_dt']:%d/%m %H:%M} — {resumo}"
            ):
                st.markdown(f"**Causa:** {causa}")
                st.caption(
                    f"{int(row['attempts'])} tentativas · {int(row['errors'])} erros · "
                    f"{int(row['warnings'])} avisos · arquivo: {row['log_file']}"
                )


def render_tasks(ft) -> None:
    """Aba das tarefas efetivamente criadas: nome, dia e número da tarefa."""
    if ft.empty:
        st.info("Nenhuma tarefa criada para os filtros selecionados.")
        return

    total = len(ft)
    dias = ft["date"].nunique()
    ult = ft["created_dt"].max()
    top_auto = ft["automation"].map(lambda k: LABELS.get(k, k)).value_counts().idxmax()
    ui.kpi_cards([
        {"label": "Tarefas criadas", "value": f"{total:,}".replace(",", "."),
         "foot": f"última: {ult:%d/%m %H:%M}"},
        {"label": "Dias com criação", "value": dias, "foot": "no período"},
        {"label": "Média por dia", "value": f"{total / dias:.1f}" if dias else "0",
         "foot": "tarefas/dia"},
        {"label": "Mais frequente", "value": top_auto.split(" ", 1)[-1], "foot": "automação"},
    ])

    ui.section("Tarefas criadas por dia")
    by_day = ft.groupby(["date", "automation"]).size().reset_index(name="qtd")
    by_day["label"] = by_day["automation"].map(lambda k: LABELS.get(k, k))
    fig = px.bar(by_day, x="date", y="qtd", color="automation",
                 color_discrete_map=ui.AUTOMATION_COLORS, barmode="stack")
    fig.update_layout(xaxis_title=None, yaxis_title="tarefas")
    fig.update_xaxes(hoverformat="%d/%m/%Y")
    for tr in fig.data:
        nome = LABELS.get(tr.name, tr.name)
        tr.hovertemplate = f"{nome}: <b>%{{y}}</b> tarefas<extra></extra>"
    st.plotly_chart(ui.style_fig(fig, 300, hovermode="x unified"), width="stretch")

    ui.section("Detalhe das tarefas")
    view = add_task_links(ft, gestta_url())
    view["Automação"] = view["automation"].map(lambda k: LABELS.get(k, k))
    view["Dia"] = view["created_dt"].dt.strftime("%d/%m/%Y")
    view["Hora"] = view["created_dt"].dt.strftime("%H:%M")
    table = view[[
        "Dia", "Hora", "Automação", "person", "task_number", "title", "task_link",
    ]].rename(columns={
        "person": "Pessoa", "task_number": "Nº da tarefa", "title": "Título",
        "task_link": "Tarefa",
    })
    st.dataframe(
        table, width="stretch", hide_index=True, height=460,
        column_config={
            "Nº da tarefa": st.column_config.TextColumn(width="small"),
            "Pessoa": st.column_config.TextColumn(width="medium"),
            "Tarefa": st.column_config.LinkColumn(
                "Tarefa", display_text="Abrir 🔗", width="small"
            ),
        },
    )

    # Export limpo: cabeçalhos claros, link completo e formato amigável ao
    # Excel em português (separador ';' + BOM utf-8-sig para acentos corretos).
    export = view[[
        "Dia", "Hora", "Automação", "person", "task_number", "title", "task_link",
    ]].rename(columns={
        "person": "Pessoa", "task_number": "Número da tarefa",
        "title": "Título", "task_link": "Link da tarefa",
    })
    csv = export.to_csv(index=False, sep=";").encode("utf-8-sig")
    st.download_button(
        "⬇️ Baixar tarefas (CSV)", data=csv,
        file_name="tarefas_criadas.csv", mime="text/csv",
    )


if __name__ == "__main__":
    main()
