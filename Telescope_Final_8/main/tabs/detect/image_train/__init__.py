"""AI/ML Training Subsystem for Celestial Object Detection"""

from .core.detection_pipeline import ContinuousLearningPipeline
from .core.model_manager import ModelManager
from .core.config import DetectionConfig, config
from .training.learning_manager import LearningManager
from .training.training_worker import TrainingWorker
from .training.training_dialog import TrainingDialog
from .annotation.annotation_wizard import AnnotationWizard

__all__ = [
    'ContinuousLearningPipeline',
    'ModelManager',
    'DetectionConfig',
    'config',
    'LearningManager',
    'TrainingWorker',
    'TrainingDialog',
    'AnnotationWizard',
]