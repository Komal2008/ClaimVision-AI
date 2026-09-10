from .base import Analyzer

class ImageQualityAnalyzer(Analyzer):

    def analyze(self, image_path, context):
        return {
            "valid_image": context["analysis"]["valid_image"],
            "quality_flags": context["analysis"]["quality_flags"],
        }
