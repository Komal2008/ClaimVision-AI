from .base import Analyzer

class SeverityEstimator(Analyzer):

    def analyze(self, image_path, context):
        analysis = context["analysis"]

        return {
            "severity": analysis["severity"],
            "confidence_score": analysis["confidence_score"],
            "estimated_cost": analysis["estimated_cost"],
        }
    