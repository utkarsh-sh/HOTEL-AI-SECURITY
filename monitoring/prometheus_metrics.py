from prometheus_client import CollectorRegistry, Gauge, generate_latest


class PrometheusMetrics:
    """Expose HOTEL AI SECURITY metrics in Prometheus format."""

    def __init__(self):
        self.registry = CollectorRegistry()

        self.cpu_utilization = Gauge(
            "hotel_security_cpu_utilization_percent",
            "Current host CPU utilization percentage.",
            registry=self.registry,
        )
        self.memory_utilization = Gauge(
            "hotel_security_memory_utilization_percent",
            "Current host memory utilization percentage.",
            registry=self.registry,
        )
        self.disk_utilization = Gauge(
            "hotel_security_disk_utilization_percent",
            "Current host disk utilization percentage.",
            registry=self.registry,
        )
        self.monitoring_status = Gauge(
            "hotel_security_monitoring_status",
            "Current monitoring status: 1 for OK, 0 for ALERT.",
            registry=self.registry,
        )

        self.gpu_utilization = Gauge(
            "hotel_security_gpu_utilization_percent",
            "Current GPU utilization percentage.",
            ["gpu"],
            registry=self.registry,
        )
        self.gpu_memory_used = Gauge(
            "hotel_security_gpu_memory_used_bytes",
            "Current GPU memory used in bytes.",
            ["gpu"],
            registry=self.registry,
        )
        self.gpu_memory_total = Gauge(
            "hotel_security_gpu_memory_total_bytes",
            "Total GPU memory in bytes.",
            ["gpu"],
            registry=self.registry,
        )

        self.camera_status = Gauge(
            "hotel_security_camera_status",
            "Camera health status: 1 for ONLINE, 0 for OFFLINE.",
            ["camera_id"],
            registry=self.registry,
        )
        self.camera_fps = Gauge(
            "hotel_security_camera_fps",
            "Current observed camera FPS.",
            ["camera_id"],
            registry=self.registry,
        )

    def update_system_metrics(self, metrics, evaluation):
        """Update exported host and GPU metrics."""
        self.cpu_utilization.set(
            metrics["cpu"]["utilization_percent"]
        )
        self.memory_utilization.set(
            metrics["memory"]["utilization_percent"]
        )
        self.disk_utilization.set(
            metrics["disk"]["utilization_percent"]
        )

        self.monitoring_status.set(
            1 if evaluation["status"] == "OK" else 0
        )

        current_gpu_names = set()

        for index, gpu in enumerate(
            metrics.get("gpu", {}).get("gpus", [])
        ):
            gpu_name = gpu["name"] or f"gpu-{index}"
            current_gpu_names.add(gpu_name)

            self.gpu_utilization.labels(
                gpu=gpu_name
            ).set(
                gpu["utilization_percent"]
            )
            self.gpu_memory_used.labels(
                gpu=gpu_name
            ).set(
                gpu["memory_used_mb"] * 1024 * 1024
            )
            self.gpu_memory_total.labels(
                gpu=gpu_name
            ).set(
                gpu["memory_total_mb"] * 1024 * 1024
            )

        for gpu_name in self._known_gpu_names() - current_gpu_names:
            self.gpu_utilization.remove(gpu_name)
            self.gpu_memory_used.remove(gpu_name)
            self.gpu_memory_total.remove(gpu_name)

    def update_camera_metrics(self, cameras):
        """Update exported camera health metrics."""
        current_camera_ids = set()

        for camera in cameras:
            camera_id = str(camera["camera_id"])
            current_camera_ids.add(camera_id)

            self.camera_status.labels(
                camera_id=camera_id
            ).set(
                1 if camera["status"] == "ONLINE" else 0
            )

            fps = camera["fps"]
            self.camera_fps.labels(
                camera_id=camera_id
            ).set(
                float(fps) if fps is not None else 0.0
            )

        for camera_id in self._known_camera_ids() - current_camera_ids:
            self.camera_status.remove(camera_id)
            self.camera_fps.remove(camera_id)

    def _known_gpu_names(self):
        return {
            sample.labels["gpu"]
            for sample in self.gpu_utilization.collect()[0].samples
            if sample.labels.get("gpu")
        }

    def _known_camera_ids(self):
        return {
            sample.labels["camera_id"]
            for sample in self.camera_status.collect()[0].samples
            if sample.labels.get("camera_id")
        }

    def render(self):
        """Return metrics in Prometheus exposition format."""
        return generate_latest(self.registry)
