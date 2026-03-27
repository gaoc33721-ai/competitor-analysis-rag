import streamlit as st
import json
import os
import subprocess
from datetime import datetime
import pandas as pd

# 页面配置
st.set_page_config(page_title="素材系统 - 管理后台", layout="wide", page_icon="⚙️")
st.title("⚙️ 竞品素材监控系统 - 管理后台")
st.markdown("轻量级系统运行状态监控与数据管理平台。")

# --- 辅助函数 ---
def load_data_stats():
    data_file = "mock_data.json"
    if not os.path.exists(data_file):
        return None
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"无法读取数据文件: {e}")
        return None

def load_logs(lines=50):
    log_file = "pipeline.log"
    if not os.path.exists(log_file):
        return "暂无日志文件。"
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    except Exception as e:
        return f"读取日志失败: {e}"

# --- 布局 ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📊 素材库数据概览")
    data = load_data_stats()
    
    if data:
        # 数据统计指标
        total_items = len(data)
        
        # 过滤掉明显的无效品牌，动态统计所有有效品牌
        invalid_brands = {"Unknown", "True Fresh", "Affresh", "None", ""}
        
        brands = set()
        categories = set()
        
        for item in data:
            brand = item.get('brand', 'Unknown')
            # 如果品牌不在黑名单中，就加入统计
            if brand and brand not in invalid_brands:
                brands.add(brand)
                
            # category 在结构中可能位于外层，也可能位于 metadata 内
            category = item.get('category')
            if not category and 'metadata' in item and isinstance(item['metadata'], dict):
                category = item['metadata'].get('category')
            
            if category:
                categories.add(category)
                
        brands_count = len(brands)
        categories_count = len(categories)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("总入库素材数", total_items)
        m2.metric("覆盖核心品牌数", brands_count)
        m3.metric("覆盖品类数", categories_count)
        
        # 数据明细表格
        st.markdown("**最新入库素材明细**")
        
        # 提取 category 并重命名为 line 用于展示
        for item in data:
            category = item.get('category')
            if not category and 'metadata' in item and isinstance(item['metadata'], dict):
                category = item['metadata'].get('category', 'Unknown')
            item['line'] = category
            
        df = pd.DataFrame(data)
        if not df.empty:
            # 只展示关键列以便于查看，在 brand 后显示 line
            display_cols = ['id', 'brand', 'line', 'title']
            available_cols = [c for c in display_cols if c in df.columns]
            st.dataframe(df[available_cols], use_container_width=True)
    else:
        st.info("当前素材库为空，请先运行数据抓取流水线。")

with col2:
    st.subheader("🛠️ 系统控制台")
    
    st.markdown("**常规全量更新**")
    st.markdown("此操作将拉起爬虫自动发现并更新 TCL、Samsung、LG 的产品。")
    if st.button("▶️ 运行常规流水线", type="primary"):
        with st.spinner("流水线运行中，请勿关闭页面..."):
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                
                result = subprocess.run(
                    ["python", "pipeline.py"],
                    capture_output=True,
                    text=True,
                    check=True,
                    encoding="utf-8",
                    env=env
                )
                st.success("✅ 流水线执行成功！数据已更新。")
                st.balloons()
                st.info("请点击右上角刷新页面以查看最新数据概览。")
            except subprocess.CalledProcessError as e:
                st.error("❌ 流水线执行失败！")
                with st.expander("查看错误详情"):
                    st.text(e.stderr)
            except Exception as e:
                st.error(f"❌ 发生未知错误: {str(e)}")

    st.markdown("---")
    st.markdown("**🎯 手工定向抓取 (添加新素材)**")
    st.markdown("业务人员可在此手工指定 ASIN 或关键词进行定向抓取分析。")
    
    fetch_mode = st.radio("选择定向抓取方式：", ["按特定 ASIN", "按搜索关键词"])
    
    if fetch_mode == "按特定 ASIN":
        custom_input = st.text_input("输入 ASIN (多个请用逗号分隔)", placeholder="例如: B0DXMT6YD4, B0C73HSQ8T")
        cmd_arg = "--asin"
    else:
        custom_input = st.text_input("输入搜索关键词 (多个请用逗号分隔)", placeholder="例如: Sony OLED TV, Hisense Laser TV")
        cmd_arg = "--query"
        
    if st.button("➕ 立即拉取并分析", type="secondary"):
        if not custom_input.strip():
            st.warning("⚠️ 请先输入要抓取的 ASIN 或关键词！")
        else:
            with st.spinner(f"正在定向拉取 {custom_input}，并调用 AI 分析，请耐心等待..."):
                try:
                    env = os.environ.copy()
                    env["PYTHONIOENCODING"] = "utf-8"
                    
                    result = subprocess.run(
                        ["python", "pipeline.py", cmd_arg, custom_input.strip()],
                        capture_output=True,
                        text=True,
                        check=True,
                        encoding="utf-8",
                        env=env
                    )
                    st.success(f"✅ 定向拉取成功！新的素材已入库。")
                    st.balloons()
                    st.info("请点击右上角刷新页面以查看最新数据概览。")
                except subprocess.CalledProcessError as e:
                    st.error("❌ 拉取失败，可能是 ASIN 无效或网络问题。")
                    with st.expander("查看错误详情"):
                        st.text(e.stderr)
                except Exception as e:
                    st.error(f"❌ 发生未知错误: {str(e)}")
                
    st.markdown("---")
    st.markdown("**调度器状态**")
    st.success("运行中 (假设由后台终端守护)")

# --- 底部日志区 ---
st.markdown("---")
st.subheader("📝 运行日志 (最近 50 行)")
st.text_area("pipeline.log", value=load_logs(), height=300, disabled=True)
