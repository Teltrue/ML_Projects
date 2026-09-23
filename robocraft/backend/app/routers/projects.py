"""Saved projects (a user's designs)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import ProjectRow
from app.deps import get_db
from app.schemas.api import ProjectIn, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])
DbDep = Annotated[Session, Depends(get_db)]


def _get(db: Session, project_id: str) -> ProjectRow:
    row = db.get(ProjectRow, project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return row


@router.get("", response_model=list[ProjectOut])
def list_projects(db: DbDep) -> list[ProjectRow]:
    return list(db.scalars(select(ProjectRow).order_by(ProjectRow.updated_at.desc())))


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, db: DbDep) -> ProjectRow:
    row = ProjectRow(name=body.name, template=body.design.template,
                     design=body.design.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: DbDep) -> ProjectRow:
    return _get(db, project_id)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectIn, db: DbDep) -> ProjectRow:
    row = _get(db, project_id)
    if row.template != body.design.template:
        raise HTTPException(status_code=422, detail="A project can't change template")
    row.name = body.name
    row.design = body.design.model_dump()
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: DbDep) -> Response:
    db.delete(_get(db, project_id))
    db.commit()
    return Response(status_code=204)
