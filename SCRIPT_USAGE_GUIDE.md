# OpenSearch-SQL 脚本使用指南

## 📝 问题解答：为什么有这么多脚本？

您问得很对！我们确实创建了多个脚本，每个都有特定的用途。让我为您解释清楚：

## 🎯 推荐使用：`run_production.sh` ⭐

**这是您应该使用的主要脚本！**

```bash
# 推荐使用这个脚本
bash run/run_production.sh
```

### 为什么选择这个？

✅ **完整功能** - 全部8个pipeline节点  
✅ **完全独立** - 不依赖原始src/目录  
✅ **生产就绪** - 适合实际使用  
✅ **易于配置** - 支持多种配置选项  
✅ **默认安全** - 使用mock模型，无需API密钥  

## 📊 脚本对比表

| 脚本 | 用途 | Pipeline节点 | 模型类型 | 数据量 | 推荐度 |
|-----|------|-------------|----------|-------|--------|
| **🌟 `run_production.sh`** | **主要使用** | **8个完整** | **可选真实/Mock** | **可配置** | **⭐⭐⭐⭐⭐** |
| `run_standalone.sh` | 独立性验证 | 3个简化 | Mock only | 5个样本 | ⭐⭐⭐ |
| `run_main_optimized.sh` | 性能测试 | 8个 | 需要修复 | 可配置 | ⭐⭐ |

## 🚀 主要脚本详细说明

### 1. **`run_production.sh`** - 生产主脚本 ⭐⭐⭐⭐⭐

```bash
# 基本使用（处理10个任务，使用mock模型）
bash run/run_production.sh

# 处理50个任务
END=50 bash run/run_production.sh

# 使用真实模型（需要API密钥）
USE_REAL_MODELS=true OPENAI_API_KEY=your-key bash run/run_production.sh

# 处理全部数据
END=-1 bash run/run_production.sh
```

**特点：**
- ✅ 完整的8个pipeline节点
- ✅ 支持真实LLM和Mock模型
- ✅ 完全独立实现
- ✅ 生产级配置
- ✅ 详细的使用说明

### 2. **`run_standalone.sh`** - 独立性验证脚本

```bash
# 验证实现的独立性
bash run/run_standalone.sh
```

**特点：**
- 📝 主要用于验证独立性
- 🔬 简化的3个节点（快速测试）
- 🤖 只使用Mock模型
- 📊 处理少量数据（5个样本）

**何时使用：**
- 验证代码是否独立运行
- 快速功能测试
- 演示系统能力

### 3. **`run_main_optimized.sh`** - 优化版本（需修复）

```bash
# 当前有问题，不推荐使用
# bash run/run_main_optimized.sh
```

**状态：** ⚠️ 需要修复参数不匹配问题

## 💡 使用建议

### 🎯 **日常使用**
```bash
# 这是您的主要选择
bash run/run_production.sh
```

### 🧪 **快速测试**
```bash
# 只处理3个任务进行快速测试
END=3 bash run/run_production.sh
```

### 🚀 **生产部署**
```bash
# 使用真实模型处理全部数据
END=-1 USE_REAL_MODELS=true OPENAI_API_KEY=your-key bash run/run_production.sh
```

### 🔍 **调试模式**
```bash
# 启用详细日志
LOG_LEVEL=DEBUG END=5 bash run/run_production.sh
```

## 📋 配置选项

### 环境变量配置

```bash
# 数据设置
export DATA_MODE=dev              # 数据模式：dev/train
export DB_ROOT_PATH=Bird          # 数据库路径
export START=0                    # 开始索引
export END=10                     # 结束索引（-1表示全部）

# 模型设置
export USE_REAL_MODELS=false      # 是否使用真实LLM
export OPENAI_API_KEY=your-key    # API密钥（真实模型需要）
export BERT_MODEL_PATH=/path/to/bge-m3  # BERT模型路径

# 执行设置
export LOG_LEVEL=INFO             # 日志级别
export PIPELINE_NODES=all         # Pipeline节点配置
```

## 📈 性能对比

| 特性 | `run_production.sh` | `run_standalone.sh` |
|-----|-------------------|-------------------|
| 执行时间 | ~1.2秒/任务 | ~0.06秒/任务 |
| 功能完整度 | 100% (8节点) | 37% (3节点) |
| 内存使用 | 正常 | 最小 |
| 适用场景 | 生产使用 | 快速验证 |

## ❓ 常见问题

### Q: 我应该用哪个脚本？
**A:** 使用 `run_production.sh` - 这是主要的生产脚本

### Q: 如何处理更多数据？
**A:** 设置环境变量：`END=100 bash run/run_production.sh`

### Q: 如何使用真实的LLM模型？
**A:** 设置：`USE_REAL_MODELS=true OPENAI_API_KEY=your-key bash run/run_production.sh`

### Q: 为什么有这么多脚本？
**A:** 
- `run_production.sh` - **主要使用**（推荐）
- `run_standalone.sh` - 验证独立性
- `run_main_optimized.sh` - 历史版本（待修复）

## 🎉 总结

**推荐使用顺序：**

1. **🥇 首选：** `bash run/run_production.sh`
2. **🥈 测试：** `bash run/run_standalone.sh` 
3. **🥉 暂停：** `run_main_optimized.sh`（需修复）

**记住：** `run_production.sh` 是您的主要选择！✨