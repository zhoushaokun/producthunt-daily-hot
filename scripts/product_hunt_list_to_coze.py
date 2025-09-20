import os
from cozepy import COZE_CN_BASE_URL, Coze, TokenAuth, Stream, WorkflowEvent, WorkflowEventType  # noqa
try:
    from dotenv import load_dotenv
    # 加载 .env 文件
    load_dotenv()
except ImportError:
    # 在 GitHub Actions 等环境中，环境变量已经设置好，不需要 dotenv
    print("dotenv 模块未安装，将直接使用环境变量")

import requests
from datetime import datetime, timedelta, timezone
import openai
from bs4 import BeautifulSoup
import pytz
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 创建 OpenAI 客户端实例
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    print("警告: 未设置 OPENAI_API_KEY 环境变量，将无法使用 OpenAI 服务")
    client = None
else:
    openai.api_key = api_key
    try:
        client = openai.Client(api_key=api_key, base_url="https://api.deepseek.com/v1")  # 新版本的客户端初始化方式
        print("成功初始化 OpenAI 客户端")
    except Exception as e:
        print(f"初始化 OpenAI 客户端失败: {e}")
        client = None

top_count = 6  # 获取前6名以防有些没有图片

class Product:
    def __init__(self, id: str, name: str, tagline: str, description: str, votesCount: int, createdAt: str, featuredAt: str, website: str, url: str, media=None, **kwargs):
        self.name = name
        self.tagline = tagline
        self.description = description
        self.votes_count = votesCount
        self.created_at = self.convert_to_beijing_time(createdAt)
        self.featured = "是" if featuredAt else "否"
        self.website = website
        self.url = url
        self.og_image_url = self.get_image_url_from_media(media)
        self.keyword = self.generate_keywords()
        self.translated_tagline = self.translate_text(self.tagline)
        self.trans_description = self.translate_text(self.description)

    def get_image_url_from_media(self, media):
        """从API返回的media字段中获取图片URL"""
        try:
            if media and isinstance(media, list) and len(media) > 0:
                # 优先使用第一张图片
                image_url = media[0].get('url', '')
                if image_url:
                    print(f"成功从API获取图片URL: {self.name}")
                    return image_url
            
            # 如果API没有返回图片，尝试使用备用方法
            print(f"API未返回图片，尝试使用备用方法: {self.name}")
            backup_url = self.fetch_og_image_url()
            if backup_url:
                print(f"使用备用方法获取图片URL成功: {self.name}")
                return backup_url
            else:
                print(f"无法获取图片URL: {self.name}")
                
            return ""
        except Exception as e:
            print(f"获取图片URL时出错: {self.name}, 错误: {e}")
            return ""

    def fetch_og_image_url(self) -> str:
        """获取产品的Open Graph图片URL（备用方法）"""
        try:
            response = requests.get(self.url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # 查找og:image meta标签
                og_image = soup.find("meta", property="og:image")
                if og_image:
                    return og_image["content"]
                # 备用:查找twitter:image meta标签
                twitter_image = soup.find("meta", name="twitter:image") 
                if twitter_image:
                    return twitter_image["content"]
            return ""
        except Exception as e:
            print(f"获取OG图片URL时出错: {self.name}, 错误: {e}")
            return ""

    def generate_keywords(self) -> str:
        """生成产品的关键词，显示在一行，用逗号分隔"""
        try:
            # 如果 OpenAI 客户端不可用，直接使用备用方法
            if client is None:
                print(f"OpenAI 客户端不可用，使用备用关键词生成方法: {self.name}")
                words = set((self.name + ", " + self.tagline).replace("&", ",").replace("|", ",").replace("-", ",").split(","))
                return ", ".join([word.strip() for word in words if word.strip()])
                
            prompt = f"根据以下内容生成适合的中文关键词，用英文逗号分隔开：\n\n产品名称：{self.name}\n\n标语：{self.tagline}\n\n描述：{self.description}"
            
            try:
                print(f"正在为 {self.name} 生成关键词...")
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "根据所提供的产品信息生成合适的中文关键词，关键词简单易懂，总数不超过5个关键词。关键词之间用逗号分隔。"},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=50,
                    temperature=0.7,
                )
                keywords = response.choices[0].message.content.strip()
                if ',' not in keywords:
                    keywords = ', '.join(keywords.split())
                print(f"成功为 {self.name} 生成关键词")
                return keywords
            except Exception as e:
                print(f"OpenAI API 调用失败，使用备用关键词生成方法: {e}")
                # 备用方法：从标题和标语中提取关键词
                words = set((self.name + ", " + self.tagline).replace("&", ",").replace("|", ",").replace("-", ",").split(","))
                return ", ".join([word.strip() for word in words if word.strip()])
        except Exception as e:
            print(f"关键词生成失败: {e}")
            return self.name  # 至少返回产品名称作为关键词

    def translate_text(self, text: str) -> str:
        """使用OpenAI翻译文本内容"""
        try:
            # 如果 OpenAI 客户端不可用，直接返回原文
            if client is None:
                print(f"OpenAI 客户端不可用，无法翻译: {self.name}")
                return text
                
            try:
                print(f"正在翻译 {self.name} 的内容...")
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "你是世界上最专业的翻译工具，擅长英文和中文互译。你是一位精通英文和中文的专业翻译，尤其擅长将IT公司黑话和专业词汇翻译成简洁易懂的地道表达。你的任务是将以下内容翻译成地道的中文，风格与科普杂志或日常对话相似。"},
                        {"role": "user", "content": text},
                    ],
                    max_tokens=500,
                    temperature=0.7,
                )
                translated_text = response.choices[0].message.content.strip()
                print(f"成功翻译 {self.name} 的内容")
                return translated_text
            except Exception as e:
                print(f"OpenAI API 翻译失败: {e}")
                # 如果 API 调用失败，返回原文
                return text
        except Exception as e:
            print(f"翻译过程中出错: {e}")
            return text

    def convert_to_beijing_time(self, utc_time_str: str) -> str:
        """将UTC时间转换为北京时间"""
        utc_time = datetime.strptime(utc_time_str, '%Y-%m-%dT%H:%M:%SZ')
        beijing_tz = pytz.timezone('Asia/Shanghai')
        beijing_time = utc_time.replace(tzinfo=pytz.utc).astimezone(beijing_tz)
        return beijing_time.strftime('%Y年%m月%d日 %p%I:%M (北京时间)')

    def to_markdown(self, rank: int) -> str:
        """返回产品数据的Markdown格式"""
        og_image_markdown = f"![{self.name}]({self.og_image_url})"
        return (
            f"## [{rank}. {self.name}]({self.url})\n"
            f"**标语**：{self.translated_tagline}\n"
            f"**介绍**：{self.translated_description}\n"
            f"**产品网站**: [立即访问]({self.website})\n"
            f"**Product Hunt**: [View on Product Hunt]({self.url})\n\n"
            f"{og_image_markdown}\n\n"
            f"**关键词**：{self.keyword}\n"
            f"**票数**: 🔺{self.votes_count}\n"
            f"**是否精选**：{self.featured}\n"
            f"**发布时间**：{self.created_at}\n\n"
            f"---\n\n"
        )

