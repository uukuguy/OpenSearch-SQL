#!/usr/bin/env python3
"""
测试增强的进度条显示，包括已用时间和预估剩余时间。
"""
import time
import random
from src_optimized.utils.progress_tracker import ProgressTracker

def test_enhanced_progress():
    """测试增强的进度条显示。"""
    print("演示：增强的进度条 - 包含已用时间和预估剩余时间")
    print("=" * 80)
    print("\n新功能:")
    print("✅ 已用时间 (格式: XhYYmZZs)")
    print("✅ 预估剩余时间 (基于平均处理速度)")
    print("✅ 总计预估时间 (已用 + 剩余)")
    print("✅ 实时处理速度 (任务/分钟)")
    print("✅ 当前任务显示")
    print("✅ 中文界面优化")
    print("\n" + "=" * 80)
    
    # 模拟不同处理速度的任务
    total_tasks = 100
    tracker = ProgressTracker(total_tasks=total_tasks, has_ground_truth=True)
    
    print(f"\n开始处理 {total_tasks} 个任务...\n")
    
    # 模拟任务处理
    for i in range(total_tasks):
        # 模拟不同的处理时间
        if i < 10:
            # 开始时较慢
            sleep_time = random.uniform(0.3, 0.6)
        elif i < 50:
            # 中期稳定
            sleep_time = random.uniform(0.1, 0.3) 
        else:
            # 后期加速
            sleep_time = random.uniform(0.05, 0.2)
            
        time.sleep(sleep_time)
        
        # 生成示例数据
        task_id = f"database_{i//20}#query_{i}"
        
        # 模拟SQL生成
        sql_samples = [
            "SELECT name, age FROM users WHERE active = 1",
            "SELECT COUNT(*) FROM orders GROUP BY status",
            "SELECT p.name, c.name FROM products p JOIN categories c ON p.cat_id = c.id",
            "SELECT AVG(salary) FROM employees WHERE department = 'Engineering'",
            "SELECT DISTINCT city FROM customers ORDER BY city"
        ]
        sql = random.choice(sql_samples)
        
        # 模拟错误（偶尔出现）
        error = ""
        if random.random() < 0.1:  # 10%概率出错
            errors = [
                "table not found",
                "column reference ambiguous", 
                "syntax error near WHERE",
                ""
            ]
            error = random.choice(errors)
        
        # 模拟执行结果
        if error:
            status = "failed"
            is_exact = False
        else:
            status = "success"
            is_exact = random.random() > 0.7  # 30%精确匹配
            
        # 更新进度
        tracker.update(
            task_id=task_id,
            generated_sql=sql,
            execution_status=status,
            is_exact_match=is_exact,
            error_message=error
        )
        
        # 在某些节点暂停，让用户看清显示
        if i in [5, 20, 50]:
            time.sleep(1.5)
    
    # 显示最终结果
    tracker.finish()

def test_time_formatting():
    """测试时间格式化功能。"""
    print("\n\n测试时间格式化:")
    print("=" * 50)
    
    tracker = ProgressTracker(100, False)
    
    # 测试不同的时间格式
    test_times = [30, 90, 125, 3661, 7325]
    for seconds in test_times:
        formatted = tracker._format_time(seconds)
        print(f"{seconds:5d}秒 -> {formatted}")
    
    # 测试ETA解析
    print("\n测试ETA解析:")
    test_etas = ["30s", "5m 30s", "1h 15m", "2h 05m"]
    for eta in test_etas:
        parsed = tracker._parse_eta_to_seconds(eta)
        print(f"{eta:>8} -> {parsed:4d}秒")

if __name__ == "__main__":
    # 运行进度条演示
    test_enhanced_progress()
    
    # 测试时间格式化
    test_time_formatting()
    
    print("\n" + "=" * 80)
    print("增强的进度条特性:")
    print("🕐 精确的已用时间显示 (小时:分钟:秒)")
    print("⏳ 智能ETA预估 (基于滚动平均速度)")
    print("📊 总计时间预估 (已用 + 预估剩余)")
    print("⚡ 实时处理速度监控")
    print("🎯 清晰的任务状态显示")
    print("🌐 中文友好的界面")
    print("=" * 80)