from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
import os

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
    # Keep prompt concise; expect frontend to pass compact context
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


@router.post("/reports/generate", response_model=ReportResponse)
async def generate_report(req: ReportRequest) -> ReportResponse:
    """Generate a markdown executive report. Uses Gemini if GEMINI_API_KEY is set; otherwise returns a heuristic summary."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    prompt = _build_prompt(req)

    if not api_key:
        # Fallback: simple heuristic report without external API
        page = req.page
        ctx = req.context or {}
        lines = [
            f"# Resumo\nRelatório para '{page}'. API de IA não configurada (defina GEMINI_API_KEY).",
            "\n# Indicadores",
        ]
        # Try to surface some numeric keys
        if isinstance(ctx, dict) and ctx:
            for k, v in list(ctx.items())[:10]:
                lines.append(f"- {k}: {v}")
        else:
            lines.append("- Sem contexto fornecido")
        lines.extend([
            "\n# Insights",
            "- Configure a chave GEMINI_API_KEY para relatórios mais ricos.",
            "- Garanta que os dados da página estejam atualizados.",
            "\n# Riscos e Oportunidades",
            "- Risco: baixa cobertura de dados recentes.",
            "- Oportunidade: padronizar categorias e descrições.",
            "\n# Próximos Passos",
            "- Definir variável de ambiente GEMINI_API_KEY.",
            "- Reexecutar a geração do relatório nesta página.",
        ])
        return ReportResponse(page=page, model="heuristic", used_ai=False, report_markdown="\n".join(lines))

    # Try Gemini if available
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
            except Exception as err:  # try next
                tried.append(name)
                last_err = err
                continue
        # Final fallback: listar modelos disponíveis e escolher um compatível
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
                raise HTTPException(status_code=500, detail=f"Nenhum modelo com generateContent disponível para esta chave. Modelos visíveis: {names}")

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
            raise HTTPException(status_code=500, detail=f"Falha ao gerar relatório. Modelos tentados: {tried}. Erro final list_models: {err_list}")
    except HTTPException:
        raise
    except Exception as e:
        # Unexpected failure when initializing SDK
        raise HTTPException(status_code=500, detail=f"Falha ao inicializar Gemini: {e}")