def get_producthunt_token():
    """获取 Product Hunt 访问令牌"""
    # 优先使用 PRODUCTHUNT_DEVELOPER_TOKEN 环境变量
    developer_token = os.getenv('PRODUCTHUNT_DEVELOPER_TOKEN')
    if developer_token:
        print("使用 PRODUCTHUNT_DEVELOPER_TOKEN 环境变量")
        return developer_token
    
    # 如果没有 developer token，尝试使用 client credentials 获取访问令牌
    client_id = os.getenv('PRODUCTHUNT_CLIENT_ID')
    client_secret = os.getenv('PRODUCTHUNT_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        raise Exception("Product Hunt client ID or client secret not found in environment variables")
    
    # 使用 client credentials 获取访问令牌
    token_url = "https://api.producthunt.com/v2/oauth/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    }
    
    try:
        response = requests.post(token_url, json=payload)
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token")
    except Exception as e:
        print(f"获取 Product Hunt 访问令牌时出错: {e}")
        raise Exception(f"Failed to get Product Hunt access token: {e}")

def fetch_product_hunt_data():
    """从Product Hunt获取前一天的Top 30数据"""
    token = get_producthunt_token()
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    date_str = yesterday.strftime('%Y-%m-%d')
    url = "https://api.producthunt.com/v2/api/graphql"
    
    # 添加更多请求头信息
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "DecohackBot/1.0 (https://decohack.com)",
        "Origin": "https://decohack.com",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Connection": "keep-alive"
    }

    # 设置重试策略
    retry_strategy = Retry(
        total=3,  # 最多重试3次
        backoff_factor=1,  # 重试间隔时间
        status_forcelist=[429, 500, 502, 503, 504]  # 需要重试的HTTP状态码
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)

    base_query = """
    {
      posts(order: VOTES, postedAfter: "%sT00:00:00Z", postedBefore: "%sT23:59:59Z", after: "%s") {
        nodes {
          id
          name
          tagline
          description
          votesCount
          createdAt
          featuredAt
          website
          url
          media {
            url
            type
            videoUrl
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """

    all_posts = []
    has_next_page = True
    cursor = ""

    while has_next_page and len(all_posts) < top_count:
        query = base_query % (date_str, date_str, cursor)
        try:
            response = session.post(url, headers=headers, json={"query": query})
            response.raise_for_status()  # 抛出非200状态码的异常
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            raise Exception(f"Failed to fetch data from Product Hunt: {e}")

        data = response.json()['data']['posts']
        posts = data['nodes']
        all_posts.extend(posts)

        has_next_page = data['pageInfo']['hasNextPage']
        cursor = data['pageInfo']['endCursor']

    # 只保留前30个产品
    return [Product(**post) for post in sorted(all_posts, key=lambda x: x['votesCount'], reverse=True)[:top_count]]

