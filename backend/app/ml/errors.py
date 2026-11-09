class ModelNotAvailable(RuntimeError):
    """The model checkpoint is missing (not trained yet) or PyTorch is not installed."""


class UnreadableImage(ValueError):
    """The file could not be decoded as an image or PDF."""
