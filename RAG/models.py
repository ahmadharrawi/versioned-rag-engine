from sentence_transformers import SentenceTransformer, CrossEncoder
from config import settings

class ModelRegistry:
    _embedding_model: SentenceTransformer = None
    _nli_model: CrossEncoder = None

    @classmethod
    def get_embedding_model(cls) -> SentenceTransformer:
        """Loads and returns the SentenceTransformer embedding model as a singleton."""
        if cls._embedding_model is None:
            cls._embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        return cls._embedding_model

    @classmethod
    def get_nli_model(cls) -> CrossEncoder:
        """Loads and returns the CrossEncoder NLI model as a singleton."""
        if cls._nli_model is None:
            cls._nli_model = CrossEncoder(settings.NLI_MODEL_NAME)
        return cls._nli_model
