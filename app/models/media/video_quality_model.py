class VideoQuality:
    OD = "OD"
    UHD = "UHD"
    HD = "HD"
    SD = "SD"
    LD = "LD"

    @classmethod
    def get_qualities(cls):
        """Get all properties of the VideoQuality class"""
        attributes = cls.__dict__
        video_qualities = [value for name, value in attributes.items() if name.isupper()]
        return video_qualities
