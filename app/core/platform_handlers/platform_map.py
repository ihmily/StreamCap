# 平台中英文映射表及工具方法
platform_map = {
    "douyin": {"zh": "抖音直播", "en": "Douyin"},
    "tiktok": {"zh": "TikTok直播", "en": "TikTok"},
    "kuaishou": {"zh": "快手直播", "en": "Kuaishou"},
    "huya": {"zh": "虎牙直播", "en": "Huya"},
    "douyu": {"zh": "斗鱼直播", "en": "Douyu"},
    "yy": {"zh": "YY直播", "en": "YY"},
    "bilibili": {"zh": "B站直播", "en": "Bilibili"},
    "xiaohongshu": {"zh": "小红书直播", "en": "Xiaohongshu"},
    "xhs": {"zh": "小红书直播", "en": "XHS"},
    "bigo": {"zh": "Bigo直播", "en": "Bigo"},
    "blued": {"zh": "Blued直播", "en": "Blued"},
    "soop": {"zh": "SOOP", "en": "SOOP"},
    "netease": {"zh": "网易CC直播", "en": "Netease CC"},
    "qiandurebo": {"zh": "千度热播", "en": "Qiandurebo"},
    "pandalive": {"zh": "PandaTV", "en": "PandaTV"},
    "maoerfm": {"zh": "猫耳FM直播", "en": "MaoerFM"},
    "winktv": {"zh": "WinkTV", "en": "WinkTV"},
    "flextv": {"zh": "FlexTV", "en": "FlexTV"},
    "look": {"zh": "Look直播", "en": "Look Live"},
    "popkontv": {"zh": "PopkonTV", "en": "PopkonTV"},
    "twitcasting": {"zh": "TwitCasting", "en": "TwitCasting"},
    "baidu": {"zh": "百度直播", "en": "Baidu Live"},
    "weibo": {"zh": "微博直播", "en": "Weibo Live"},
    "kugou": {"zh": "酷狗直播", "en": "Kugou Live"},
    "twitch": {"zh": "TwitchTV", "en": "TwitchTV"},
    "liveme": {"zh": "LiveMe", "en": "LiveMe"},
    "huajiao": {"zh": "花椒直播", "en": "Huajiao Live"},
    "liuxing": {"zh": "流星直播", "en": "Liuxing"},
    "showroom": {"zh": "ShowRoom", "en": "ShowRoom"},
    "acfun": {"zh": "Acfun", "en": "Acfun"},
    "changliao": {"zh": "畅聊直播", "en": "Changliao"},
    "yingbo": {"zh": "音播直播", "en": "Yinbo"},
    "inke": {"zh": "映客直播", "en": "Inke"},
    "zhihu": {"zh": "知乎直播", "en": "Zhihu"},
    "chzzk": {"zh": "CHZZK", "en": "CHZZK"},
    "haixiu": {"zh": "嗨秀直播", "en": "Haixiu Live"},
    "vvxq": {"zh": "VV星球", "en": "VVXQ"},
    "17live": {"zh": "17Live", "en": "17Live"},
    "lang": {"zh": "浪Live", "en": "Lang Live"},
    "piaopiao": {"zh": "漂漂直播", "en": "PiaoPiao Live"},
    "6room": {"zh": "六间房直播", "en": "6Room"},
    "lehai": {"zh": "乐嗨直播", "en": "Lehai"},
    "catshow": {"zh": "花猫直播", "en": "Catshow"},
    "shopee": {"zh": "Shopee", "en": "Shopee"},
    "youtube": {"zh": "Youtube", "en": "Youtube"},
    "taobao": {"zh": "淘宝直播", "en": "Taobao"},
    "jd": {"zh": "京东直播", "en": "JD"},
    "faceit": {"zh": "faceit", "en": "faceit"},
}

def get_platform_display_name(key, lang="zh"):
    """
    根据平台key和语言返回平台显示名。
    :param key: 平台key
    :param lang: 语言代码（zh/en）
    :return: 平台显示名
    """
    if key in platform_map:
        return platform_map[key].get(lang[:2], key)
    return key 