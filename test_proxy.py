import asyncio
import argparse
import sys
import os
import logging
import traceback
from typing import Optional, Dict, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("ProxyTest")

try:
    import streamget
    from streamget import StreamData
except ImportError:
    logger.error("未安装streamget库，请先安装: pip install streamget")
    sys.exit(1)

async def test_proxy_connection(proxy: Optional[str] = None, test_url: str = "https://www.google.com") -> Dict:
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
        
        logger.info(f"测试连接 {test_url} 使用代理: {proxy or '无'}")
        proxies = None
        
        if proxy:
            # 处理代理
            if proxy.startswith("http://"):
                proxies = {"http://": proxy, "https://": proxy}
            else:
                # 无协议前缀的情况，默认添加http://前缀
                logger.warning(f"代理地址缺少协议前缀: {proxy}，将添加http://前缀")
                if ":" in proxy:  # 确保格式为IP:端口
                    http_proxy = f"http://{proxy}"
                    proxies = {"http://": http_proxy, "https://": http_proxy}
                    result["tried_protocol"] = http_proxy
                else:
                    # 纯IP无端口，无法使用
                    logger.error(f"代理地址格式无效，缺少端口: {proxy}")
                    result["error"] = "代理地址格式无效，缺少端口"
                    return result
        
        timeout = httpx.Timeout(10.0)
        
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
        logger.error(f"测试连接时发生未知错误: {e}")
        result["error"] = str(e)
    
    return result

async def test_douyin_live(url: str, proxy: Optional[str] = None) -> Dict:
    """测试抖音直播解析"""
    result = {
        "platform": "douyin",
        "url": url,
        "proxy": proxy,
        "success": False,
        "error": None,
        "is_live": False,
        "anchor_name": None,
        "title": None,
        "record_url": None
    }
    
    try:
        logger.info(f"测试抖音直播解析，URL: {url}, 代理: {proxy or '无'}")
        live_stream = streamget.DouyinLiveStream(proxy_addr=proxy)
        
        # 获取直播数据
        if "v.douyin.com" in url:
            json_data = await live_stream.fetch_app_stream_data(url=url)
        else:
            json_data = await live_stream.fetch_web_stream_data(url=url)
        
        # 检查json_data是否为字符串(错误响应)或None
        if json_data is None:
            logger.error("获取直播数据失败，返回None")
            result["error"] = "获取直播数据失败，返回None"
            return result
        elif isinstance(json_data, str):
            logger.error(f"获取直播数据失败，返回字符串: {json_data}")
            result["error"] = f"获取直播数据失败: {json_data}"
            return result
            
        # 获取直播流URL
        stream_data = await live_stream.fetch_stream_url(json_data, "OD")
        
        # 填充结果
        result["success"] = True
        result["is_live"] = stream_data.is_live
        result["anchor_name"] = stream_data.anchor_name
        result["title"] = stream_data.title
        
        if stream_data.is_live:
            result["record_url"] = stream_data.record_url
            logger.info(f"解析结果 - 主播: {stream_data.anchor_name}, 标题: {stream_data.title}")
            logger.info(f"录制URL: {stream_data.record_url}")
        else:
            logger.info(f"解析结果 - 主播: {stream_data.anchor_name}, 未开播")
    except Exception as e:
        error_msg = f"解析抖音直播失败: {e}"
        logger.error(error_msg)
        traceback.print_exc()
        result["error"] = error_msg
    
    return result

