import schedule
import time
import subprocess
import logging
import sys
import os
import json

# 配置日志记录
# 确保日志文件保存在同一目录下
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline.log")
config_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduler_config.json")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def get_scheduler_config():
    try:
        if os.path.exists(config_file_path):
            with open(config_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"无法读取配置文件: {e}")
    return {"frequency": "每天", "run_time": "02:00"}

def schedule_job(frequency, run_time, job_func):
    """根据频率和时间动态注册任务"""
    if frequency == "每天":
        return schedule.every().day.at(run_time).do(job_func)
    elif frequency == "每 3 天":
        return schedule.every(3).days.at(run_time).do(job_func)
    elif frequency == "每周一":
        return schedule.every().monday.at(run_time).do(job_func)
    elif frequency == "每月 1 号":
        # schedule 库原生不支持每月特定日期，用个折中方案或每天检查
        # 这里简化处理：每天在指定时间检查今天是不是 1 号
        def run_if_first_of_month():
            from datetime import datetime
            if datetime.now().day == 1:
                job_func()
        return schedule.every().day.at(run_time).do(run_if_first_of_month)
    else:
        # Fallback
        return schedule.every().day.at(run_time).do(job_func)

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
    config = get_scheduler_config()
    schedule_freq = config.get("frequency", "每天")
    schedule_time = config.get("run_time", "02:00")
    
    # 记录当前注册的任务
    current_job = schedule_job(schedule_freq, schedule_time, run_pipeline)
    
    logging.info(f"📅 调度器已启动。任务将【{schedule_freq}】于 {schedule_time} 自动运行。")
    logging.info("按 Ctrl+C 可以停止调度器。")
    
    # 保持脚本持续运行，定期检查是否有待执行的任务
    try:
        last_check_freq = schedule_freq
        last_check_time = schedule_time
        while True:
            # 每分钟检查一次配置是否有更新
            new_config = get_scheduler_config()
            new_freq = new_config.get("frequency", "每天")
            new_time = new_config.get("run_time", "02:00")
            
            # 如果业务人员在后台修改了频率或时间，动态重新注册任务
            if new_freq != last_check_freq or new_time != last_check_time:
                logging.info(f"🔄 检测到定时任务配置变更，更新执行计划为: 【{new_freq}】 {new_time}")
                schedule.cancel_job(current_job)
                current_job = schedule_job(new_freq, new_time, run_pipeline)
                last_check_freq = new_freq
                last_check_time = new_time
                
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        logging.info("🛑 调度器已手动停止。")

if __name__ == "__main__":
    main()
