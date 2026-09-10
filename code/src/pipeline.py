from  .analyzers.image_quality import ImageQualityAnalyzer
from  .analyzers.damage_detector import DamageDetector 
from  .analyzers.severity_estimator import SeverityEstimator
from  .analyzers.fraud_detector import FraudDetector
from  .image_analyzer import analyze_image

class AnalysisPipeline:

    def __init__(self):
        
        self.analyzers =[ImageQualityAnalyzer(), DamageDetector(), SeverityEstimator(), FraudDetector()]
    
    def run(self, image_path, claim_object):
        analysis = analyze_image(image_path, claim_object)

        context = {
            "analysis": analysis
        }

        result = {}

        for analyzer in self.analyzers:
            result.update(
                analyzer.analyze(image_path, context)
            )

        return result    