async def test_kuaishou_live(url: str, proxy: Optional[str] = None) -> Dict:
    """测试快手直播解析"""
    result = {
        "platform": "kuaishou",
        "url": url,
        "proxy": proxy,
        "success": False,
        "error": None,
        "is_live": False,
        "anchor_name": None,
        "title": None,
        "record_url": None
    }
    
    try:
        logger.info(f"测试快手直播解析，URL: {url}, 代理: {proxy or '无'}")
        live_stream = streamget.KwaiLiveStream(proxy_addr=proxy)
        
        # 获取直播数据
        json_data = await live_stream.fetch_web_stream_data(url=url)
        
        # 检查json_data是否为字符串(错误响应)或None
        if json_data is None:
            logger.error("获取直播数据失败，返回None")
            result["error"] = "获取直播数据失败，返回None"
            return result
        elif isinstance(json_data, str):
            logger.error(f"获取直播数据失败，返回字符串: {json_data}")
            result["error"] = f"获取直播数据失败: {json_data}"
            return result
            
        # 获取直播流URL
        stream_data = await live_stream.fetch_stream_url(json_data, "OD")
        
        # 填充结果
        result["success"] = True
        result["is_live"] = stream_data.is_live
        result["anchor_name"] = stream_data.anchor_name
        result["title"] = stream_data.title
        
        if stream_data.is_live:
            result["record_url"] = stream_data.record_url
            logger.info(f"解析结果 - 主播: {stream_data.anchor_name}, 标题: {stream_data.title}")
            logger.info(f"录制URL: {stream_data.record_url}")
        else:
            logger.info(f"解析结果 - 主播: {stream_data.anchor_name}, 未开播")
    except Exception as e:
        error_msg = f"解析快手直播失败: {e}"
        logger.error(error_msg)
        traceback.print_exc()
        result["error"] = error_msg
    
    return result

async def test_with_fallback(url: str, proxy: Optional[str] = None, platform: str = "douyin", test_fallback: bool = True) -> Dict:
    """使用代理测试，失败时尝试不使用代理"""
    # 首先测试与Google的连接
    proxy_connection = await test_proxy_connection(proxy)
    if not proxy_connection["success"]:
        logger.warning(f"代理连接测试失败: {proxy_connection['error']}")
    else:
        logger.info(f"代理连接测试成功: 响应时间 {proxy_connection['response_time']}ms")
    
    # 测试直播解析
    test_func = test_douyin_live if platform == "douyin" else test_kuaishou_live
    
    # 首先使用代理
    result = await test_func(url, proxy)
    
    # 如果失败且启用了回退，尝试不使用代理
    if not result["success"] and test_fallback and proxy:
        logger.warning(f"使用代理解析失败，尝试不使用代理")
        no_proxy_result = await test_func(url, None)
        
        # 比较结果
        if no_proxy_result["success"]:
            logger.info("不使用代理解析成功，这表明代理配置可能有问题")
            # 添加对比信息
            result["fallback_success"] = True
            result["fallback_result"] = no_proxy_result
        else:
            logger.info("使用和不使用代理都解析失败")
            result["fallback_success"] = False
    
    return result

async def main():
    parser = argparse.ArgumentParser(description="直播平台代理测试工具")
    parser.add_argument("--url", type=str, help="直播URL", required=True)
    parser.add_argument("--proxy", type=str, help="代理地址，如socks5://127.0.0.1:7897", default=None)
    parser.add_argument("--platform", type=str, choices=["douyin", "kuaishou"], help="平台类型", required=True)
    parser.add_argument("--no-fallback", action="store_true", help="禁用回退到无代理测试")
    
    args = parser.parse_args()
    
    # 运行测试
    result = await test_with_fallback(
        args.url, 
        args.proxy, 
        args.platform, 
        not args.no_fallback
    )
    
    # 打印最终结果摘要
    logger.info("\n=== 测试结果摘要 ===")
    if result["success"]:
        logger.info(f"平台: {result['platform']}")
        logger.info(f"URL: {result['url']}")
        logger.info(f"代理: {result['proxy'] or '无'}")
        logger.info(f"主播: {result['anchor_name']}")
        logger.info(f"标题: {result['title']}")
        logger.info(f"直播状态: {'正在直播' if result['is_live'] else '未开播'}")
        if result["is_live"]:
            logger.info(f"录制URL: {result['record_url']}")
        logger.info("测试成功完成")
    else:
        logger.error(f"测试失败: {result['error']}")
        
        if result.get("fallback_success"):
            logger.info("\n不使用代理可以成功解析，建议检查代理配置")
            fallback = result["fallback_result"]
            logger.info(f"无代理解析结果 - 主播: {fallback['anchor_name']}, "
                      f"{'正在直播' if fallback['is_live'] else '未开播'}")

if __name__ == "__main__":
    asyncio.run(main()) 