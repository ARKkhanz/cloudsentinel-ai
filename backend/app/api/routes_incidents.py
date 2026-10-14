from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.incidents import (
    IncidentListResponse,
    IncidentResponse,
)
from backend.app.services.incident_service import (
    get_incident_by_id,
    get_incidents,
)

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


@router.get(
    "",
    response_model=IncidentListResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve list of persisted anomaly incidents",
)
def list_incidents(
    service: Optional[str] = Query(None, description="Filter incidents by service identifier"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (open, resolved, etc.)"),
    detector_name: Optional[str] = Query(None, description="Filter by detector algorithm"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of incidents to return"),
    db: Session = Depends(get_db),
) -> IncidentListResponse:
    """
    List persisted incidents ordered newest-first.
    Returns complete evidence summaries and filter metadata.
    """
    return get_incidents(
        db=db,
        service=service,
        status=status_filter,
        detector_name=detector_name,
        limit=limit,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve complete evidence and metadata for a specific incident",
)
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
) -> IncidentResponse:
    """
    Lookup a specific incident by its unique UUID.
    Returns HTTP 404 if the incident does not exist.
    """
    incident = get_incident_by_id(db=db, incident_id=incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found",
        )
    return IncidentResponse.model_validate(incident)
