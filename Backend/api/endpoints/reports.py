from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import os
from datetime import datetime

router = APIRouter()


class ReportRequest(BaseModel):
    page: str
    context: Optional[Dict[str, Any]] = None
    simulation_type: Optional[str] = None


class ReportResponse(BaseModel):
    page: str
    model: str
    used_ai: bool
    report_markdown: str


def _build_prompt(req: ReportRequest) -> str:
    page = req.page
    sim = req.simulation_type or ""
    ctx = req.context or {}
    return (
        f"Gere um relatório executivo, em português (pt-BR), claro e direto, "
        f"sobre a página '{page}'{f' (simulação: {sim})' if sim else ''}.\n"
        f"Use os dados a seguir como contexto JSON, se fornecido.\n\n"
        f"Contexto:\n{ctx}\n\n"
        "Estrutura do relatório (markdown):\n"
        "# Resumo\n"
        "- Principais destaques\n"
        "# Indicadores\n"
        "- KPIs relevantes com valores\n"
        "# Insights\n"
        "- 3 a 6 observações acionáveis\n"
        "# Riscos e Oportunidades\n"
        "- Lista objetiva\n"
        "# Próximos Passos\n"
        "- Itens práticos (bullet points)\n"
    )


def _fmt_brl(value: Any) -> str:
    try:
        num = float(value or 0)
    except (TypeError, ValueError):
        return "R$ 0,00"
    formatted = f"{abs(num):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    sign = "-" if num < 0 else ""
    return f"{sign}R$ {formatted}"


def _month_label(mes_ano: str) -> str:
    if not mes_ano:
        return "—"
    return mes_ano.replace("-", "/")


def _report_visao_geral(ctx: Dict[str, Any]) -> str:
    global_stats = ctx.get("globalStats") or ctx.get("global_stats") or {}
    period_stats = ctx.get("periodStats") or ctx.get("period_stats") or {}
    months: List[Dict[str, Any]] = ctx.get("firstMonths") or ctx.get("first_months") or []

    saldo = global_stats.get("saldoAtual", global_stats.get("saldo_atual", 0))
    entradas = global_stats.get("totalEntradas", global_stats.get("total_entradas", 0))
    saidas = global_stats.get("totalSaidas", global_stats.get("total_saidas", 0))
    fluxo = period_stats.get("fluxoLiquido", period_stats.get("fluxo_liquido", entradas - saidas))
    updated = global_stats.get("dataAtualizacao") or global_stats.get("data_atualizacao") or ""

    saldo_status = "positivo" if float(saldo or 0) >= 0 else "negativo"
    months_with_data = [m for m in months if (m.get("total_entradas") or m.get("totalEntradas") or 0) > 0
                        or (m.get("total_saidas") or m.get("totalSaidas") or 0) > 0]

    lines = [
        "# Resumo",
        f"- Saldo atual **{saldo_status}**: {_fmt_brl(saldo)}.",
        f"- Entradas acumuladas: {_fmt_brl(entradas)} | Saídas acumuladas: {_fmt_brl(saidas)}.",
        f"- Fluxo de caixa líquido do período: {_fmt_brl(fluxo)}.",
    ]
    if updated:
        lines.append(f"- Dados atualizados em: {str(updated)[:19].replace('T', ' ')} UTC.")

    lines.extend(["", "# Indicadores", "", "| Indicador | Valor |", "| --- | --- |"])
    lines.append(f"| Saldo atual | {_fmt_brl(saldo)} |")
    lines.append(f"| Total de entradas | {_fmt_brl(entradas)} |")
    lines.append(f"| Total de saídas | {_fmt_brl(saidas)} |")
    lines.append(f"| Fluxo líquido | {_fmt_brl(fluxo)} |")
    lines.append(f"| Meses com movimentação | {len(months_with_data)} |")

    if months_with_data:
        lines.extend(["", "### Detalhamento mensal (amostra)", "", "| Mês | Entradas | Saídas | Fluxo | Saldo final |", "| --- | --- | --- | --- | --- |"])
        for m in months_with_data[:12]:
            mes = _month_label(str(m.get("mes_ano", "")))
            te = m.get("total_entradas", m.get("totalEntradas", 0))
            ts = m.get("total_saidas", m.get("totalSaidas", 0))
            fl = m.get("fluxo_liquido", m.get("fluxoLiquido", te - ts))
            sf = m.get("saldo_final_mes", m.get("saldoFinalMes", 0))
            lines.append(f"| {mes} | {_fmt_brl(te)} | {_fmt_brl(ts)} | {_fmt_brl(fl)} | {_fmt_brl(sf)} |")

    insights: List[str] = []
    if float(fluxo or 0) < 0:
        insights.append(f"Despesas superam receitas em {_fmt_brl(abs(float(fluxo)))} — revise custos fixos e despesas recorrentes.")
    else:
        insights.append(f"Fluxo positivo de {_fmt_brl(fluxo)} — há margem para reserva ou investimento.")

    if months_with_data:
        best = max(months_with_data, key=lambda m: float(m.get("fluxo_liquido", m.get("fluxoLiquido", 0)) or 0))
        worst = min(months_with_data, key=lambda m: float(m.get("fluxo_liquido", m.get("fluxoLiquido", 0)) or 0))
        insights.append(
            f"Melhor mês: {_month_label(str(best.get('mes_ano', '')))} "
            f"(fluxo {_fmt_brl(best.get('fluxo_liquido', best.get('fluxoLiquido', 0)))})."
        )
        insights.append(
            f"Mês mais apertado: {_month_label(str(worst.get('mes_ano', '')))} "
            f"(fluxo {_fmt_brl(worst.get('fluxo_liquido', worst.get('fluxoLiquido', 0)))})."
        )

    if float(entradas or 0) > 0:
        margem = (float(fluxo or 0) / float(entradas)) * 100
        insights.append(f"Margem líquida sobre entradas: {margem:.1f}%.")

    lines.extend(["", "# Insights"])
    for item in insights[:6]:
        lines.append(f"- {item}")

    lines.extend(["", "# Riscos e Oportunidades"])
    if float(saldo or 0) < 0:
        lines.append("- **Risco:** saldo negativo pode limitar capacidade de pagamento.")
    if float(fluxo or 0) < 0:
        lines.append("- **Risco:** fluxo líquido negativo indica queimada de caixa.")
    lines.append("- **Oportunidade:** identificar meses sazonais fortes para antecipar recebíveis.")
    lines.append("- **Oportunidade:** renegociar despesas fixas nos meses de fluxo negativo.")

    lines.extend(["", "# Próximos Passos"])
    lines.append("- Revisar transações dos meses com saldo final mais baixo.")
    lines.append("- Simular cenários otimista/pessimista na aba **Simulação de Cenários**.")
    lines.append("- Gerar previsão de fluxo para os próximos 30–90 dias.")
    lines.append("- (Opcional) Configure `GEMINI_API_KEY` no Render para relatórios com IA.")

    return "\n".join(lines)


