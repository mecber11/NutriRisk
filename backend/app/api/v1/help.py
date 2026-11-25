"""In-app help content."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import require_permission
from app.core.rbac import Action, Module
from app.models.user import User
from app.schemas.system import FaqItem, HelpSection

router = APIRouter(prefix="/help", tags=["Ayuda"])

HELP_READ = Depends(require_permission(Module.HELP, Action.READ))

SECTIONS: list[HelpSection] = [
    HelpSection(
        code="inicio",
        title="Primeros pasos",
        content=[
            "Inicie sesión con su cuenta institucional. Los roles determinan qué módulos puede ver y operar.",
            "El tablero resume la situación nutricional, el riesgo predicho y los territorios prioritarios.",
            "Use los filtros de año, región, sexo y grupo de edad para acotar todos los indicadores.",
        ],
        links=[{"label": "Manual de usuario", "href": "/MANUAL_USUARIO.md"}],
    ),
    HelpSection(
        code="datos",
        title="Carga y calidad de datos",
        content=[
            "Descargue la plantilla canónica en Datasets → Plantilla CSV y complete los campos obligatorios.",
            "Al cargar un archivo se valida el esquema, se calculan indicadores de calidad y se registra la ingesta.",
            "Los datos de demostración son sintéticos y están identificados como tales en todo el sistema.",
        ],
    ),
    HelpSection(
        code="indicadores",
        title="Indicadores antropométricos OMS",
        content=[
            "Los z-scores HAZ, WAZ, WHZ y BAZ se calculan con los estándares OMS 2006 (parámetros LMS).",
            "Retraso del crecimiento: HAZ < -2 DE; emaciación: WHZ < -2 DE; bajo peso: WAZ < -2 DE.",
            "El módulo de referencia muestra el autochequeo contra los puntos de corte publicados por la OMS.",
        ],
    ),
    HelpSection(
        code="modelos",
        title="Modelado y validación",
        content=[
            "Se entrenan Random Forest, XGBoost y CatBoost con validación agrupada por región.",
            "El híbrido XGBoost + regresión espacial añade rezagos territoriales y calibración SAR de residuos.",
            "El CNN-LSTM se evalúa con partición por territorio y prueba de estrés leave-one-region-out.",
        ],
    ),
    HelpSection(
        code="xai",
        title="Explicabilidad y equidad",
        content=[
            "SHAP global muestra qué determinantes pesan más; SHAP local explica el riesgo de un niño.",
            "La equidad se evalúa con Fairlearn por sexo, quintil de riqueza, área y región.",
            "Un resultado es aceptable cuando la disparidad de tasa de selección no supera 0,20.",
        ],
    ),
    HelpSection(
        code="reportes",
        title="Reportes y exportaciones",
        content=[
            "Genere fichas territoriales, rankings, desempeño de modelos, equidad y bitácora.",
            "Formatos disponibles: PDF, Word (.docx) y Excel (.xlsx).",
            "n8n puede programar la generación periódica mediante webhooks.",
        ],
    ),
    HelpSection(
        code="auditoria",
        title="Bitácora y seguridad",
        content=[
            "Cada solicitud a la API queda registrada con usuario, rol, módulo, acción, IP y resultado.",
            "La bitácora es inmutable: la base de datos bloquea actualizaciones y borrados.",
            "El rol Auditor puede consultar y exportar la bitácora sin modificar datos.",
        ],
    ),
]

FAQ: list[FaqItem] = [
    FaqItem(
        question="¿Los datos mostrados son reales?",
        answer="No. La demostración usa un país y una encuesta sintéticos generados con el motor de NutriRisk AI. "
        "Al cargar datos DHS, UNICEF o WorldPop el sistema los procesa con el mismo pipeline.",
    ),
    FaqItem(
        question="¿Cómo se interpretan los z-scores?",
        answer="Un z-score expresa la distancia respecto a la mediana de la población de referencia en desviaciones estándar. "
        "Valores por debajo de -2 indican desnutrición según el indicador correspondiente.",
    ),
    FaqItem(
        question="¿Por qué el F1 a umbral 0,5 es bajo?",
        answer="La prevalencia es cercana al 19 %, por lo que el umbral 0,5 es conservador. El sistema reporta además el umbral "
        "que maximiza F1 y un umbral de tamizaje con sensibilidad objetivo del 75 %.",
    ),
    FaqItem(
        question="¿Qué significa Moran's I de residuos?",
        answer="Mide autocorrelación espacial de los errores del modelo. Un valor cercano a cero con p > 0,05 indica que "
        "no queda estructura espacial sin explicar.",
    ),
    FaqItem(
        question="¿Puedo usar mi propia clave de OpenAI con el agente?",
        answer="Sí. Configure OPENAI_API_KEY y LLM_PROVIDER=openai en el archivo .env; sin clave, el agente usa un motor "
        "determinista basado en reglas con las mismas herramientas.",
    ),
    FaqItem(
        question="¿Cómo restablezco mi contraseña?",
        answer="Use 'Recuperar contraseña' en la pantalla de acceso. En modo demostración el token se muestra en pantalla "
        "para completar el flujo sin servidor de correo.",
    ),
]


@router.get("", response_model=list[HelpSection], summary="Contenido de ayuda")
def help_sections(_: User = HELP_READ) -> list[HelpSection]:
    return SECTIONS


@router.get("/faq", response_model=list[FaqItem], summary="Preguntas frecuentes")
def faq(_: User = HELP_READ) -> list[FaqItem]:
    return FAQ
