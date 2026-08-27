from datetime import datetime

from pydantic import BaseModel


class BreakdownItem(BaseModel):
    label: str
    count: int


class TimeSeriesPoint(BaseModel):
    date: str      # YYYY-MM-DD
    count: int


class DashboardOverview(BaseModel):
    total_qr: int
    active_qr: int
    total_scans: int
    scans_today: int
    scans_this_week: int
    scans_over_time: list[TimeSeriesPoint]
    top_qr: list["TopQRItem"]


class TopQRItem(BaseModel):
    id: int
    name: str
    short_id: str
    scan_count: int


class QRAnalytics(BaseModel):
    qr_id: int
    name: str
    total_scans: int
    scans_today: int
    scans_this_week: int
    scans_over_time: list[TimeSeriesPoint]
    device_breakdown: list[BreakdownItem]
    browser_breakdown: list[BreakdownItem]
    country_breakdown: list[BreakdownItem]
    contains_demo_data: bool  # honesty flag: true if any scan row is synthetic seed data


DashboardOverview.model_rebuild()
