import requests
import json
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
API_KEY = os.environ.get("RAINFOREST_API_KEY")

def test_rainforest_api(asin="B0DXMT6YD4"):
    """
    使用 Rainforest API 获取真实的亚马逊商品数据。
    ASIN B0DXMT6YD4 对应的是用户指定的三星电视。
    """
    if not API_KEY or API_KEY == "your_rainforest_api_key_here":
        print("⚠️ 错误：未配置 RAINFOREST_API_KEY！请先在 .env 文件中填入您的免费 API Key。")
        return

    print(f"🔄 正在调用 Rainforest API 获取亚马逊商品 (ASIN: {asin}) 的真实数据...")
    
    # Rainforest API 的请求参数
    params = {
        "api_key": API_KEY,
        "type": "product",           # 获取商品详情页面
        "amazon_domain": "amazon.com", # 指定美国站
        "asin": asin                 # 商品的唯一识别码
    }

    try:
        # 发送 GET 请求
        response = requests.get("https://api.rainforestapi.com/request", params=params)
        response.raise_for_status()
        
        # 解析返回的 JSON 数据
        data = response.json()
        
        # 检查请求是否成功
        if data.get("request_info", {}).get("success") == False:
            print(f"❌ API 请求失败：{data.get('request_info', {}).get('message')}")
            return
            
        # 提取我们需要关注的字段
        product = data.get("product", {})
        
        print("\n✅ 成功获取真实数据！")
        print("-" * 50)
        print(f"🏷️ 品牌 (Brand): {product.get('brand')}")
        print(f"📌 标题 (Title): {product.get('title')}")
        
        # 提取特征描述 (Bullet Points) 作为文案
        feature_bullets = product.get("feature_bullets", [])
        copy = " ".join(feature_bullets) if feature_bullets else "无描述"
        print(f"📝 核心文案 (Copy) 前 100 字: {copy[:100]}...")
        
        # 提取主图
        main_image = product.get("main_image", {}).get("link")
        print(f"🖼️ 主图链接: {main_image}")
        
        # 提取评分和评论数
        rating = product.get("rating")
        ratings_total = product.get("ratings_total")
        print(f"⭐ 评分: {rating} ({ratings_total} 条评论)")
        
        print("-" * 50)
        print("💡 结论：API 调用成功！您可以将这个真实抓取的结构直接喂给 MiniMax 进行 AI 打标了。")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求出错: {e}")

if __name__ == "__main__":
    test_rainforest_api()