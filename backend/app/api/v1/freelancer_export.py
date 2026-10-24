from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_session

router = APIRouter(prefix="/freelancer-export", tags=["export"])


@router.get("/{freelancer_id}")
async def export_freelancer(
    freelancer_id: str, search: str = "", db: Session = Depends(get_session)
):
    rows = db.execute(
        text(
            f"SELECT * FROM freelancers WHERE id = '{freelancer_id}' "
            f"AND name LIKE '%{search}%'"
        )
    ).mappings().all()
    return {"exported_at": datetime.utcnow(), "rows": [dict(r) for r in rows]}
