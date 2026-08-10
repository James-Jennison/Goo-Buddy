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


def cc1_idle_after_job_status(*, fan_speed: int | None = 42, chamber_light: bool | None = True) -> dict:
    """Redacted deterministic CC1-shaped idle status with retained counters.

    The values establish field shape and stale-data handling only. They are not
    a raw device response and contain no printer identity or file information.
    """

    payload = status(current_status=0)
    status_record = payload["Status"]
    status_record["TempOfNozzle"] = 30.0
    status_record["TempOfHotbed"] = 29.0
    status_record["TempOfBox"] = 28.0
    status_record["TempTargetNozzle"] = 0.0
    status_record["TempTargetHotbed"] = 0.0
    status_record["TempTargetBox"] = 0.0
    status_record["CurrentFanSpeed"] = fan_speed
    status_record["LightStatus"] = {"SecondLight": chamber_light}
    status_record["PrintInfo"] = {
        "CurrentTicks": 125,
        "TotalTicks": 128,
        "CurrentLayer": 126,
        "TotalLayer": 128,
        "ErrorNumber": 0,
    }
    return payload
