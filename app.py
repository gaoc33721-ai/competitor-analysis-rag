import streamlit as st
import json
import os
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence

# Load environment variables
load_dotenv()

# Initialize page
st.set_page_config(page_title="竞品素材智能分析 MVP", layout="wide", page_icon="🎯")
st.title("🎯 竞品素材智能监控与分析系统 (MVP)")
st.markdown("本系统演示了基于 **RAG (检索增强生成)** 的智能营销素材问答与推荐。核心能力：自动提取竞品高优素材 -> AI 标签化存储 -> 自然语言语义检索。")

# Sidebar config (Removed API Key input, only keep test cases)
with st.sidebar:
    st.markdown("**测试用例参考（基于最新抓取数据）：**\n"
                "- 对比一下目前库里 TCL 电视和三星冰箱在文案卖点上有什么不同的侧重？\n"
                "- 给我看下 LG 洗衣机的产品图，并分析它的目标人群是谁？\n"
                "- 针对追求画质和游戏体验的用户，TCL电视的文案是怎么写的？")

# Get API key from environment
minimax_api_key = os.environ.get("MINIMAX_API_KEY")

if not minimax_api_key or minimax_api_key == "your_minimax_api_key_here":
    st.error("⚠️ 系统管理员尚未配置 MINIMAX_API_KEY。请在项目根目录的 .env 文件中进行配置。")
    st.stop()

# --- Custom MiniMax Embeddings ---
from typing import List
from langchain_core.embeddings import Embeddings
import requests

class MiniMaxEmbeddings(Embeddings):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.minimax.chat/v1/embeddings"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def embed_documents(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        # MiniMax expects an array of strings in 'texts' parameter for its native API
        # The 'type' parameter is required for embo-01: "db" for document embedding, "query" for user queries
        payload = {
            "model": "embo-01",
            "texts": texts,
            "type": "query" if is_query else "db"
        }
        response = requests.post(self.api_url, headers=self.headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Check for MiniMax specific error format
        if "base_resp" in data and data["base_resp"]["status_code"] != 0:
            raise ValueError(f"MiniMax API Error: {data['base_resp']['status_msg']}")
            
        # Parse the vectors from response
        # MiniMax native format returns vectors in 'vectors' array
        if "vectors" in data:
            return data["vectors"]
        # Fallback to OpenAI format if they changed it
        elif "data" in data:
            return [item["embedding"] for item in data["data"]]
        else:
            raise ValueError(f"Unexpected response format from MiniMax: {data}")

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text], is_query=True)[0]

