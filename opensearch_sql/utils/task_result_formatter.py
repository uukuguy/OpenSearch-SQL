"""
任务结果格式化器，用于清晰显示每个任务的完成状态。
"""
import json
from typing import Dict, Any, Optional
from opensearch_sql.utils.loguru_config import get_logger

logger = get_logger(__name__)


class TaskResultFormatter:
    """
    任务结果格式化器，用于美化显示SQL生成任务的完成结果。
    支持调试模式和简洁模式。
    """
    
    def __init__(self, max_sql_length: int = 200):
        """
        初始化格式化器。
        
        Args:
            max_sql_length: SQL显示的最大长度
        """
        self.max_sql_length = max_sql_length
        
    def format_task_completion(self, 
                              task_id: str,
                              question: str,
                              generated_sql: str = "",
                              ground_truth_sql: str = "",
                              execution_status: str = "unknown",
                              evaluation_results: Optional[Dict[str, Any]] = None,
                              processing_time: float = 0.0,
                              error_message: str = "") -> None:
        """
        格式化并显示任务完成结果。
        
        Args:
            task_id: 任务ID
            question: 问题内容
            generated_sql: 生成的SQL
            ground_truth_sql: 标准SQL
            execution_status: 执行状态
            evaluation_results: 评估结果
            processing_time: 处理时间
            error_message: 错误信息
        """
        # 任务结果始终详细显示（重要信息，不受verbose控制）
        # 创建结果分隔线
        separator = "=" * 80
        print(f"\n{separator}")
        print(f"任务完成: {task_id}")
        print(separator)
        
        # 显示问题
        print(f"📋 问题:")
        wrapped_question = self._wrap_text(question, 76)
        for line in wrapped_question:
            print(f"   {line}")
        print()
        
        # 显示生成的SQL
        print(f"🔧 生成的SQL:")
        if generated_sql:
            formatted_sql = self._format_sql(generated_sql)
            print(f"   {formatted_sql}")
        else:
            print("   ❌ 未生成SQL")
        print()
        
        # 显示Ground Truth SQL（如果有）
        if ground_truth_sql:
            print(f"✅ 标准SQL:")
            formatted_gt_sql = self._format_sql(ground_truth_sql)
            print(f"   {formatted_gt_sql}")
            print()
        
        # 显示执行状态
        status_icon = "✅" if execution_status == "success" else "❌" if execution_status == "failed" else "❓"
        status_text = {
            "success": "执行成功",
            "failed": "执行失败", 
            "unknown": "状态未知"
        }.get(execution_status, execution_status)
        
        print(f"🚀 执行状态: {status_icon} {status_text}")
        
        # 显示evaluation节点的验证结果
        if evaluation_results:
            print("📊 执行验证结果:")
            
            # 显示总体评分
            overall_score = evaluation_results.get("overall_score")
            if overall_score is not None:
                score_percentage = overall_score * 100 if overall_score <= 1 else overall_score
                if overall_score >= 0.8:
                    score_icon = "🟢"
                elif overall_score >= 0.5:
                    score_icon = "🟡"
                else:
                    score_icon = "🔴"
                print(f"   {score_icon} 总体评分: {score_percentage:.1f}%")
            
            # 显示评估摘要
            if "evaluation_summary" in evaluation_results:
                print(f"   📋 评估摘要: {evaluation_results['evaluation_summary']}")
            
            # 显示执行匹配结果
            execution_match = evaluation_results.get("execution_match", evaluation_results.get("exec_res"))
            if execution_match is not None:
                if execution_match == 1 or execution_match == True:
                    print("   🎯 执行结果: ✅ 与标准SQL结果一致")
                else:
                    print("   🎯 执行结果: ❌ 与标准SQL结果不一致")
                    if "exec_err" in evaluation_results:
                        print(f"      错误类型: {evaluation_results['exec_err']}")
            
            # 显示SQL执行结果对比
            predicted_result = evaluation_results.get("predicted_result")
            ground_truth_result = evaluation_results.get("ground_truth_result")
            
            if predicted_result or ground_truth_result:
                print("   📄 SQL执行结果对比:")
                
                if predicted_result:
                    self._display_sql_result("生成SQL", predicted_result)
                
                if ground_truth_result:
                    self._display_sql_result("标准SQL", ground_truth_result)
            
            # 显示语法评估
            if "syntax_evaluation" in evaluation_results:
                syntax_eval = evaluation_results["syntax_evaluation"]
                if isinstance(syntax_eval, dict):
                    syntax_correct = syntax_eval.get("syntax_correct", False)
                    syntax_icon = "✅" if syntax_correct else "❌"
                    print(f"   📝 语法检查: {syntax_icon} {'正确' if syntax_correct else '有误'}")
                    
                    if "issues" in syntax_eval and syntax_eval["issues"]:
                        print("      语法问题:")
                        for issue in syntax_eval["issues"][:3]:  # 最多显示3个问题
                            print(f"        - {issue}")
            
            # 显示其他重要指标
            other_important = {
                "execution_accuracy": "执行准确率",
                "f1_score": "F1分数",
                "precision": "精确率", 
                "recall": "召回率",
                "semantic_similarity": "语义相似度"
            }
            
            for metric, display_name in other_important.items():
                if metric in evaluation_results:
                    value = evaluation_results[metric]
                    if isinstance(value, (int, float)):
                        if value <= 1:
                            percentage = value * 100
                            print(f"   - {display_name}: {percentage:.1f}%")
                        else:
                            print(f"   - {display_name}: {value}")
            
            # 显示执行错误（如果有）
            if "error" in evaluation_results:
                print(f"   ⚠️  执行错误: {evaluation_results['error']}")
        
        # 显示处理时间
        time_str = f"{processing_time:.2f}秒" if processing_time < 60 else f"{processing_time/60:.1f}分钟"
        print(f"⏱️  处理时间: {time_str}")
        
        # 显示错误信息（如果有）
        if error_message:
            print(f"⚠️  错误信息:")
            wrapped_error = self._wrap_text(error_message, 76)
            for line in wrapped_error:
                print(f"   {line}")
        
        print(separator)
        
    def _format_sql(self, sql: str) -> str:
        """
        格式化SQL显示。
        
        Args:
            sql: SQL查询
            
        Returns:
            str: 格式化后的SQL
        """
        if not sql:
            return ""
            
        # 清理SQL
        sql = sql.strip()
        
        # 如果太长，进行截断
        if len(sql) > self.max_sql_length:
            sql = sql[:self.max_sql_length-3] + "..."
            
        # 基本格式化：替换多个空格为单个空格
        sql = " ".join(sql.split())
        
        return sql
        
    def _wrap_text(self, text: str, width: int = 80) -> list:
        """
        文本换行。
        
        Args:
            text: 要换行的文本
            width: 每行最大宽度
            
        Returns:
            list: 换行后的文本列表
        """
        if not text:
            return [""]
            
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line + " " + word) <= width:
                current_line = current_line + " " + word if current_line else word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
                
        if current_line:
            lines.append(current_line)
            
        return lines if lines else [""]
        
    def _display_sql_result(self, result_type: str, result_data):
        """
        显示SQL执行结果。
        
        Args:
            result_type: 结果类型（"生成SQL" 或 "标准SQL"）
            result_data: 结果数据
        """
        if not result_data:
            print(f"      {result_type}结果: 无数据")
            return
            
        # 处理不同格式的结果数据
        actual_result = None
        
        if isinstance(result_data, dict):
            # 尝试提取实际结果数据（支持多种格式）
            if 'result' in result_data:
                actual_result = result_data['result']
            elif 'RESULT' in result_data:  # DatabaseManager的validate_sql_query返回格式
                actual_result = result_data['RESULT']
            elif 'data' in result_data:
                actual_result = result_data['data']
            elif 'rows' in result_data:
                actual_result = result_data['rows']
            elif 'output' in result_data:
                actual_result = result_data['output']
            else:
                # 如果没有找到数据字段，检查是否包含错误
                if 'error' in result_data:
                    print(f"      {result_type}结果: 执行错误 - {result_data['error']}")
                    return
                elif 'STATUS' in result_data and result_data['STATUS'] == 'ERROR':
                    # DatabaseManager的错误格式
                    error_msg = result_data.get('RESULT', '未知错误')
                    print(f"      {result_type}结果: 执行错误 - {error_msg}")
                    return
                elif 'status' in result_data and result_data['status'] == 'error':
                    print(f"      {result_type}结果: 执行失败")
                    return
                else:
                    # 显示整个字典的简化版本，但过滤掉SQL字段
                    filtered_data = {k: v for k, v in result_data.items() 
                                   if k.lower() != 'sql' and not k.startswith('predicted_') and not k.startswith('ground_truth_')}
                    if filtered_data:
                        result_str = str(filtered_data)[:150]
                        if len(str(filtered_data)) > 150:
                            result_str += "..."
                        print(f"      {result_type}结果: {result_str}")
                        return
                    else:
                        print(f"      {result_type}结果: 数据格式不明确")
                        return
        elif isinstance(result_data, list):
            actual_result = result_data
        else:
            # 其他类型的数据
            result_str = str(result_data)[:100]
            if len(str(result_data)) > 100:
                result_str += "..."
            print(f"      {result_type}结果: {result_str}")
            return
            
        # 显示实际结果数据
        if actual_result is not None:
            if isinstance(actual_result, list):
                if len(actual_result) == 0:
                    print(f"      {result_type}结果: 0行数据 (空结果集)")
                else:
                    print(f"      {result_type}结果: {len(actual_result)}行数据")
                    
                    # 显示前几行数据
                    display_count = min(3, len(actual_result))
                    for i in range(display_count):
                        row = actual_result[i]
                        if isinstance(row, list) or isinstance(row, tuple):
                            # 处理列表或元组形式的行数据
                            row_str = ", ".join([str(cell) if cell is not None else "NULL" for cell in row])
                            print(f"        行{i+1}: [{row_str}]")
                        else:
                            # 处理其他格式的行数据
                            print(f"        行{i+1}: {row}")
                    
                    # 如果有更多行，显示省略信息
                    if len(actual_result) > 3:
                        print(f"        ... (还有{len(actual_result)-3}行)")
            else:
                # 非列表格式的结果
                result_str = str(actual_result)[:100]
                if len(str(actual_result)) > 100:
                    result_str += "..."
                print(f"      {result_type}结果: {result_str}")
        else:
            print(f"      {result_type}结果: 无法提取数据")
    
    def _format_compact_summary(self, task_id: str, execution_status: str, 
                              evaluation_results: Optional[Dict[str, Any]], 
                              processing_time: float, error_message: str):
        """
        格式化简洁的任务完成摘要（一行显示）。
        
        Args:
            task_id: 任务ID
            execution_status: 执行状态
            evaluation_results: 评估结果
            processing_time: 处理时间
            error_message: 错误信息
        """
        # 状态图标
        status_icon = "✅" if execution_status == "success" else "❌" if execution_status == "failed" else "❓"
        
        # 评分信息
        score_text = ""
        if evaluation_results and "overall_score" in evaluation_results:
            score = evaluation_results["overall_score"]
            score_percentage = score * 100 if score <= 1 else score
            if score >= 0.8:
                score_icon = "🟢"
            elif score >= 0.5:
                score_icon = "🟡"
            else:
                score_icon = "🔴"
            score_text = f" {score_icon}{score_percentage:.0f}%"
        
        # 时间信息
        time_str = f"{processing_time:.1f}s" if processing_time < 60 else f"{processing_time/60:.1f}m"
        
        # 错误信息（简化）
        error_text = ""
        if error_message and execution_status == "failed":
            if "syntax error" in error_message.lower():
                error_text = " (语法错误)"
            elif "column" in error_message.lower():
                error_text = " (字段错误)"
            elif "table" in error_message.lower():
                error_text = " (表错误)"
            else:
                error_text = " (执行错误)"
        
        # 一行摘要显示
        print(f"📋 {task_id}: {status_icon}{score_text} ({time_str}){error_text}")


