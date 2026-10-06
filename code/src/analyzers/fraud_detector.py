from .base import Analyzer

class FraudDetector(Analyzer):

    def analyze(self, image_path, context):
        analysis = context["analysis"]

        return {
            "fraud_risk": analysis["fraud_risk"],
            "fraud_risk_score": analysis["fraud_risk_score"],
        }