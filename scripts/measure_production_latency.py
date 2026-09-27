"""Measure end-to-end latency through the production CCTV event path."""

import json
from pathlib import Path

from ai.run_intrusion_detection import (
    CAMERA_CONFIG_PATH,
    OUTPUT_DIRECTORY,
    RULES_CONFIG_PATH,
    ZONE_PATH,
    WEAPON_MODEL_PATH,
    FIRE_SMOKE_MODEL_PATH,
    CameraManager,
    CameraDatabase,
    NotificationDispatcher,
    PersonDetector,
    ZoneDatabase,
    ZoneDetector,
    ConsoleNotificationProvider,
    load_camera_configs,
    load_camera_configs_from_database,
    load_rule_config,
    load_runtime_zones,
    process_camera_worker,
)


BENCHMARK_DIRECTORY = Path(
    OUTPUT_DIRECTORY
) / "latency_benchmark"

BENCHMARK_DATABASE = (
    BENCHMARK_DIRECTORY / "benchmark.db"
)

REPORT_PATH = (
    BENCHMARK_DIRECTORY
    / "production_latency_CAM-001.json"
)


def main():
    BENCHMARK_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    if BENCHMARK_DATABASE.exists():
        BENCHMARK_DATABASE.unlink()

    camera_manager = None
    notification_dispatcher = None
    camera_database = CameraDatabase(
        str(BENCHMARK_DATABASE)
    )

    try:
        bootstrap_cameras = load_camera_configs(
            CAMERA_CONFIG_PATH
        )

        camera_database.initialize_from_bootstrap(
            bootstrap_cameras
        )

        camera_configs = load_camera_configs_from_database(
            camera_database
        )

        camera_config = next(
            config
            for config in camera_configs
            if config.camera_id == "CAM-001"
        )

        camera_manager = CameraManager(
            [camera_config]
        )

        opened = camera_manager.open_all()

        if "CAM-001" not in opened:
            raise RuntimeError(
                "CAM-001 source failed to open."
            )

        zone_database = ZoneDatabase(
            str(BENCHMARK_DATABASE)
        )

        zones = load_runtime_zones(
            zone_database,
            ZONE_PATH,
        )

        rule_config = load_rule_config(
            RULES_CONFIG_PATH
        )

        crowding_config = rule_config.get(
            "crowding",
            {},
        )

        after_hours_config = rule_config.get(
            "after_hours",
            {},
        )

        detector = PersonDetector()

        zone_detector = ZoneDetector(
            zones
        )

        notification_dispatcher = (
            NotificationDispatcher(
                providers={
                    "CONSOLE":
                    ConsoleNotificationProvider(),
                },
                database_path=str(
                    BENCHMARK_DATABASE
                ),
                max_workers=2,
                max_retries=2,
            )
        )

        result = process_camera_worker(
            camera_config=camera_config,
            camera_manager=camera_manager,
            detector=detector,
            zones=zones,
            zone_detector=zone_detector,
            notification_dispatcher=(
                notification_dispatcher
            ),
            crowding_config=crowding_config,
            after_hours_config=after_hours_config,
            database_path=str(BENCHMARK_DATABASE),
        )

        notification_dispatcher.shutdown()

        if result.get("error") is not None:
            raise RuntimeError(
                result["error"]
            )

        report = {
            "report_version": "1.0",
            "benchmark": {
                "camera_id": camera_config.camera_id,
                "video": camera_config.source,
                "ai_fps": camera_config.ai_fps,
                "database": str(
                    BENCHMARK_DATABASE
                ),
            },
            "processing": {
                "frames": result["frames"],
                "ai_frames": result["ai_frames"],
                "events": result["events"],
            },
            "latency": result["latency"],
            "target": {
                "end_to_end_p95_ms": 10000.0,
                "criterion": (
                    "Measured p95 end-to-end "
                    "frame-to-notification latency "
                    "for successfully queued "
                    "notifications."
                ),
            },
        }

        REPORT_PATH.write_text(
            json.dumps(
                report,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        print()
        print("=" * 60)
        print("PRODUCTION LATENCY BENCHMARK COMPLETE")
        print("=" * 60)
        print(
            f"Camera       : "
            f"{camera_config.camera_id}"
        )
        print(
            f"Video        : "
            f"{camera_config.source}"
        )
        print(
            f"Frames       : "
            f"{result['frames']}"
        )
        print(
            f"AI frames    : "
            f"{result['ai_frames']}"
        )
        print(
            f"Events       : "
            f"{result['events']}"
        )
        print(
            f"Latency p95  : "
            f"{result['latency']['overall']['p95_ms']} ms"
        )
        print(
            f"Report       : "
            f"{REPORT_PATH}"
        )
        print("=" * 60)

    finally:
        if notification_dispatcher is not None:
            notification_dispatcher.shutdown()

        if camera_manager is not None:
            camera_manager.release_all()

        camera_database.close()


if __name__ == "__main__":
    main()