def fetch_mock_data():
    """生成模拟数据用于测试"""
    print("使用模拟数据进行测试...")
    mock_products = [
        {
            "id": "1",
            "name": "Venice",
            "tagline": "Private & censorship-resistant AI | Unlock unlimited intelligence",
            "description": "Venice is a private, censorship-resistant AI platform powered by open-source models and decentralized infrastructure. The app combines the benefits of decentralized blockchain technology with the power of generative AI.",
            "votesCount": 566,
            "createdAt": "2025-03-07T16:01:00Z",
            "featuredAt": "2025-03-07T16:01:00Z",
            "website": "https://www.producthunt.com/r/4D6Z6F7I3SXTGN",
            "url": "https://www.producthunt.com/posts/venice-3",
            "media": [
                {
                    "url": "https://ph-files.imgix.net/97baee49-6dda-47f5-8a47-91d2c56e1976.jpeg",
                    "type": "image",
                    "videoUrl": None
                }
            ]
        },
        # {
        #     "id": "2",
        #     "name": "Mistral OCR",
        #     "tagline": "Introducing the world's most powerful document understanding API",
        #     "description": "Introducing Mistral OCR—an advanced, lightweight optical character recognition model focused on speed, accuracy, and efficiency. Whether extracting text from images or digitizing documents, it delivers top-tier performance with ease.",
        #     "votesCount": 477,
        #     "createdAt": "2025-03-07T16:01:00Z",
        #     "featuredAt": "2025-03-07T16:01:00Z",
        #     "website": "https://www.producthunt.com/r/SPXNTAWQSVRLGH",
        #     "url": "https://www.producthunt.com/posts/mistral-ocr",
        #     "media": [
        #         {
        #             "url": "https://ph-files.imgix.net/4224517b-29e4-4944-98c9-2eee59374870.png",
        #             "type": "image",
        #             "videoUrl": None
        #         }
        #     ]
        # }
    ]
    return [Product(**product) for product in mock_products]


def post_products_coze(products, date_str):
    """生成Markdown内容并保存到data目录"""
    # 获取今天的日期并格式化
    today = datetime.now(timezone.utc)
    date_today = today.strftime('%Y-%m-%d')

    product_jsons = []
    for _, product in enumerate(products, top_count):
        print(product.name)
        product_jsons.append({
            "name": product.name,
            "tagline": product.tagline,
            "description": product.description,
            "votes_count": product.votes_count,
            "created_at": product.created_at,
            "featured": product.featured,
            "website": product.website,
            "url": product.url,
            "og_image_url": product.og_image_url,
            "keyword": product.keyword,
            "translated_tagline": product.translated_tagline,
            "trans_description": product.translated_description,
        })

    to_post_data = {
        "title": f"Product Hunt 每日精选 - {date_str}",
        "date": date_today,
        "description": f"这里是 {date_str} 在 Product Hunt 上的前 10 名产品。",
        "products": product_jsons
    }

    print(to_post_data)

    # Get an access_token through personal access token or oauth.
    coze_api_token = 'cztei_hafSUaei1g37O64GoYNUISyHdH0HB41Z6MRASKodWDPH9K97xm3fvFXcv4NqBtRjq'
    # The default access is api.coze.com, but if you need to access api.coze.cn,
    # please use base_url to configure the api endpoint to access
    coze_api_base = COZE_CN_BASE_URL


    # Init the Coze client through the access_token.
    coze = Coze(auth=TokenAuth(token=coze_api_token), base_url=coze_api_base)

    # Create a workflow instance in Coze, copy the last number from the web link as the workflow's ID.
    workflow_id = '7550337148278685738'
    def handle_workflow_iterator(stream: Stream[WorkflowEvent]):
        for event in stream:
            if event.event == WorkflowEventType.MESSAGE:
                print("got message", event.message)
            elif event.event == WorkflowEventType.ERROR:
                print("got error", event.error)
            elif event.event == WorkflowEventType.INTERRUPT:
                handle_workflow_iterator(
                    coze.workflows.runs.resume(
                        workflow_id=workflow_id,
                        event_id=event.interrupt.interrupt_data.event_id,
                        resume_data="hey",
                        interrupt_type=event.interrupt.interrupt_data.type,
                    )
                )
    handle_workflow_iterator(
        coze.workflows.runs.stream(
            workflow_id=workflow_id,
            parameters={"product_data": to_post_data}
        )
    )
    print(f"已上传到 coze 平台并进行发布！")


def main():
    # 获取昨天的日期并格式化
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    date_str = yesterday.strftime('%Y-%m-%d')

    try:
        # 尝试获取Product Hunt数据
        products = fetch_product_hunt_data()
    except Exception as e:
        print(f"获取Product Hunt数据失败: {e}")
        print("使用模拟数据继续...")
        products = fetch_mock_data()

    # 生成Markdown文件
    post_products_coze(products, date_str)

if __name__ == "__main__":
    main()