class TaskResultLogger:
    """
    任务结果记录器，将结果写入结构化日志。
    """
    
    def __init__(self):
        """
        初始化记录器。
        任务结果始终详细显示。
        """
        self.formatter = TaskResultFormatter()
        
    def log_task_result(self, 
                       task_id: str,
                       question: str, 
                       generated_sql: str = "",
                       ground_truth_sql: str = "",
                       execution_status: str = "unknown",
                       evaluation_results: Optional[Dict[str, Any]] = None,
                       processing_time: float = 0.0,
                       error_message: str = ""):
        """
        记录任务结果到日志。
        
        Args:
            task_id: 任务ID
            question: 问题内容
            generated_sql: 生成的SQL
            ground_truth_sql: 标准SQL
            execution_status: 执行状态
            evaluation_results: 评估结果
            processing_time: 处理时间
            error_message: 错误信息
        """
        # 格式化显示结果
        self.formatter.format_task_completion(
            task_id=task_id,
            question=question,
            generated_sql=generated_sql,
            ground_truth_sql=ground_truth_sql,
            execution_status=execution_status,
            evaluation_results=evaluation_results,
            processing_time=processing_time,
            error_message=error_message
        )
        
        # 也记录到结构化日志
        result_summary = {
            "task_id": task_id,
            "execution_status": execution_status,
            "has_generated_sql": bool(generated_sql),
            "has_ground_truth": bool(ground_truth_sql),
            "processing_time": processing_time,
            "evaluation_results": evaluation_results or {}
        }
        
        logger.info(f"Task completed: {task_id}", extra={"task_result": result_summary})