def _report_previsao(ctx: Dict[str, Any]) -> str:
    days = ctx.get("days", 30)
    sample = ctx.get("sample") or []
    lines = [
        "# Resumo",
        f"- Previsão solicitada para **{days} dias**.",
        f"- Amostra com {len(sample)} registros recebidos do modelo.",
        "",
        "# Indicadores",
    ]
    if sample:
        lines.extend(["", "| Data | Fluxo previsto | Saldo previsto |", "| --- | --- | --- |"])
        for row in sample[:10]:
            lines.append(
                f"| {row.get('data', '—')} | {_fmt_brl(row.get('fluxo_previsto', 0))} | "
                f"{_fmt_brl(row.get('saldo_previsto', 0))} |"
            )
    else:
        lines.append("- Execute a previsão antes de gerar o relatório completo.")

    lines.extend([
        "",
        "# Insights",
        "- A previsão usa o histórico carregado no upload.",
        "- Valores negativos de fluxo indicam dias com pressão de caixa.",
        "",
        "# Riscos e Oportunidades",
        "- **Risco:** previsões dependem da qualidade e volume dos dados históricos.",
        "- **Oportunidade:** ajustar despesas antes dos dias com saldo previsto em queda.",
        "",
        "# Próximos Passos",
        "- Comparar previsão com o dashboard geral.",
        "- Rodar simulação de cenários com variações de entrada/saída.",
    ])
    return "\n".join(lines)


def _report_simulacao(ctx: Dict[str, Any], sim_type: str) -> str:
    lines = [
        "# Resumo",
        f"- Relatório da simulação **{sim_type or 'macroeconômica'}**.",
        "",
        "# Indicadores",
    ]
    for key in ("probabilidadeSaldoNegativo", "cenarioMedio", "piorCenario", "melhorCenario"):
        if key in ctx:
            val = ctx[key]
            label = key.replace("probabilidadeSaldoNegativo", "Prob. saldo negativo (%)")
            if key == "probabilidadeSaldoNegativo":
                lines.append(f"- {label}: {float(val):.1f}%")
            else:
                lines.append(f"- {label}: {_fmt_brl(val)}")

    if len(lines) == 4:
        lines.append("- Execute uma simulação para ver resultados detalhados.")

    lines.extend([
        "",
        "# Insights",
        "- Cenários pessimistas ajudam a dimensionar reserva de emergência.",
        "- Use eventos de negócio para testar impacto de receitas/despesas específicas.",
        "",
        "# Próximos Passos",
        "- Documentar premissas usadas na simulação.",
        "- Revisar dashboard após upload de dados reais.",
    ])
    return "\n".join(lines)


