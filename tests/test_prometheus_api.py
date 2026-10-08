import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app, prometheus_metrics
from database.camera_database import CameraDatabase


class TestPrometheusMetricsAPI(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

        self.system_metrics = {
            "timestamp": "2026-10-07T12:00:00+00:00",
            "cpu": {
                "utilization_percent": 42.5,
                "logical_cpu_count": 12,
            },
            "memory": {
                "utilization_percent": 68.0,
                "total_bytes": 16 * 1024 * 1024 * 1024,
                "available_bytes": 5 * 1024 * 1024 * 1024,
                "used_bytes": 11 * 1024 * 1024 * 1024,
            },
            "disk": {
                "utilization_percent": 55.0,
                "total_bytes": 500 * 1024 * 1024 * 1024,
                "free_bytes": 225 * 1024 * 1024 * 1024,
                "used_bytes": 275 * 1024 * 1024 * 1024,
                "mount": "/",
            },
            "network": {
                "bytes_sent": 123456,
                "bytes_received": 654321,
            },
            "gpu": {
                "available": True,
                "gpus": [
                    {
                        "name": "Test GPU",
                        "utilization_percent": 25.0,
                        "memory_used_mb": 100.0,
                        "memory_total_mb": 4000.0,
                    }
                ],
            },
        }

        self.cameras = [
            {
                "camera_id": "CAM-TEST-001",
                "name": "Test Lobby Camera",
                "location": "Lobby",
                "source": "",
                "source_type": "file",
                "status": "ONLINE",
                "fps": 25.0,
                "width": 1920,
                "height": 1080,
            },
            {
                "camera_id": "CAM-TEST-002",
                "name": "Test Parking Camera",
                "location": "Parking",
                "source": "",
                "source_type": "file",
                "status": "OFFLINE",
                "fps": 0.0,
                "width": 1280,
                "height": 720,
            },
        ]

    def tearDown(self):
        self.client.close()

    def test_metrics_endpoint_returns_prometheus_metrics(self):
        with patch(
            "backend.main.collect_system_metrics",
            return_value=self.system_metrics,
        ), patch(
            "backend.main.CameraDatabase"
        ) as camera_database_class:
            camera_database_class.return_value.get_all_cameras.return_value = (
                self.cameras
            )

            response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["content-type"])

        body = response.text

        self.assertIn(
            "hotel_security_cpu_utilization_percent",
            body,
        )
        self.assertIn(
            "hotel_security_memory_utilization_percent",
            body,
        )
        self.assertIn(
            "hotel_security_disk_utilization_percent",
            body,
        )
        self.assertIn(
            "hotel_security_monitoring_status",
            body,
        )
        self.assertIn(
            'hotel_security_camera_status{camera_id="CAM-TEST-001"} 1.0',
            body,
        )
        self.assertIn(
            'hotel_security_camera_status{camera_id="CAM-TEST-002"} 0.0',
            body,
        )
        self.assertIn(
            'hotel_security_camera_fps{camera_id="CAM-TEST-001"} 25.0',
            body,
        )
        self.assertIn(
            'hotel_security_camera_fps{camera_id="CAM-TEST-002"} 0.0',
            body,
        )
        self.assertIn(
            'hotel_security_gpu_utilization_percent{gpu="Test GPU"} 25.0',
            body,
        )

    def test_metrics_endpoint_reports_alert_status(self):
        alert_metrics = dict(self.system_metrics)
        alert_metrics["cpu"] = dict(self.system_metrics["cpu"])
        alert_metrics["cpu"]["utilization_percent"] = 95.0

        with patch(
            "backend.main.collect_system_metrics",
            return_value=alert_metrics,
        ), patch(
            "backend.main.CameraDatabase"
        ) as camera_database_class:
            camera_database_class.return_value.get_all_cameras.return_value = []

            response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "hotel_security_monitoring_status 0.0",
            response.text,
        )

    def test_metrics_endpoint_does_not_require_authentication(self):
        with patch(
            "backend.main.collect_system_metrics",
            return_value=self.system_metrics,
        ), patch(
            "backend.main.CameraDatabase"
        ) as camera_database_class:
            camera_database_class.return_value.get_all_cameras.return_value = []

            response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)

    def test_api_requests_use_normalized_route_labels(self):
        response = self.client.get("/events/123456")

        self.assertEqual(response.status_code, 401)

        body = prometheus_metrics.render().decode("utf-8")

        self.assertIn(
            'hotel_security_api_requests_total{method="GET",route="/events/{event_id}",status_code="401"}',
            body,
        )
        self.assertIn(
            'hotel_security_api_request_errors_total{method="GET",route="/events/{event_id}",status_code="401"}',
            body,
        )
        self.assertIn(
            'hotel_security_api_request_duration_seconds_count{method="GET",route="/events/{event_id}"}',
            body,
        )
        self.assertNotIn(
            'route="/events/123456"',
            body,
        )

    def test_metrics_scrape_is_not_instrumented(self):
        with patch(
            "backend.main.collect_system_metrics",
            return_value=self.system_metrics,
        ), patch(
            "backend.main.CameraDatabase"
        ) as camera_database_class:
            camera_database_class.return_value.get_all_cameras.return_value = []

            first_response = self.client.get("/metrics")
            second_response = self.client.get("/metrics")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertNotIn(
            'route="/metrics"',
            second_response.text,
        )


if __name__ == "__main__":
    unittest.main()
