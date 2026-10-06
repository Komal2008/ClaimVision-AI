from abc import ABC, abstractmethod

class Analyzer(ABC):

    @abstractmethod
    def analyze(self, image_path, context):
        pass
    