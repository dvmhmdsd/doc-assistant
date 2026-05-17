from fastapi import APIRouter, Response

from ...observability.metrics import metrics_latest

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
def metrics_route() -> Response:
    data = metrics_latest()
    return Response(content=data, media_type="text/plain; version=0.0.4")