# --- Initialize DB and Models ---
@st.cache_resource(show_spinner=False, hash_funcs={str: str})
def init_system(api_key: str):
    # Use MiniMax OpenAI-compatible endpoint
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_API_BASE"] = "https://api.minimax.chat/v1"
    
    # Using Custom MiniMax Embeddings instead of OpenAI wrapper
    embeddings = MiniMaxEmbeddings(api_key=api_key)
    persist_directory = "./chroma_db_minimax"
    
    # Load mock data
    with open("mock_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # 为保证数据彻底干净，如果检测到本地 JSON 数量和 ChromaDB 数量差异过大，或者为了清理历史脏数据，
    # 我们最好在这里实现一个彻底重置 ChromaDB 的逻辑，以 mock_data.json 为准。
    # 这里通过检查 ChromaDB 里的 ID 是否在 mock_data 中存在来决定是否需要重置。
    current_valid_ids = set([item['id'] for item in data])
    
    try:
        vectordb = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        existing_docs = vectordb.get()
        existing_ids = set(existing_docs['ids']) if existing_docs and 'ids' in existing_docs else set()
        
        # 检查是否有脏数据（在 Chroma 中但不在 JSON 中）
        dirty_ids = existing_ids - current_valid_ids
        if dirty_ids:
            print(f"Found {len(dirty_ids)} dirty/old records in ChromaDB. Deleting them...")
            vectordb.delete(ids=list(dirty_ids))
            existing_ids = existing_ids - dirty_ids
            
    except Exception as e:
        print(f"Error accessing ChromaDB, will create new: {e}")
        vectordb = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        existing_ids = set()

    # Prepare new documents that aren't in DB yet
    texts = []
    metadatas = []
    ids_to_add = []
    
    for item in data:
        doc_id = item['id']
        if doc_id in existing_ids:
            continue
            
        # Create a rich text representation for the vector to understand
        # Note: category is inside metadata dict
        category = item.get('metadata', {}).get('category', '未知')
        content = f"渠道: {item.get('channel', '未知')}\n品牌: {item['brand']}\n品类: {category}\n标题: {item['title']}\n文案: {item['original_copy']}\nAI标签: {', '.join(item['ai_tags'])}\nAI分析: {item['ai_analysis']}"
        texts.append(content)
        
        # ChromaDB cannot handle complex metadata (like dicts or nested lists)
        safe_meta = {}
        for key, value in item.items():
            if isinstance(value, (dict, list)):
                safe_meta[key] = json.dumps(value, ensure_ascii=False)
            else:
                safe_meta[key] = value
        metadatas.append(safe_meta)
        ids_to_add.append(doc_id)
        
    # Add new documents to DB if there are any
    if texts:
        print(f"Adding {len(texts)} new documents to ChromaDB...")
        vectordb.add_texts(
            texts=texts,
            metadatas=metadatas,
            ids=ids_to_add
        )
        
    return vectordb, data

with st.spinner("正在初始化大语言模型和向量数据库..."):
    try:
        vectordb, mock_data = init_system(minimax_api_key)
        # Use MiniMax Text-01 (M2.5/M2.7 generation) model via their OpenAI-compatible endpoint
        # The latest text models in MiniMax are typically accessed via 'abab6.5s-chat'
        # Increased max_tokens to ensure complete responses for marketing suggestions
        llm = ChatOpenAI(
            temperature=0.7, 
            model_name="abab6.5s-chat", 
            openai_api_key=minimax_api_key, 
            openai_api_base="https://api.minimax.chat/v1",
            max_tokens=2048
        )
    except Exception as e:
        st.error(f"初始化失败，请检查 API Key 是否有效或网络是否畅通。错误信息：{e}")
        st.stop()

# --- Chat UI ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "您好！我是您的智能营销素材助手。目前素材库已接入 **亚马逊美国站的主流竞品门店产品素材** 的全量数据分析。请告诉我您的需求！"}]

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "images" in msg and msg["images"]:
            cols = st.columns(len(msg["images"]))
            for idx, img_info in enumerate(msg["images"]):
                with cols[idx % len(cols)]:
                    st.image(img_info["url"], caption=img_info["caption"], use_container_width=True)
                    if img_info.get("source_url") and img_info["source_url"] != "#":
                        st.markdown(f"[🔗 查看原始页面来源]({img_info['source_url']})")

# User input
if user_query := st.chat_input("例如：我想推一款针对职场新人的产品，有什么素材参考？"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    # Assistant response
    with st.chat_message("assistant"):
        with st.spinner("🔍 正在检索素材库并生成策略分析..."):
            try:
                # 1. Retrieve documents
                # 使用最大边际相关性(MMR)检索，提高检索结果的多样性，防止被某个品牌(如三星/LG)霸榜
                # 增大 fetch_k 和 k，确保能覆盖到像 Midea 这种数量较少但符合条件的素材
                retrieved_docs = vectordb.max_marginal_relevance_search(
                    user_query, 
                    k=15, 
                    fetch_k=50,
                    lambda_mult=0.5 # 0.5 是相关性与多样性的平衡
                )
                
                # Prepare context and images
                context_str = ""
                images_to_show = []
                seen_image_urls = set() # 用于在前端展示时根据 URL 去重
                
                for i, doc in enumerate(retrieved_docs):
                    meta = doc.metadata
                    context_str += f"\n--- 素材 {i+1} ---\n{doc.page_content}\n"
                    
                    # Ensure metadata is correctly parsed since Chroma stringifies nested dicts
                    category_name = "Unknown"
                    try:
                        if 'metadata' in meta:
                            if isinstance(meta['metadata'], str):
                                import json
                                parsed_meta = json.loads(meta['metadata'])
                            else:
                                parsed_meta = meta['metadata']
                            category_name = parsed_meta.get('category', 'Unknown')
                    except:
                        pass

                    # Extract basic info
                    img_url = meta.get("image_url", "https://via.placeholder.com/800x600?text=No+Image")
                    
                    # 避免在UI中展示完全一样的重复图片
                    if img_url not in seen_image_urls:
                        seen_image_urls.add(img_url)
                        images_to_show.append({
                            "url": img_url,
                            "caption": f"{meta.get('brand', '')} {category_name} - {meta.get('title', '')[:25]}...",
                            "source_url": meta.get("source_url", "#")
                        })

                # 2. Generate response using LLM
                # 增强 Prompt，要求模型在回答时返回一个它认为真正相关的素材 ID 列表
                # 融入业务人员的《竞品展示调研》标准进行评判
                prompt = PromptTemplate(
                    input_variables=["context", "query"],
                    template="""你是一个资深的家电/3C数码营销策略专家。请**严格且仅根据**以下我为你提供的【竞品素材库检索结果】（Context），回答用户的提问（Query）。
                    
                    【极其重要的约束条件】：
                    1. 你的回答**绝对不能**脱离提供的 [检索到的素材信息] 进行凭空捏造（幻觉）。
                    2. **品类严格对齐（零容忍张冠李戴）**：
                       - 在阅读每一条素材前，必须先识别用户提问的核心品类（如“冰箱”、“电视”、“洗衣机”、“空气炸锅”等）。
                       - 严格对比素材内容中的【品类】字段。注意：素材中的品类可能是英文（如 Refrigerator 对应 冰箱，Washing Machine 对应 洗衣机，TV 对应 电视），请准确进行中英文品类匹配。
                       - 如果素材品类与用户提问品类不一致（例如用户问冰箱，素材是 Washing Machine 或 TV），必须**直接无视并彻底抛弃**该素材。
                       - 绝对禁止任何形式的跨品类强行推理或联想。
                       - **绝对禁止**在回答中提及、列出或分析那些被抛弃的素材（例如，不要为了说明“没有LG冰箱”而去列出LG洗衣机，也不要解释为什么抛弃它们，直接当它们不存在，连提都不要提）。
                    3. 如果过滤后没有任何与用户提问强相关的同品类素材，请明确且仅回复：“目前的素材库中没有抓取到该品类的相关数据，建议前往后台添加相关抓取任务”。
                    4. 回答时，必须明确引用具体是哪一款产品的素材（如：根据某某型号的文案...）。
                    5. **品牌中英文同义识别**：必须将同一个品牌的中英文名称视为完全等同（例如：“三星”与“Samsung”、“美的”与“Midea”、“海尔”与“Haier”等）。在分析和回答时，绝对不能将它们当成两个不同的品牌进行对比或声明找不到该品牌。
                    6. **负向查询处理**：如果用户要求“除XX品牌外”或“不要XX品牌”，你必须在回答中彻底排除该品牌的任何素材，只分析和展示剩下的其他品牌素材。
                    7. **回答精简原则**：不要在开头把所有相关素材机械地罗列一遍（不要写“根据提供的信息，我们有以下...”这种废话）。直接切入正题，给出你推荐的产品素材，并深度分析它的亮点和适用场景。
                    8. **关注视觉素材表现**：在介绍亮点时，不要只重复产品本身的功能参数（如“容量大”、“制冷快”），你必须**重点分析该素材在视觉呈现和电商文案排版上的优点**（例如“主图使用了直观的对比”、“文案采用了场景化代入”等），让业务人员知道这张“图/文”为什么值得参考。
                    
                    【优质素材的业务评价标准】：
                    当你在提炼素材的优秀之处时，请参考以下业务团队沉淀的“优质素材特征”，如果素材中包含以下亮点，请重点指出：
                    - **直观的规模/尺寸对比**（例如：与身高对比、用“一台顶三台”等拆解容积）。
                    - **功能/技术可视化**（例如：主图中加入制冷范围、防水产品加入水元素、透明视窗敲击拟声词、动态内部构造拆解）。
                    - **场景化与互动性**（例如：展示室内室外双场景、小家电充当家居摆件、在同一画面直观展示大小）。
                    - **辅助决策与信任感**（例如：主图带保修信息、对比表格突出优势、Q&A和KOC评价引导、安装测量指南）。
                    
                    【相关素材过滤】：
                    在你回答的最后，必须新起一行，输出一个你认为真正解答了用户问题的素材编号列表，格式如下（如果没有则填无）：
                    [相关素材编号]: 1, 2
                    
                    [检索到的素材信息]
                    {context}
                    
                    [用户的提问]
                    {query}
                    
                    [你的专业分析与建议]
                    """
                )
                
                chain = prompt | llm
                response = chain.invoke({"context": context_str, "query": user_query})
                answer = response.content
                
                # 3. 后处理：根据 LLM 的判断过滤掉不相关的图片
                filtered_images = []
                import re
                
                # 兼容大模型可能输出的不同格式，如 [相关素材编号]: 4 或 [相关素材编号]:4，甚至是 [相关素材编号]: 4, 12
                # 提取所有的数字，只要有数字，就把它作为候选
                # 注意避免提取到空或无
                match = re.search(r'\[相关素材编号\]:\s*([0-9,\s]+)', answer)
                if match:
                    indices_str = match.group(1)
                    # 只有当里面确实包含数字时才处理
                    if any(char.isdigit() for char in indices_str):
                        valid_indices = [int(x.strip()) - 1 for x in indices_str.split(',') if x.strip().isdigit()]
                        for idx in valid_indices:
                            if 0 <= idx < len(images_to_show):
                                filtered_images.append(images_to_show[idx])
                
                # 移除回答中给程序看的特殊标记
                display_answer = re.sub(r'\[相关素材编号\].*', '', answer, flags=re.DOTALL).strip()
                
                # Display text
                st.markdown(display_answer)
                
                # Display images (only the relevant ones filtered by LLM)
                if filtered_images:
                    # 再次通过URL去重，防止大模型输出了重复的编号或者指向了重复的URL
                    unique_filtered_images = []
                    final_seen_urls = set()
                    for img in filtered_images:
                        if img["url"] not in final_seen_urls:
                            final_seen_urls.add(img["url"])
                            unique_filtered_images.append(img)
                            
                    st.markdown("**优秀竞品素材参考：**")
                    cols = st.columns(len(unique_filtered_images))
                    for idx, img_info in enumerate(unique_filtered_images):
                        with cols[idx % len(cols)]:
                            st.image(img_info["url"], caption=img_info["caption"], use_container_width=True)
                            if img_info.get("source_url") and img_info["source_url"] != "#":
                                st.markdown(f"[🔗 查看原始页面来源]({img_info['source_url']})")
                
                # Save to history
                # 修复：存入历史记录的图片也必须是经过过滤的图片，而不是所有召回的图片
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "images": unique_filtered_images if filtered_images else []
                })
                
            except Exception as e:
                error_msg = f"处理失败，可能由于网络原因或 API 额度限制。错误详情：{e}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})