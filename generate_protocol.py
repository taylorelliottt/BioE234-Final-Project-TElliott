"""
tools/generate_protocol.py
===========================
Generate an Opentrons OT-2 Python protocol script from a task description.
"""

import json
import matplotlib
matplotlib.use("Agg")

from .._lib.generator import generate_ot2_script


class GenerateProtocol:
    def initiate(self) -> None:
        pass

    def run(self, task_type: str, parameters_json: str) -> str:
        try:
            params = json.loads(parameters_json)
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"Invalid parameters_json: {exc}"})

        params["task_type"] = task_type

        try:
            script = generate_ot2_script(params)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": f"Script generation failed: {exc}"})

        return json.dumps({"script": script})


_instance = GenerateProtocol()
_instance.initiate()
generate_protocol = _instance.run
