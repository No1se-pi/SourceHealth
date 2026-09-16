"""Analyses HTTP endpoints."""

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import Response

from sourcehealth.application.services import ServiceError
from sourcehealth.markdown import render_markdown

from ..dependencies import public_run
from ..schemas import AnalysisDetails, AnalysisSummary

router = APIRouter()



@router.get("/api/v1/analyses/{analysis_id}", response_model=AnalysisDetails)
def analysis(analysis_id: UUID, request: Request):
    with request.app.state.sessions() as db:
        run = public_run(db, analysis_id)
        return AnalysisDetails(**AnalysisSummary.model_validate(run).model_dump(), category_scores=run.category_scores,
                               data_coverage=run.data_coverage, recommendations=run.recommendations,
                               checks=run.results.get("checks", {}))


@router.get("/api/v1/analyses/{analysis_id}/report.md", response_class=Response,
         responses={200: {"content": {"text/markdown": {"schema": {"type": "string"}}}}})
def markdown(analysis_id: UUID, request: Request):
    with request.app.state.sessions() as db:
        run = public_run(db, analysis_id)
        if run.status not in {"completed", "partial"}:
            raise ServiceError("report_not_ready", 409)
        return Response(render_markdown(run.results), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="sourcehealth-{analysis_id}.md"'})
