class VideoFormat:
    TS = "TS"
    MP4 = "MP4"
    FLV = "FLV"
    MKV = "MKV"
    MOV = "MOV"

    @classmethod
    def get_formats(cls):
        """Get all properties of the VideoFormat class"""
        attributes = cls.__dict__
        video_formats = [value for name, value in attributes.items() if name.isupper()]
        return video_formats
