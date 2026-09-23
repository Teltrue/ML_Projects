"""Component library and template metadata."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.catalog import Catalog
from app.deps import get_catalog
from app.schemas.api import ComponentOut, ParameterOut, TemplateOut
from app.schemas.design import TEMPLATE_MODELS

router = APIRouter(prefix="/api", tags=["catalog"])
CatalogDep = Annotated[Catalog, Depends(get_catalog)]

TEMPLATE_INFO = {
    "arm": {
        "name": "3-Axis Robotic Arm",
        "tagline": "Desktop pick-and-place arm with a gripper",
        "description": (
            "Base yaw, shoulder and elbow servos plus a gripper. RoboCraft derives the DH "
            "model, solves inverse kinematics, sizes every servo for your payload and wires a "
            "safe, separate servo power rail."
        ),
    },
    "rover": {
        "name": "Differential-Drive Rover",
        "tagline": "Two- or four-wheel rover with obstacle avoidance",
        "description": (
            "Skid/differential steering with DC gearmotors. RoboCraft budgets drive forces "
            "for your terrain, matches motors, battery and an H-bridge driver, and simulates "
            "the rover driving."
        ),
    },
}


def _options(source: str, catalog: Catalog) -> list[dict[str, Any]]:
    if source == "microcontroller":
        return [{"value": c.id, "label": c.name,
                 "note": f"{c.spec('logic_v'):g} V logic · {', '.join(c.spec('languages'))}"}
                for c in catalog.by_category("microcontroller")]
    template = source.split(":", 1)[1]
    sources = [c for c in catalog.by_category("power_source") if c.spec("selectable", True)]
    if template == "rover":
        sources = [c for c in sources if c.spec("kind") == "battery"]
        auto = "Auto (best match)"
    else:
        auto = "Auto (6 V adapter)"
    return [{"value": "auto", "label": auto}] + [
        {"value": c.id, "label": c.name} for c in sources
    ]


def template_parameters(template: str, catalog: Catalog) -> list[ParameterOut]:
    params = []
    for key, field in TEMPLATE_MODELS[template].model_fields.items():
        extra = field.json_schema_extra if isinstance(field.json_schema_extra, dict) else {}
        ui = dict(extra.get("ui", {}))
        if not ui:
            continue
        options_from = ui.pop("options_from", None)
        if options_from:
            ui["options"] = _options(options_from, catalog)
        params.append(ParameterOut(key=key, help=field.description or "", **ui))
    return params


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(catalog: CatalogDep) -> list[TemplateOut]:
    out = []
    for template_id, model in TEMPLATE_MODELS.items():
        params = template_parameters(template_id, catalog)
        groups = list(dict.fromkeys(p.group for p in params))
        out.append(TemplateOut(id=template_id, defaults=model().model_dump(), groups=groups,
                               parameters=params, **TEMPLATE_INFO[template_id]))
    return out


@router.get("/components", response_model=list[ComponentOut])
def list_components(catalog: CatalogDep, category: str | None = None) -> list[ComponentOut]:
    components = catalog.by_category(category) if category else catalog.all()
    return [ComponentOut(**c.__dict__) for c in components]
