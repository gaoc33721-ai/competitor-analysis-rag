import schedule
import time
import subprocess
import logging
import sys
import os

# 配置日志记录
# 确保日志文件保存在同一目录下
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def run_pipeline():
    logging.info("==================================================")
    logging.info("🚀 开始执行定时任务：运行 pipeline.py")
    start_time = time.time()
    
    # 获取 pipeline.py 的绝对路径，确保 subprocess 能够找到它
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pipeline_path = os.path.join(script_dir, "pipeline.py")
    
    try:
        # 使用 subprocess 运行 pipeline.py
        result = subprocess.run(
            [sys.executable, pipeline_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        execution_time = time.time() - start_time
        logging.info("✅ 任务执行成功！")
        logging.info(f"⏱️ 任务耗时: {execution_time:.2f} 秒")
        
        # 记录 pipeline 的输出
        if result.stdout:
            logging.info(f"任务标准输出:\n{result.stdout.strip()}")
            
    except subprocess.CalledProcessError as e:
        execution_time = time.time() - start_time
        logging.error("❌ 任务执行失败！")
        logging.error(f"⏱️ 失败前耗时: {execution_time:.2f} 秒")
        logging.error(f"错误输出 (stderr):\n{e.stderr.strip()}")
        if e.stdout:
            logging.error(f"标准输出 (stdout):\n{e.stdout.strip()}")
    except Exception as e:
        execution_time = time.time() - start_time
        logging.error(f"❌ 发生未预期的错误: {str(e)}")
        logging.error(f"⏱️ 失败前耗时: {execution_time:.2f} 秒")

def main():
    # 设定每天凌晨 02:00 运行一次
    schedule_time = "02:00"
    schedule.every().day.at(schedule_time).do(run_pipeline)
    
    logging.info(f"📅 调度器已启动。任务将于每天 {schedule_time} 自动运行。")
    logging.info("按 Ctrl+C 可以停止调度器。")
    
    # 保持脚本持续运行，定期检查是否有待执行的任务
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        logging.info("🛑 调度器已手动停止。")

if __name__ == "__main__":
    main()
