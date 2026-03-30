import os, json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_community.vectorstores import Chroma
from app import MiniMaxEmbeddings

load_dotenv()
api_key = os.environ['MINIMAX_API_KEY']
os.environ['OPENAI_API_BASE'] = 'https://api.minimax.chat/v1'

embeddings = MiniMaxEmbeddings(api_key)
db = Chroma(persist_directory='./chroma_db_minimax', embedding_function=embeddings)

query = '帮我推荐一些除三星外其他品牌的冰箱素材，并说明亮点'
docs = db.max_marginal_relevance_search(query, k=8, fetch_k=20)

context_str = ''
for i, doc in enumerate(docs):
    context_str += f'\n--- 素材 {i+1} ---\n{doc.page_content}\n'

print('--- CONTEXT ---')
print(context_str)

prompt_template = """你是一个资深的家电/3C数码营销策略专家。请**严格且仅根据**以下我为你提供的【竞品素材库检索结果】（Context），回答用户的提问（Query）。

【极其重要的约束条件】：
1. 你的回答**绝对不能**脱离提供的 [检索到的素材信息] 进行凭空捏造（幻觉）。
2. **品类严格对齐（零容忍张冠李戴）**：
   - 在阅读每一条素材前，必须先识别用户提问的核心品类（如“冰箱”、“电视”、“洗衣机”、“空气炸锅”等）。
   - 严格对比素材内容中的【品类】字段。如果素材品类与用户提问品类不一致，必须**直接无视并彻底抛弃**该素材。
   - 绝对禁止任何形式的跨品类强行推理或联想（例如绝对不允许说：“虽然这是洗衣机的素材，但冰箱也可以借鉴...”）。
3. 如果过滤后没有任何与用户提问强相关的同品类素材，请明确且仅回复：“目前的素材库中没有抓取到该品类的相关数据，建议前往后台添加相关抓取任务”。
4. 回答时，必须明确引用具体是哪一款产品的素材（如：根据某某型号的文案...）。
5. **品牌中英文同义识别**：必须将同一个品牌的中英文名称视为完全等同（例如：“三星”与“Samsung”、“美的”与“Midea”、“海尔”与“Haier”等）。在分析和回答时，绝对不能将它们当成两个不同的品牌进行对比或声明找不到该品牌。

【相关素材过滤】：
在你回答的最后，必须新起一行，输出一个你认为真正解答了用户问题的素材编号列表，格式如下：
[相关素材编号]: 1, 2
如果没有相关的，输出：
[相关素材编号]: 无

[检索到的素材信息]
{context}

[用户的提问]
{query}

[你的专业分析与建议]
"""

prompt = PromptTemplate(input_variables=['context', 'query'], template=prompt_template)
llm = ChatOpenAI(temperature=0.7, model_name='abab6.5s-chat', openai_api_key=api_key, max_tokens=2048)
chain = prompt | llm
res = chain.invoke({'context': context_str, 'query': query})
print('--- AI RESPONSE ---')
print(res.content)
