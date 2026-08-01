"""Obviously synthetic SDCP v3-shaped observations for driver tests."""


def attributes(*, capabilities: list[str] | None = None) -> dict:
    return {
        "Attributes": {
            "Name": "Synthetic Centauri",
            "MachineName": "Synthetic-Centauri-01",
            "FirmwareVersion": "0.0.0-fixture",
            "Capabilities": capabilities or ["temperature", "job_status", "job_progress", "layers"],
        }
    }


def status(*, current_status: int = 1, error: int = 0) -> dict:
    return {
        "Status": {
            "CurrentStatus": current_status,
            "TempOfNozzle": 215.0,
            "TargetTempOfNozzle": 220.0,
            "TempOfHotbed": 60.0,
            "TargetTempOfHotbed": 60.0,
            "PrintInfo": {
                "Filename": "synthetic-cube.gcode",
                "CurrentTicks": 25,
                "TotalTicks": 100,
                "CurrentLayer": 5,
                "TotalLayer": 20,
                "ErrorNumber": error,
            },
        }
    }
