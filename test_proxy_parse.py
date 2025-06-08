import asyncio
import logging
import re
import urllib.parse
from typing import Optional, Dict, List, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("ProxyFormatTest")

def analyze_proxy_format(proxy: str) -> Dict:
    """分析代理地址格式"""
    result = {
        "original": proxy,
        "valid": False,
        "protocol": None,
        "host": None,
        "port": None,
        "has_protocol": False,
        "has_port": False,
        "normalized": None,
        "suggestions": []
    }
    
    # 检查是否为空
    if not proxy or not proxy.strip():
        result["suggestions"].append("代理地址为空")
        return result
    
    # 去除空格
    proxy = proxy.strip()
    result["original"] = proxy
    
    # 检查协议
    if "://" in proxy:
        protocol, rest = proxy.split("://", 1)
        result["has_protocol"] = True
        result["protocol"] = protocol.lower()
        
        # 检查协议是否支持
        if protocol.lower() != "http":
            result["suggestions"].append(f"不支持的协议 '{protocol}'，应为 'http'")
    else:
        rest = proxy
        result["suggestions"].append("缺少协议前缀，应以 'http://' 开头")
    
    # 解析主机和端口
    if ":" in rest:
        host_part, port_part = rest.rsplit(":", 1)
        result["has_port"] = True
        
        # 验证主机
        result["host"] = host_part
        
        # 验证端口
        try:
            port = int(port_part)
            if 1 <= port <= 65535:
                result["port"] = port
            else:
                result["suggestions"].append(f"端口号 {port} 超出有效范围 (1-65535)")
        except ValueError:
            result["suggestions"].append(f"端口号 '{port_part}' 不是有效的数字")
    else:
        result["host"] = rest
        result["suggestions"].append("缺少端口号，应使用 'host:port' 格式")
    
    # 检查主机是否为有效的IP或域名
    if result["host"]:
        # 简单的IPv4检查
        ipv4_pattern = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')
        # 简单的域名检查
        domain_pattern = re.compile(r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$')
        
        if ipv4_pattern.match(result["host"]):
            # 验证IP地址的每个部分
            valid_ip = True
            for part in result["host"].split("."):
                if not (0 <= int(part) <= 255):
                    valid_ip = False
                    result["suggestions"].append(f"IP地址部分 '{part}' 超出有效范围 (0-255)")
                    break
            
            if valid_ip:
                # IP地址有效
                pass
        elif domain_pattern.match(result["host"]):
            # 域名格式有效
            pass
        else:
            result["suggestions"].append(f"主机名 '{result['host']}' 不是有效的IP地址或域名")
    
    # 生成标准化的代理地址
    if result["host"] and result["port"]:
        protocol = result["protocol"] or "http"
        result["normalized"] = f"{protocol}://{result['host']}:{result['port']}"
        
        # 如果没有明显错误，标记为有效
        if not result["suggestions"]:
            result["valid"] = True
    
    # 生成备选格式建议
    if result["host"] and result["port"] and result["protocol"] != "http":
        result["suggestions"].append(f"尝试 HTTP 格式: http://{result['host']}:{result['port']}")
    
    return result

async def test_proxy_connection(proxy: str, test_url: str = "https://www.baidu.com") -> Dict:
    """测试代理连接是否可用"""
    result = {
        "proxy": proxy,
        "success": False,
        "error": None,
        "status_code": None,
        "response_time": None,
        "test_url": test_url
    }
    
    try:
        import httpx
        import time
        
        logger.info(f"测试连接 {test_url} 使用代理: {proxy}")
        timeout = httpx.Timeout(10.0)
        
        # 根据协议类型设置代理
        if proxy.startswith("http://"):
            proxies = {"http://": proxy, "https://": proxy}
        else:
            # 默认使用http
            http_proxy = f"http://{proxy}"
            proxies = {"http://": http_proxy, "https://": http_proxy}
            logger.info(f"代理地址缺少协议前缀，已添加http://前缀: {http_proxy}")
        
        start_time = time.time()    
        async with httpx.AsyncClient(proxies=proxies, timeout=timeout) as client:
            response = await client.get(test_url)
            end_time = time.time()
            
            result["success"] = True
            result["status_code"] = response.status_code
            result["response_time"] = round((end_time - start_time) * 1000)  # 毫秒
            logger.info(f"连接测试成功，状态码: {response.status_code}, 响应时间: {result['response_time']}ms")
    except httpx.ConnectError as e:
        logger.error(f"连接错误: {e}")
        result["error"] = f"连接错误: {str(e)}"
    except httpx.ConnectTimeout as e:
        logger.error(f"连接超时: {e}")
        result["error"] = f"连接超时: {str(e)}"
    except httpx.ProxyError as e:
        logger.error(f"代理错误: {e}")
        result["error"] = f"代理错误: {str(e)}"
    except httpx.ReadTimeout as e:
        logger.error(f"读取超时: {e}")
        result["error"] = f"读取超时: {str(e)}"
    except Exception as e:
        logger.error(f"连接测试失败: {e}")
        result["error"] = str(e)
    
    return result

async def test_stream_proxy(proxy: str, platform: str = None, url: str = None) -> Dict:
    """测试代理对直播流解析的影响"""
    result = {
        "proxy": proxy,
        "success": False,
        "error": None,
        "platform": platform,
        "url": url,
        "stream_available": False
    }
    
    if not platform or not url:
        result["error"] = "缺少平台或URL参数"
        return result
    
    try:
        import streamget
        
        logger.info(f"测试直播流解析 - 平台: {platform}, URL: {url}, 代理: {proxy}")
        
        # 如果代理不是以http://开头，记录会自动添加前缀的信息
        if proxy and not proxy.startswith("http://"):
            logger.info(f"代理地址缺少http://前缀，将自动添加: http://{proxy}")
        
        # 根据平台选择合适的处理类
        if platform.lower() == "douyin":
            live_stream = streamget.DouyinLiveStream(proxy_addr=proxy)
            
            # 获取直播数据
            if "v.douyin.com" in url:
                json_data = await live_stream.fetch_app_stream_data(url=url)
            else:
                json_data = await live_stream.fetch_web_stream_data(url=url)
                
            # 获取直播流URL
            stream_data = await live_stream.fetch_stream_url(json_data, "OD")
            
            result["success"] = True
            result["stream_available"] = stream_data.is_live
            
            if stream_data.is_live:
                result["anchor_name"] = stream_data.anchor_name
                result["title"] = stream_data.title
                logger.info(f"直播流解析成功 - 主播: {stream_data.anchor_name}, 标题: {stream_data.title}")
            else:
                logger.info("直播间未开播")
                
        elif platform.lower() == "kuaishou":
            live_stream = streamget.KwaiLiveStream(proxy_addr=proxy)
            
            # 获取直播数据
            json_data = await live_stream.fetch_web_stream_data(url=url)
            
            # 获取直播流URL
            stream_data = await live_stream.fetch_stream_url(json_data, "OD")
            
            result["success"] = True
            result["stream_available"] = stream_data.is_live
            
            if stream_data.is_live:
                result["anchor_name"] = stream_data.anchor_name
                result["title"] = stream_data.title
                logger.info(f"直播流解析成功 - 主播: {stream_data.anchor_name}, 标题: {stream_data.title}")
            else:
                logger.info("直播间未开播")
        
        # 可以根据需要添加更多平台支持
                
        return result
    except Exception as e:
        logger.error(f"直播流解析测试失败: {e}")
        result["error"] = str(e)
        return result

async def test_utils_handle_proxy(proxy: str) -> Dict:
    """测试utils.py中的handle_proxy_addr函数"""
    result = {
        "original": proxy,
        "handled": None,
        "success": False,
        "error": None
    }
    
    try:
        # 尝试导入utils模块
        try:
            from app.utils.utils import handle_proxy_addr
            
            # 调用handle_proxy_addr函数
            result["handled"] = handle_proxy_addr(proxy)
            result["success"] = True
            
            # 检查处理结果
            if proxy and result["handled"] != proxy and not proxy.startswith("http://"):
                logger.info(f"代理地址被修改: {proxy} -> {result['handled']}")
            elif not proxy and result["handled"] is None:
                logger.info("空代理地址被正确处理为None")
            else:
                logger.info(f"代理地址未变: {proxy}")
                
        except ImportError:
            logger.error("无法导入app.utils.utils模块")
            result["error"] = "无法导入app.utils.utils模块"
            
    except Exception as e:
        logger.error(f"测试handle_proxy_addr函数时出错: {e}")
        result["error"] = str(e)
        
    return result

async def test_stream_manager_validate(proxy: str) -> Dict:
    """测试stream_manager.py中的validate_proxy_address方法"""
    result = {
        "original": proxy,
        "is_valid": False,
        "success": False,
        "error": None
    }
    
    try:
        # 尝试导入stream_manager模块
        try:
            import sys
            from app.core.stream_manager import LiveStreamRecorder
            
            # 创建一个简单的模拟App对象
            class MockApp:
                def __init__(self):
                    self.language_manager = MockLanguageManager()
                    self.page = MockPage()
                    self.settings = MockSettings()
                    
            class MockLanguageManager:
                def __init__(self):
                    self.language = {}
                def add_observer(self, observer):
                    pass
                    
            class MockPage:
                def run_task(self, *args, **kwargs):
                    pass
                    
            class MockSettings:
                def __init__(self):
                    self.user_config = {}
                    self.accounts_config = {}
                    self.cookies_config = {}
            
            class MockRecording:
                def __init__(self):
                    self.streamer_name = "测试主播"
                    
            # 创建LiveStreamRecorder实例
            app = MockApp()
            recording = MockRecording()
            recording_info = {"platform_key": "test", "platform": "test", "live_url": "https://example.com"}
            
            recorder = LiveStreamRecorder(app, recording, recording_info)
            
            # 调用validate_proxy_address方法
            result["is_valid"] = recorder.validate_proxy_address(proxy)
            result["success"] = True
            
            logger.info(f"代理地址验证结果: {'有效' if result['is_valid'] else '无效'}")
                
        except ImportError as e:
            logger.error(f"无法导入stream_manager模块: {e}")
            result["error"] = f"无法导入stream_manager模块: {str(e)}"
            
    except Exception as e:
        logger.error(f"测试validate_proxy_address方法时出错: {e}")
        result["error"] = str(e)
        
    return result

async def test_all_proxy_formats(original_proxy: str, test_sites: List[str] = None, test_stream: bool = False, 
                                platform: str = None, stream_url: str = None):
    """测试多种代理格式"""
    # 默认测试站点
    if not test_sites:
        test_sites = ["https://www.baidu.com", "https://www.google.com"]
    
    # 分析代理格式
    analysis = analyze_proxy_format(original_proxy)
    logger.info(f"\n代理地址分析结果: {analysis['original']}")
    logger.info(f"格式有效: {analysis['valid']}")
    
    if analysis["suggestions"]:
        logger.info("\n格式建议:")
        for suggestion in analysis["suggestions"]:
            logger.info(f"  - {suggestion}")
    
    # 尝试测试StreamCap内部处理函数
    try:
        logger.info("\n=== 测试app.utils.utils.handle_proxy_addr函数 ===")
        handle_result = await test_utils_handle_proxy(original_proxy)
        
        if handle_result["success"]:
            logger.info(f"处理结果: {original_proxy} -> {handle_result['handled']}")
        else:
            logger.warning(f"处理测试失败: {handle_result['error']}")
    except Exception as e:
        logger.error(f"测试handle_proxy_addr时出错: {e}")
    
    try:
        logger.info("\n=== 测试app.core.stream_manager.validate_proxy_address方法 ===")
        validate_result = await test_stream_manager_validate(original_proxy)
        
        if validate_result["success"]:
            logger.info(f"验证结果: {original_proxy} -> {'有效' if validate_result['is_valid'] else '无效'}")
        else:
            logger.warning(f"验证测试失败: {validate_result['error']}")
    except Exception as e:
        logger.error(f"测试validate_proxy_address时出错: {e}")
    
    # 尝试连接测试
    if analysis["host"] and analysis["port"]:
        # 准备要测试的代理格式
        test_formats = []
        
        # 总是测试标准化格式
        if analysis["normalized"]:
            test_formats.append(analysis["normalized"])
        
        # 添加http协议格式
        host_port = f"{analysis['host']}:{analysis['port']}"
        test_formats.append(f"http://{host_port}")
        
        # 移除重复
        test_formats = list(set(test_formats))
        
        # 测试所有格式和站点组合
        connection_results = []
        
        for proxy_format in test_formats:
            logger.info(f"\n=== 测试代理格式: {proxy_format} ===")
            
            for site in test_sites:
                logger.info(f"正在测试站点: {site}")
                result = await test_proxy_connection(proxy_format, site)
                connection_results.append(result)
        
        # 直播流测试
        stream_results = []
        if test_stream and platform and stream_url:
            logger.info(f"\n=== 测试直播流解析 ===")
            # 只用有效的代理格式测试直播流
            valid_formats = [r["proxy"] for r in connection_results if r["success"]]
            
            if not valid_formats:
                logger.warning("没有找到可用的代理格式，无法测试直播流解析")
            else:
                for proxy_format in valid_formats:
                    logger.info(f"使用代理 {proxy_format} 测试 {platform} 平台直播流")
                    result = await test_stream_proxy(proxy_format, platform, stream_url)
                    stream_results.append(result)
        
        # 显示结果摘要
        logger.info("\n=== 连接测试结果摘要 ===")
        for result in connection_results:
            if result["success"]:
                logger.info(f"✅ {result['proxy']} -> {result['test_url']} - 状态码: {result['status_code']}, 响应时间: {result['response_time']}ms")
            else:
                logger.info(f"❌ {result['proxy']} -> {result['test_url']} - 错误: {result['error']}")
        
        # 显示直播流测试结果
        if stream_results:
            logger.info("\n=== 直播流测试结果摘要 ===")
            for result in stream_results:
                if result["success"] and result["stream_available"]:
                    logger.info(f"✅ {result['proxy']} -> {result['platform']} - 直播流可用")
                elif result["success"]:
                    logger.info(f"⚠️ {result['proxy']} -> {result['platform']} - 解析成功但直播未开播")
                else:
                    logger.info(f"❌ {result['proxy']} -> {result['platform']} - 错误: {result['error']}")
    else:
        logger.warning("缺少主机或端口信息，无法执行连接测试")
    
    return {
        "analysis": analysis
    }

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="增强版代理格式分析和测试工具")
    parser.add_argument("proxy", help="要测试的代理地址")
    parser.add_argument("--google", action="store_true", help="包括测试Google连接")
    parser.add_argument("--stream", action="store_true", help="测试直播流解析")
    parser.add_argument("--platform", choices=["douyin", "kuaishou"], help="直播平台")
    parser.add_argument("--url", help="直播URL")
    
    args = parser.parse_args()
    
    test_sites = ["https://www.baidu.com"]
    if args.google:
        test_sites.append("https://www.google.com")
    
    await test_all_proxy_formats(
        args.proxy, 
        test_sites=test_sites, 
        test_stream=args.stream,
        platform=args.platform,
        stream_url=args.url
    )

if __name__ == "__main__":
    asyncio.run(main()) 