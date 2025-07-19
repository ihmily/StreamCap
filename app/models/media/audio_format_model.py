class AudioFormat:
    WAV = "WAV"
    MP3 = "MP3"
    WMA = "WMA"
    M4A = "M4A"
    AAC = "AAC"

    @classmethod
    def get_formats(cls):
        """Get all properties of the AudioFormat class"""
        attributes = cls.__dict__
        audio_formats = [value for name, value in attributes.items() if name.isupper()]
        return audio_formats
