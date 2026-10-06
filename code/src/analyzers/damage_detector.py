from .base import Analyzer

class DamageDetector(Analyzer):

    def analyze(self, image_path, context):
        analysis = context["analysis"]

        return {
            "damage_visible": analysis["damage_visible"],
            "issue_type": analysis["issue_type"],
            "object_part": analysis["object_part"],
        }