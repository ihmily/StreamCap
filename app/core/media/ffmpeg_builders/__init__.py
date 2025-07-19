from typing import Any

from .audio import AACCommandBuilder, M4ACommandBuilder, MP3CommandBuilder, WAVCommandBuilder, WMACommandBuilder
from .video import FLVCommandBuilder, MKVCommandBuilder, MOVCommandBuilder, MP4CommandBuilder, TSCommandBuilder


def create_builder(format_type: str, *args: Any, **kwargs: Any) -> Any:
    """
    Creates and returns an instance of the appropriate CommandBuilder based on the format_type.

    :param format_type: Media file format (e.g., 'ts','mkv', 'mp4').
    :param args: Positional arguments passed to the CommandBuilder constructor.
    :param kwargs: Keyword arguments passed to the CommandBuilder constructor.
    :return: An instance of the corresponding CommandBuilder.
    :raises ValueError: If the provided format_type is not supported.
    """
    format_to_class = {
        "mkv": MKVCommandBuilder,
        "mp4": MP4CommandBuilder,
        "ts": TSCommandBuilder,
        "flv": FLVCommandBuilder,
        "mov": MOVCommandBuilder,
        "mp3": MP3CommandBuilder,
        "m4a": M4ACommandBuilder,
        "wav": WAVCommandBuilder,
        "aac": AACCommandBuilder,
        "wma": WMACommandBuilder,
    }
    builder_class = format_to_class.get(format_type.lower())
    if not builder_class:
        raise ValueError(f"Unsupported format: {format_type}")
    return builder_class(*args, **kwargs)
