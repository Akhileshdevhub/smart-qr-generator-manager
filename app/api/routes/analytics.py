"""Analytics routes: an account-wide overview and per-QR detail.

Both are authenticated and ownership-checked — analytics are private to the QR's
owner, even though the redirect that generates them is public.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_owned_project
from app.db.database import get_db
from app.db.models import QRProject, User
from app.schemas.analytics import DashboardOverview, QRAnalytics
from app.services import analytics_service

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics/overview", response_model=DashboardOverview)
def overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return analytics_service.dashboard_overview(db, current_user.id)


@router.get("/qr/{qr_id}/analytics", response_model=QRAnalytics)
def qr_detail(project: QRProject = Depends(get_owned_project), db: Session = Depends(get_db)):
    return analytics_service.qr_analytics(db, project)
