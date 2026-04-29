from fastapi.testclient import TestClient

from backend.main import app
from backend.interfaces.api import monthly_report as monthly_report_api
from backend.interfaces.api.monthly_report import get_monthly_report_service


class FakeMonthlyReportService:
    def queue_report_generation(self, report_month: str, regenerate: bool = False):
        return type(
            "QueueResult",
            (),
            {
                "queued": True,
                "report": {
                    "id": "report-1",
                    "report_month": report_month,
                    "status": "PROCESSING",
                    "model_provider": "fake",
                    "model_name": "fake-model",
                    "summary_text": "",
                    "report": {},
                    "facts": {},
                    "generated_at": "2026-04-29T00:00:00",
                },
            },
        )()

    def process_queued_report(self, report_month: str):
        return None

    def try_generate_report(self, report_month: str, regenerate: bool = False):
        return {
            "id": "report-1",
            "report_month": report_month,
            "status": "READY",
            "model_provider": "fake",
            "model_name": "fake-model",
            "summary_text": "summary",
            "report": {"monthly_summary": "summary"},
            "facts": {"report_month": report_month},
            "generated_at": "2026-04-29T00:00:00",
        }

    def get_report(self, report_month: str):
        if report_month == "2026-04":
            return self.try_generate_report(report_month)
        return None

    def list_reports(self, limit: int = 12):
        return [self.try_generate_report("2026-04")]


def test_generate_monthly_report_api(monkeypatch):
    app.dependency_overrides[get_monthly_report_service] = lambda: FakeMonthlyReportService()
    monkeypatch.setattr(monthly_report_api, "run_monthly_report_generation", lambda report_month: None)
    client = TestClient(app)

    response = client.post(
        "/api/monthly-reports/generate",
        json={"report_month": "2026-04", "regenerate": True},
    )

    assert response.status_code == 202
    assert response.json()["report_month"] == "2026-04"
    assert response.json()["status"] == "PROCESSING"

    list_response = client.get("/api/monthly-reports")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    detail_response = client.get("/api/monthly-reports/2026-04")
    assert detail_response.status_code == 200

    not_found_response = client.get("/api/monthly-reports/2026-05")
    assert not_found_response.status_code == 404

    app.dependency_overrides.clear()
