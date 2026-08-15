from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models import SavedSearch
from ..dependencies import get_session
from ..schemas import SavedSearchRequest, SavedSearchResponse

router = APIRouter(prefix="/api/saved-searches", tags=["saved-searches"])


@router.get("", response_model=list[SavedSearchResponse])
def list_saved_searches(session: Annotated[Session, Depends(get_session)]) -> list[SavedSearchResponse]:
    saved_searches = session.execute(select(SavedSearch).order_by(SavedSearch.name)).scalars().all()
    return [_to_response(saved_search) for saved_search in saved_searches]


@router.post("", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
def create_saved_search(
        request: SavedSearchRequest,
        session: Annotated[Session, Depends(get_session)],
) -> SavedSearchResponse:
    existing = session.execute(
        select(SavedSearch).where(SavedSearch.name == request.name)
    ).scalar_one_or_none()

    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Saved search '{request.name}' already exists")

    saved_search = SavedSearch(name=request.name, query=request.query)
    session.add(saved_search)
    session.flush()
    return _to_response(saved_search)


@router.put("/{saved_search_id}", response_model=SavedSearchResponse)
def update_saved_search(
        saved_search_id: int,
        request: SavedSearchRequest,
        session: Annotated[Session, Depends(get_session)],
) -> SavedSearchResponse:
    saved_search = session.get(SavedSearch, saved_search_id)
    if saved_search is None:
        raise HTTPException(status_code=404, detail=f"Saved search {saved_search_id} not found")

    saved_search.name = request.name
    saved_search.query = request.query
    session.flush()
    return _to_response(saved_search)


@router.delete("/{saved_search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_search(
        saved_search_id: int,
        session: Annotated[Session, Depends(get_session)],
) -> Response:
    saved_search = session.get(SavedSearch, saved_search_id)
    if saved_search is None:
        raise HTTPException(status_code=404, detail=f"Saved search {saved_search_id} not found")

    session.delete(saved_search)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _to_response(saved_search: SavedSearch) -> SavedSearchResponse:
    return SavedSearchResponse(
        id=saved_search.id,
        name=saved_search.name,
        query=saved_search.query,
        created_at=saved_search.created_at,
        updated_at=saved_search.updated_at,
    )
