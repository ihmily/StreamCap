# 窗口和界面常量
# 默认窗口尺寸
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 890

# 屏幕分辨率适配比例
SCALE_2K = 1.5  # 2K屏幕(2560x1440)
SCALE_4K = 2.0  # 4K屏幕(3840x2160)

# 最小窗口宽度
MIN_WIDTH = 950

# 计算最小窗口高度，保持默认窗口宽高比
MIN_HEIGHT = int(MIN_WIDTH * DEFAULT_HEIGHT / DEFAULT_WIDTH)

# 窗口边距，避免窗口超出屏幕边界
WINDOW_MARGIN = 50 