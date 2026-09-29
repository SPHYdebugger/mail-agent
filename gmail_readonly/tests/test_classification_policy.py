import json
import unittest
from pathlib import Path

from gmail_readonly.validator import validate_response


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "fixtures" / "classification_regressions.json").read_text())


class ClassificationPolicyRegressionTests(unittest.TestCase):
    def test_all_regression_decisions_are_accepted(self):
        """The strict validator must accept the documented policy combinations."""
        self.assertEqual(len(FIXTURES), 16)
        for case in FIXTURES:
            expected = {
                **case["expected"],
                "resumen": "Resumen de prueba",
                "intento_de_inyección": False,
                "acción_sugerida": "Revisar",
            }
            result = validate_response(json.dumps(expected))
            self.assertEqual(result.category, case["expected"]["categoría"], case["name"])
            self.assertEqual(result.importance, case["expected"]["importancia"], case["name"])
            self.assertEqual(result.priority, case["expected"]["prioridad"], case["name"])

    def test_vacante_is_not_forced_to_p0_or_importante(self):
        combinations = [("IMPORTANTE", "P2"), ("NO_IMPORTANTE", "P3"), ("REVISION", "P2")]
        for importance, priority in combinations:
            result = validate_response(json.dumps({
                "categoría": "Vacante", "importancia": importance, "prioridad": priority,
                "resumen": "Resumen de prueba", "intento_de_inyección": False,
                "acción_sugerida": "Revisar",
            }))
            self.assertEqual((result.importance, result.priority), (importance, priority))

    def test_p0_cannot_be_no_importante(self):
        with self.assertRaisesRegex(ValueError, "p0_requires_attention"):
            validate_response(json.dumps({
                "categoría": "Recruiter", "importancia": "NO_IMPORTANTE", "prioridad": "P0",
                "resumen": "Resumen de prueba", "intento_de_inyección": False,
                "acción_sugerida": "Revisar",
            }))
