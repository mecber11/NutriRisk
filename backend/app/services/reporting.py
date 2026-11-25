"""Operational report generation in PDF, DOCX and XLSX."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.features import FEATURE_LABELS
from app.models.audit import AuditLog
from app.models.data import AnthropometricIndicator, Child, Dataset, Household, Territory
from app.models.ml import MLModel, ModelExperiment, TerritoryRisk
from app.models.system import Report

REPORT_KINDS: dict[str, dict[str, Any]] = {
    "territory_profile": {
        "label": "Ficha de riesgo por territorio",
        "description": "Perfil territorial con prevalencias, riesgo predicho, determinantes y recomendaciones.",
        "params": ["territory_code", "year"],
    },
    "priority_ranking": {
        "label": "Ranking de priorización territorial",
        "description": "Territorios ordenados por riesgo predicho con población en riesgo.",
        "params": ["year", "limit"],
    },
    "model_performance": {
        "label": "Desempeño de modelos",
        "description": "Comparación de algoritmos, métricas por región y diagnósticos espaciales.",
        "params": ["model_id"],
    },
    "fairness": {
        "label": "Informe de equidad",
        "description": "Métricas por sexo, quintil de riqueza, área y región.",
        "params": ["model_id"],
    },
    "audit_log": {
        "label": "Bitácora de auditoría",
        "description": "Registro inmutable de accesos y acciones, filtrable y exportable.",
        "params": ["date_from", "date_to", "module", "action", "search"],
    },
    "prevalence_summary": {
        "label": "Resumen de prevalencias",
        "description": "Prevalencias nacionales y por región, sexo y año.",
        "params": ["year", "region"],
    },
}

FORMAT_LABELS = {"pdf": "PDF", "docx": "Word", "xlsx": "Excel"}


@dataclass
class ReportTable:
    headers: list[str]
    rows: list[list[Any]]
    widths: list[float] | None = None


@dataclass
class ReportSection:
    title: str
    paragraphs: list[str] = field(default_factory=list)
    tables: list[ReportTable] = field(default_factory=list)


@dataclass
class ReportDocument:
    title: str
    subtitle: str
    sections: list[ReportSection]
    kpis: list[dict[str, Any]] = field(default_factory=list)
    footer: str = "NutriRisk AI · datos sintéticos de demostración"
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# --------------------------------------------------------------------------- #
# Report builders
# --------------------------------------------------------------------------- #
def _active_model(db: Session) -> MLModel | None:
    return db.scalar(select(MLModel).where(MLModel.is_active.is_(True)))


def _year(frame_years: list[int], requested: int | None) -> int | None:
    if requested:
        return requested
    return max(frame_years) if frame_years else None


def territory_profile(db: Session, *, territory_code: str | None, year: int | None) -> ReportDocument:
    from app.services.dashboard import apply_filters, comparison, load_frame

    model = _active_model(db)
    frame = load_frame(db, model)
    years = sorted(frame["period_year"].unique().tolist()) if not frame.empty else []
    selected_year = _year(years, year)
    territory = None
    if territory_code:
        territory = db.scalar(select(Territory).where(Territory.code == territory_code))
    elif not frame.empty:
        territory_id = int(frame[frame["period_year"] == selected_year]["territory_id"].iloc[0])
        territory = db.get(Territory, territory_id)
    if territory is None:
        raise ValueError("Territorio no encontrado")

    subset = apply_filters(frame, year=selected_year, territory_id=territory.id)
    risk = db.scalar(
        select(TerritoryRisk).where(
            TerritoryRisk.territory_id == territory.id,
            TerritoryRisk.period_year == selected_year,
            TerritoryRisk.model_id == (model.id if model else -1),
        )
    )
    stunting = float(subset["stunting"].mean()) if not subset.empty else 0.0
    wasting = float(subset["wasting"].mean()) if not subset.empty else 0.0
    underweight = float(subset["underweight"].mean()) if not subset.empty else 0.0
    mean_haz = float(subset["haz"].mean()) if not subset.empty else 0.0
    mean_risk = float(risk.mean_risk) if risk else float(subset["risk"].mean() if not subset.empty else 0.0)

    sections: list[ReportSection] = []
    sections.append(
        ReportSection(
            title="Situación nutricional",
            paragraphs=[
                f"El territorio {territory.name} ({territory.code}) pertenece a la región {territory.region} "
                f"y agrupa {int(territory.population):,} habitantes, de los cuales {int(territory.population_u5):,} "
                f"son menores de cinco años.",
                f"En el periodo {selected_year} se evaluaron {len(subset)} niños y niñas. La prevalencia de retraso "
                f"del crecimiento es {stunting * 100:.1f} %, la emaciación {wasting * 100:.1f} % y el bajo peso "
                f"{underweight * 100:.1f} %. El HAZ medio es {mean_haz:.2f} DE.",
            ],
            tables=[
                ReportTable(
                    headers=["Indicador", "Valor", "Referencia OMS"],
                    rows=[
                        ["Retraso del crecimiento (HAZ < -2)", f"{stunting * 100:.1f} %", "Alerta ≥ 20 %"],
                        ["Emaciación (WHZ < -2)", f"{wasting * 100:.1f} %", "Alerta ≥ 5 %"],
                        ["Bajo peso (WAZ < -2)", f"{underweight * 100:.1f} %", "Alerta ≥ 12 %"],
                        ["HAZ medio", f"{mean_haz:.2f}", "0 DE"],
                        ["Riesgo medio predicho", f"{mean_risk * 100:.1f} %", "Priorización ≥ 30 %"],
                    ],
                )
            ],
        )
    )

    if risk:
        drivers = risk.top_features or []
        sections.append(
            ReportSection(
                title="Priorización y determinantes",
                paragraphs=[
                    f"El territorio ocupa la posición {risk.priority_rank} del ranking nacional de riesgo "
                    f"({risk.risk_band}). La población menor de 5 años en riesgo estimada es "
                    f"{int(risk.population_at_risk):,} niños.",
                    "Los determinantes que más contribuyen al riesgo, según valores SHAP agregados, son: "
                    + ", ".join(item.get("label", item.get("feature", "")) for item in drivers[:5])
                    + ".",
                ],
                tables=[
                    ReportTable(
                        headers=["Determinante", "Contribución media |SHAP|"],
                        rows=[
                            [item.get("label", item.get("feature", "")), f"{item.get('mean_abs_shap', 0):.4f}"]
                            for item in drivers
                        ],
                    )
                ],
            )
        )

    if not subset.empty:
        age_rows = []
        for label, subset_group in subset.groupby("age_group"):
            age_rows.append(
                [
                    label,
                    len(subset_group),
                    f"{subset_group['stunting'].mean() * 100:.1f} %",
                    f"{subset_group['wasting'].mean() * 100:.1f} %",
                ]
            )
        sections.append(
            ReportSection(
                title="Distribución por grupo de edad",
                tables=[ReportTable(headers=["Grupo", "Niños", "Retraso", "Emaciación"], rows=sorted(age_rows))],
            )
        )

    recommendations = _recommendations(risk.top_features if risk else [])
    sections.append(
        ReportSection(
            title="Recomendaciones de intervención",
            paragraphs=recommendations,
        )
    )

    regional = comparison(subset, "region")
    _ = regional
    return ReportDocument(
        title=f"Ficha de riesgo territorial · {territory.name}",
        subtitle=f"Periodo {selected_year} · modelo {(model.name if model else 'sin modelo activo')}",
        sections=sections,
        kpis=[
            {"label": "Retraso del crecimiento", "value": f"{stunting * 100:.1f} %"},
            {"label": "Riesgo medio", "value": f"{mean_risk * 100:.1f} %"},
            {"label": "Ranking nacional", "value": f"#{risk.priority_rank}" if risk else "s/d"},
            {"label": "Población en riesgo", "value": f"{int(risk.population_at_risk):,}" if risk else "s/d"},
        ],
    )


def _recommendations(drivers: list[dict[str, Any]]) -> list[str]:
    mapping = {
        "wealth_quintile": "Ampliar transferencias monetarias y protección social a los hogares de menor quintil.",
        "maternal_education_years": "Vincular madres y cuidadores a programas de educación y estimulación temprana.",
        "water_improved": "Priorizar conexión a agua segura y tratamiento intradomiciliario.",
        "sanitation_improved": "Ampliar saneamiento mejorado y eliminación segura de excretas.",
        "food_insecurity_score": "Activar asistencia alimentaria y consejería nutricional en el hogar.",
        "territory_food_insecurity": "Reforzar la disponibilidad de alimentos y la agricultura familiar.",
        "minimum_diet_diversity": "Promover diversidad dietética y alimentación complementaria oportuna.",
        "vaccination_complete": "Completar esquemas de vacunación y controles de crecimiento.",
        "diarrhea_14d": "Fortalecer el manejo integrado de la diarrea y la suplementación con zinc.",
        "ndvi": "Monitorear la relación entre vegetación, producción local y disponibilidad alimentaria.",
        "altitude_m": "Adaptar la consejería nutricional al contexto altitudinal y de acceso.",
    }
    lines = [
        mapping.get(item.get("feature", ""), "Revisar el determinante principal con el equipo territorial.")
        for item in drivers[:4]
    ]
    if not lines:
        lines = ["Mantener la vigilancia nutricional y repetir la medición en el próximo periodo."]
    lines.append("Las acciones deben coordinarse con el nivel territorial y registrarse en la bitácora de intervenciones.")
    return lines


def priority_ranking(db: Session, *, year: int | None, limit: int = 24) -> ReportDocument:
    model = _active_model(db)
    if model is None:
        raise ValueError("No hay modelo activo para construir el ranking")
    years = [row[0] for row in db.execute(select(TerritoryRisk.period_year).distinct()).all()]
    selected_year = _year(sorted(years), year)
    rows = db.execute(
        select(TerritoryRisk, Territory)
        .join(Territory, TerritoryRisk.territory_id == Territory.id)
        .where(TerritoryRisk.model_id == model.id, TerritoryRisk.period_year == selected_year)
        .order_by(TerritoryRisk.priority_rank)
        .limit(limit)
    ).all()
    table_rows = [
        [
            risk.priority_rank,
            territory.code,
            territory.name,
            territory.region,
            f"{risk.mean_risk * 100:.1f} %",
            f"{risk.stunting_prevalence * 100:.1f} %",
            f"{int(risk.population_at_risk):,}",
            risk.risk_band,
        ]
        for risk, territory in rows
    ]
    total_population = sum(int(risk.population_at_risk) for risk, _ in rows)
    return ReportDocument(
        title="Ranking de priorización territorial",
        subtitle=f"Periodo {selected_year} · modelo {model.name} v{model.version}",
        kpis=[
            {"label": "Territorios priorizados", "value": str(len(rows))},
            {"label": "Población en riesgo", "value": f"{total_population:,}"},
            {"label": "Riesgo medio (top 5)", "value": f"{(sum(r.mean_risk for r, _ in rows[:5]) / max(len(rows[:5]), 1)) * 100:.1f} %"},
        ],
        sections=[
            ReportSection(
                title="Territorios ordenados por riesgo predicho",
                paragraphs=[
                    "El ranking combina el riesgo medio predicho por territorio con la prevalencia observada de "
                    "retraso del crecimiento y la población menor de cinco años expuesta."
                ],
                tables=[
                    ReportTable(
                        headers=[
                            "Prioridad", "Código", "Territorio", "Región", "Riesgo medio",
                            "Retraso observado", "Población en riesgo", "Banda",
                        ],
                        rows=table_rows,
                    )
                ],
            )
        ],
    )


def model_performance(db: Session, *, model_id: int | None) -> ReportDocument:
    models = db.execute(select(MLModel).order_by(MLModel.id)).scalars().all()
    if not models:
        raise ValueError("No hay modelos entrenados")
    selected = db.get(MLModel, model_id) if model_id else (_active_model(db) or models[-1])
    comparison_rows = []
    for model in models:
        metrics = model.metrics or {}
        comparison_rows.append(
            [
                model.name,
                model.version,
                model.algorithm,
                f"{metrics.get('auc'):.4f}" if metrics.get("auc") is not None else "s/d",
                f"{metrics.get('f1_optimal'):.4f}" if metrics.get("f1_optimal") is not None else "s/d",
                f"{metrics.get('rmse'):.4f}" if metrics.get("rmse") is not None else "s/d",
                "Sí" if model.is_active else "No",
            ]
        )
    sections = [
        ReportSection(
            title="Comparación de algoritmos",
            paragraphs=[
                "Métricas calculadas con validación espacial (GroupKFold por región) para los modelos de "
                "clasificación y con partición por territorio para el CNN-LSTM."
            ],
            tables=[
                ReportTable(
                    headers=["Modelo", "Versión", "Algoritmo", "AUC", "F1 óptimo", "RMSE", "Activo"],
                    rows=comparison_rows,
                )
            ],
        )
    ]
    experiment = db.get(ModelExperiment, selected.experiment_id) if selected.experiment_id else None
    if experiment and experiment.per_region_metrics:
        region_rows = [
            [
                region,
                metrics.get("n", ""),
                f"{metrics.get('auc'):.4f}" if metrics.get("auc") is not None else f"{metrics.get('rmse', '')}",
                f"{metrics.get('f1'):.4f}" if metrics.get("f1") is not None else "",
                f"{metrics.get('recall'):.4f}" if metrics.get("recall") is not None else "",
            ]
            for region, metrics in experiment.per_region_metrics.items()
        ]
        sections.append(
            ReportSection(
                title=f"Transferibilidad por región · {selected.name}",
                tables=[
                    ReportTable(
                        headers=["Región", "n", "AUC / RMSE", "F1", "Recall"],
                        rows=region_rows,
                    )
                ],
            )
        )
    diagnostics = (experiment.spatial_diagnostics if experiment else {}) or {}
    moran = diagnostics.get("moran", {})
    if moran.get("available"):
        sections.append(
            ReportSection(
                title="Diagnósticos espaciales",
                paragraphs=[
                    f"Moran's I de residuos = {moran['i']} (p = {moran['p_value']}): {moran['interpretation']}.",
                    *[str(line) for line in diagnostics.get("summary", [])],
                ],
            )
        )
    return ReportDocument(
        title="Desempeño de modelos",
        subtitle=f"Modelo seleccionado: {selected.name} v{selected.version}",
        kpis=[
            {"label": "AUC", "value": f"{(selected.metrics or {}).get('auc', 0):.4f}"},
            {"label": "F1 (óptimo)", "value": f"{(selected.metrics or {}).get('f1_optimal', 0):.4f}"},
            {"label": "Algoritmo", "value": selected.algorithm},
        ],
        sections=sections,
    )


def fairness_report(db: Session, *, model_id: int | None) -> ReportDocument:
    from app.services.fairness import summary as fairness_summary

    model = db.get(MLModel, model_id) if model_id else _active_model(db)
    if model is None:
        raise ValueError("No hay modelo disponible")
    data = fairness_summary(db, model.id)
    sections = []
    for attribute in data["attributes"]:
        rows = [
            [
                group["group"],
                group["n"],
                f"{group['selection_rate'] * 100:.1f} %",
                f"{group['tpr'] * 100:.1f} %" if group.get("tpr") is not None else "s/d",
                f"{group['fpr'] * 100:.1f} %" if group.get("fpr") is not None else "s/d",
                f"{group['auc']:.4f}" if group.get("auc") is not None else "s/d",
            ]
            for group in attribute["groups"]
        ]
        sections.append(
            ReportSection(
                title=f"Atributo: {attribute['sensitive_attribute']}",
                paragraphs=[
                    f"Disparidad máxima de tasa de selección: {attribute['max_disparity']:.4f} "
                    f"({'aceptable' if attribute['is_acceptable'] else 'requiere revisión'}; umbral "
                    f"{attribute['threshold']})."
                ],
                tables=[
                    ReportTable(
                        headers=["Grupo", "n", "Tasa de selección", "TPR", "FPR", "AUC"],
                        rows=rows,
                    )
                ],
            )
        )
    return ReportDocument(
        title="Informe de equidad del modelo",
        subtitle=f"{model.name} v{model.version} · {model.algorithm}",
        kpis=[
            {"label": "Atributos evaluados", "value": str(len(data["attributes"]))},
            {"label": "Resultado global", "value": "Aceptable" if data["overall_acceptable"] else "Revisar"},
        ],
        sections=sections,
    )


def audit_report(db: Session, *, filters: dict[str, Any]) -> ReportDocument:
    from app.services.audit import build_audit_query

    stmt = build_audit_query(
        search=filters.get("search"),
        module=filters.get("module"),
        action=filters.get("action"),
        result=filters.get("result"),
        role_code=filters.get("role_code"),
        user_email=filters.get("user_email"),
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
    ).limit(1000)
    rows = db.execute(stmt).scalars().all()
    table_rows = [
        [
            entry.started_at.strftime("%Y-%m-%d %H:%M:%S") if entry.started_at else "",
            entry.user_email or "anónimo",
            entry.role_code or "",
            entry.module,
            entry.action,
            entry.result,
            entry.path or "",
            entry.ip_address or "",
            entry.duration_ms,
        ]
        for entry in rows
    ]
    total = db.scalar(select(func.count(AuditLog.id))) or 0
    return ReportDocument(
        title="Bitácora de auditoría",
        subtitle=f"{len(rows)} registros exportados de {total} totales",
        kpis=[
            {"label": "Registros exportados", "value": str(len(rows))},
            {"label": "Total histórico", "value": str(total)},
        ],
        sections=[
            ReportSection(
                title="Eventos registrados",
                paragraphs=[
                    "Registro inmutable de accesos: usuario, rol, módulo, acción, fecha/hora, IP, agente de usuario "
                    "y resultado. Los datos sensibles se enmascaran."
                ],
                tables=[
                    ReportTable(
                        headers=["Fecha", "Usuario", "Rol", "Módulo", "Acción", "Resultado", "Ruta", "IP", "ms"],
                        rows=table_rows,
                    )
                ],
            )
        ],
    )


def prevalence_report(db: Session, *, year: int | None, region: str | None) -> ReportDocument:
    from app.services.dashboard import apply_filters, comparison, kpis, load_frame, trend

    frame = load_frame(db, _active_model(db))
    years = sorted(frame["period_year"].unique().tolist()) if not frame.empty else []
    selected_year = _year(years, year)
    subset = apply_filters(frame, year=selected_year, region=region)
    cards = kpis(subset)
    region_rows = [
        [row["label"], row["n"], f"{row['stunting']:.1f} %", f"{row['wasting']:.1f} %", f"{row['underweight']:.1f} %"]
        for row in comparison(subset, "region")
    ]
    sex_rows = [
        [row["label"], row["n"], f"{row['stunting']:.1f} %", f"{row['wasting']:.1f} %"]
        for row in comparison(subset, "sex")
    ]
    trend_rows = [
        [item["period"], f"{item['stunting']:.1f} %", f"{item['wasting']:.1f} %", f"{item['underweight']:.1f} %"]
        for item in trend(apply_filters(frame, region=region))
    ]
    return ReportDocument(
        title="Resumen de prevalencias nutricionales",
        subtitle=f"Periodo {selected_year}" + (f" · región {region}" if region else " · nacional"),
        kpis=[
            {"label": card["label"], "value": f"{card['value']:.1f} {card['unit']}"}
            for card in cards[:4]
        ],
        sections=[
            ReportSection(
                title="Prevalencia por región",
                tables=[ReportTable(headers=["Región", "n", "Retraso", "Emaciación", "Bajo peso"], rows=region_rows)],
            ),
            ReportSection(
                title="Prevalencia por sexo",
                tables=[ReportTable(headers=["Sexo", "n", "Retraso", "Emaciación"], rows=sex_rows)],
            ),
            ReportSection(
                title="Serie temporal",
                tables=[ReportTable(headers=["Año", "Retraso", "Emaciación", "Bajo peso"], rows=trend_rows)],
            ),
        ],
    )


BUILDERS = {
    "territory_profile": lambda db, params: territory_profile(
        db, territory_code=params.get("territory_code"), year=params.get("year")
    ),
    "priority_ranking": lambda db, params: priority_ranking(db, year=params.get("year"), limit=int(params.get("limit", 24))),
    "model_performance": lambda db, params: model_performance(db, model_id=params.get("model_id")),
    "fairness": lambda db, params: fairness_report(db, model_id=params.get("model_id")),
    "audit_log": lambda db, params: audit_report(db, filters=params),
    "prevalence_summary": lambda db, params: prevalence_report(db, year=params.get("year"), region=params.get("region")),
}


# --------------------------------------------------------------------------- #
# Renderers
# --------------------------------------------------------------------------- #
def _safe(value: Any) -> str:
    return "" if value is None else str(value)


def render_pdf(document: ReportDocument, path: Path) -> None:
    from app.services.interpretation import table_note
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="KpiLabel", fontSize=8, textColor=colors.HexColor("#475569")))
    styles.add(ParagraphStyle(name="KpiValue", fontSize=15, fontName="Helvetica-Bold", textColor=colors.HexColor("#0f766e")))
    styles.add(ParagraphStyle(name="Sub", fontSize=9, textColor=colors.HexColor("#64748b")))
    styles.add(ParagraphStyle(name="Cell", fontSize=7.5, leading=9))

    wide = any(len(table.headers) > 6 for section in document.sections for table in section.tables)
    pdf_path = str(path)
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=landscape(A4) if wide else A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=document.title,
        author="NutriRisk AI",
    )
    story: list[Any] = [
        Paragraph(document.title, styles["Title"]),
        Paragraph(document.subtitle, styles["Sub"]),
        Paragraph(
            f"Generado el {document.generated_at.strftime('%Y-%m-%d %H:%M UTC')} · {document.footer}",
            styles["Sub"],
        ),
        Spacer(1, 8),
    ]

    if document.kpis:
        cells = []
        for item in document.kpis:
            cells.append(
                [
                    Paragraph(_safe(item.get("label")), styles["KpiLabel"]),
                    Paragraph(_safe(item.get("value")), styles["KpiValue"]),
                ]
            )
        table = Table([[Table([cell], colWidths=[40 * mm]) for cell in cells]], colWidths=None)
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        story.extend([table, Spacer(1, 10), Paragraph('Interpretación: estos indicadores resumen el periodo y los filtros del reporte. Distinga conteos, prevalencias observadas y métricas del modelo; el resumen sintético no acredita utilidad clínica.', styles['BodyText']), Spacer(1, 6)])

    for section in document.sections:
        story.append(Paragraph(section.title, styles["Heading2"]))
        for paragraph in section.paragraphs:
            story.append(Paragraph(paragraph, styles["BodyText"]))
            story.append(Spacer(1, 3))
        for table_data in section.tables:
            data = [[Paragraph(str(header), styles["Cell"]) for header in table_data.headers]]
            for row in table_data.rows:
                data.append([Paragraph(_safe(cell), styles["Cell"]) for cell in row])
            widths = table_data.widths
            pdf_table = Table(data, repeatRows=1, colWidths=widths, hAlign="LEFT")
            pdf_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            story.extend([pdf_table, Spacer(1, 6), Paragraph(table_note(section.title, table_data.headers), styles['BodyText']), Spacer(1, 6)])
        story.append(Spacer(1, 4))

    def _footer(canvas, doc_obj):  # noqa: ANN001
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawString(15 * mm, 8 * mm, f"NutriRisk AI · {document.title}")
        canvas.drawRightString(doc_obj.pagesize[0] - 15 * mm, 8 * mm, f"Página {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)


def render_docx(document: ReportDocument, path: Path) -> None:
    from app.services.interpretation import table_note
    from docx import Document as DocxDocument
    from docx.shared import Pt, RGBColor

    doc = DocxDocument()
    doc.add_heading(document.title, level=0)
    subtitle = doc.add_paragraph(document.subtitle)
    subtitle.runs[0].italic = True
    meta = doc.add_paragraph(
        f"Generado el {document.generated_at.strftime('%Y-%m-%d %H:%M UTC')} · {document.footer}"
    )
    meta.runs[0].font.size = Pt(8)
    meta.runs[0].font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    if document.kpis:
        table = doc.add_table(rows=2, cols=len(document.kpis))
        table.style = "Light Grid Accent 1"
        for index, item in enumerate(document.kpis):
            table.cell(0, index).text = _safe(item.get("label"))
            table.cell(1, index).text = _safe(item.get("value"))
        doc.add_paragraph('Interpretación: estos indicadores resumen el periodo y los filtros del reporte. Los conteos, las prevalencias y las métricas del modelo tienen unidades distintas; los datos sintéticos no acreditan utilidad clínica.')

    for section in document.sections:
        doc.add_heading(section.title, level=1)
        for paragraph in section.paragraphs:
            doc.add_paragraph(paragraph)
        for table_data in section.tables:
            table = doc.add_table(rows=1, cols=len(table_data.headers))
            table.style = "Light List Accent 1"
            for index, header in enumerate(table_data.headers):
                table.rows[0].cells[index].text = str(header)
            for row in table_data.rows:
                cells = table.add_row().cells
                for index, cell in enumerate(row):
                    cells[index].text = _safe(cell)
            doc.add_paragraph(table_note(section.title, table_data.headers))
    doc.save(str(path))


def render_xlsx(document: ReportDocument, path: Path) -> None:
    from app.services.interpretation import table_note
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    summary = workbook.active
    summary.title = "Resumen"
    header_fill = PatternFill("solid", fgColor="0F766E")
    header_font = Font(color="FFFFFF", bold=True)

    summary["A1"] = document.title
    summary["A1"].font = Font(size=14, bold=True)
    summary["A2"] = document.subtitle
    summary["A3"] = f"Generado el {document.generated_at.strftime('%Y-%m-%d %H:%M UTC')}"
    summary["A4"] = document.footer
    row = 6
    for item in document.kpis:
        summary.cell(row=row, column=1, value=_safe(item.get("label")))
        summary.cell(row=row, column=2, value=_safe(item.get("value")))
        row += 1

    summary.merge_cells(start_row=row+1,start_column=1,end_row=row+1,end_column=4)
    summary.cell(row=row+1,column=1,value='Interpretación: el resumen corresponde al periodo y filtros indicados. Distinga conteos, prevalencias y métricas predictivas; los datos sintéticos no acreditan utilidad clínica.').alignment=Alignment(wrap_text=True,vertical='top')
    summary.row_dimensions[row+1].height=90

    for index, section in enumerate(document.sections, start=1):
        title = section.title[:28].replace("/", "-").replace("\\", "-")
        sheet = workbook.create_sheet(title=f"{index}. {title}")
        current = 1
        sheet.cell(row=current, column=1, value=section.title).font = Font(bold=True, size=12)
        current += 2
        for paragraph in section.paragraphs:
            sheet.cell(row=current, column=1, value=paragraph)
            current += 1
        current += 1
        for table_data in section.tables:
            for column_index, header in enumerate(table_data.headers, start=1):
                cell = sheet.cell(row=current, column=column_index, value=str(header))
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            current += 1
            for row_values in table_data.rows:
                for column_index, value in enumerate(row_values, start=1):
                    cell = sheet.cell(row=current, column=column_index, value=_safe(value))
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                current += 1
            current += 1
            sheet.merge_cells(start_row=current,start_column=1,end_row=current,end_column=max(2,len(table_data.headers)))
            note=sheet.cell(row=current,column=1,value=table_note(section.title,table_data.headers))
            note.alignment=Alignment(wrap_text=True,vertical='top')
            sheet.row_dimensions[current].height=60
            current+=2
            for column_index, header in enumerate(table_data.headers, start=1):
                width = max(12, min(48, len(str(header)) + 6))
                sheet.column_dimensions[get_column_letter(column_index)].width = width
    workbook.save(str(path))


RENDERERS = {"pdf": render_pdf, "docx": render_docx, "xlsx": render_xlsx}


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def generate_report(
    db: Session,
    *,
    kind: str,
    fmt: str,
    params: dict[str, Any] | None = None,
    title: str | None = None,
    user_id: int | None = None,
) -> Report:
    """Build, render and register a report."""
    params = params or {}
    if kind not in BUILDERS:
        raise ValueError(f"Tipo de reporte no soportado: {kind}")
    if fmt not in RENDERERS:
        raise ValueError(f"Formato no soportado: {fmt}")

    report = Report(
        kind=kind,
        title=title or REPORT_KINDS[kind]["label"],
        fmt=fmt,
        params=params,
        status="RUNNING",
        created_by=user_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    try:
        document = BUILDERS[kind](db, params)
        if title:
            document.title = title
        extension = fmt
        filename = f"{kind}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{extension}"
        path = settings.storage_dir / "reports" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        RENDERERS[fmt](document, path)
        report.file_path = str(path)
        report.file_name = filename
        report.size_bytes = path.stat().st_size
        report.status = "READY"
        report.title = document.title
        db.commit()
        db.refresh(report)
        return report
    except Exception as exc:  # noqa: BLE001
        report.status = "FAILED"
        report.error = str(exc)
        db.commit()
        raise


def serialize_report(report: Report) -> dict[str, Any]:
    return {
        "id": report.id,
        "kind": report.kind,
        "title": report.title,
        "fmt": report.fmt,
        "params": report.params or {},
        "file_name": report.file_name,
        "size_bytes": report.size_bytes,
        "status": report.status,
        "error": report.error,
        "created_at": report.created_at,
        "download_url": f"/api/v1/reports/{report.id}/download" if report.status == "READY" else None,
    }


def dataset_catalog_summary(db: Session) -> dict[str, Any]:
    datasets = db.execute(select(Dataset)).scalars().all()
    return {
        "datasets": len(datasets),
        "children": db.scalar(select(func.count(Child.id))) or 0,
        "households": db.scalar(select(func.count(Household.id))) or 0,
        "indicators": db.scalar(select(func.count(AnthropometricIndicator.id))) or 0,
    }


def feature_label(name: str) -> str:
    return FEATURE_LABELS.get(name, name)