def _report_upload(ctx: Dict[str, Any]) -> str:
    files = ctx.get("files") or ctx.get("fileCount") or ctx.get("file_count")
    lines = [
        "# Resumo",
        "- Relatório pós-upload de dados financeiros.",
        "",
        "# Indicadores",
    ]
    if files is not None:
        lines.append(f"- Arquivos processados: **{files}**")
    lines.extend([
        "- Verifique o **Dashboard Geral** para confirmar totais e gráficos.",
        "",
        "# Próximos Passos",
        "- Conferir se entradas e saídas batem com a planilha original.",
        "- Gerar previsão e simulações com os dados carregados.",
    ])
    return "\n".join(lines)


def _generate_heuristic_report(req: ReportRequest) -> str:
    page = req.page
    ctx = req.context or {}

    if page == "VisaoGeral":
        return _report_visao_geral(ctx)
    if page == "PrevisaoFluxo":
        return _report_previsao(ctx)
    if page == "SimulacaoCenarios":
        return _report_simulacao(ctx, req.simulation_type or "")
    if page == "UploadDados":
        return _report_upload(ctx)

    lines = [
        f"# Resumo\nRelatório gerado para **{page}** (modo automático, sem IA).",
        "\n# Indicadores",
    ]
    if ctx:
        for k, v in list(ctx.items())[:8]:
            if isinstance(v, (int, float)):
                lines.append(f"- {k}: {_fmt_brl(v)}")
            elif isinstance(v, dict):
                lines.append(f"- {k}: {len(v)} campos")
            elif isinstance(v, list):
                lines.append(f"- {k}: {len(v)} itens")
            else:
                lines.append(f"- {k}: {v}")
    else:
        lines.append("- Sem contexto adicional.")
    lines.append("\n# Próximos Passos\n- Configure `GEMINI_API_KEY` no Render para relatórios enriquecidos com IA.")
    return "\n".join(lines)


@router.post("/reports/generate", response_model=ReportResponse)
async def generate_report(req: ReportRequest) -> ReportResponse:
    """Generate a markdown executive report. Uses Gemini if GEMINI_API_KEY is set; otherwise returns a formatted heuristic summary."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    prompt = _build_prompt(req)

    if not api_key:
        markdown = _generate_heuristic_report(req)
        return ReportResponse(page=req.page, model="heuristic", used_ai=False, report_markdown=markdown)

    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=api_key)
        configured = os.getenv("GEMINI_MODEL")
        candidates = [
            configured,
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash-8b",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest",
            "gemini-pro",
        ]
        tried = []
        last_err: Optional[Exception] = None
        for name in [m for m in candidates if m]:
            try:
                model = genai.GenerativeModel(name)
                response = model.generate_content(prompt)
                text = getattr(response, "text", None) or (
                    response.candidates[0].content.parts[0].text
                    if getattr(response, "candidates", None)
                    else ""
                )
                if not text:
                    raise RuntimeError("Resposta vazia do modelo")
                return ReportResponse(page=req.page, model=name, used_ai=True, report_markdown=text)
            except Exception as err:
                tried.append(name)
                last_err = err
                continue
        try:
            available = list(genai.list_models())
            preferred = [
                m for m in available
                if getattr(m, "name", "").find("1.5") != -1 and "generateContent" in getattr(m, "supported_generation_methods", [])
            ] or [
                m for m in available
                if "generateContent" in getattr(m, "supported_generation_methods", [])
            ]
            if not preferred:
                names = [getattr(m, "name", "?") for m in available]
                raise HTTPException(status_code=500, detail=f"Nenhum modelo com generateContent disponível. Modelos: {names}")

            chosen = preferred[0].name.replace("models/", "")
            model = genai.GenerativeModel(chosen)
            response = model.generate_content(prompt)
            text = getattr(response, "text", None) or (
                response.candidates[0].content.parts[0].text if getattr(response, "candidates", None) else ""
            )
            if not text:
                raise RuntimeError("Resposta vazia do modelo (fallback list_models)")
            return ReportResponse(page=req.page, model=chosen, used_ai=True, report_markdown=text)
        except HTTPException:
            raise
        except Exception as err_list:
            raise HTTPException(status_code=500, detail=f"Falha ao gerar relatório. Modelos tentados: {tried}. Erro: {err_list}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao inicializar Gemini: {e}")
