# 沃工单知识库系统 V3

## 系统简介

沃工单知识库系统是一个基于Redis Stack和智普大模型的智能客服问题分析与解决方案系统。系统支持多种文件格式的知识库管理，提供语义搜索和AI智能分析功能。

## 主要功能

### 1. 知识库管理
- **全量重建 (init)**：清空现有数据，重新导入所有文件
- **增量更新 (rebuild)**：只处理新增或修改的文件
- **实时统计 (stats)**：查看知识库文档数量和类型分布

### 2. 智能查询
- **语义搜索**：基于向量相似度的智能搜索
- **关键词搜索**：支持订单号、手机号精确查询
- **类型筛选**：按问题类型筛选查询结果
- **AI智能分析**：智普大模型提供问题分析和解决方案

### 3. 支持的文件格式
- 文本文件：.txt, .md
- Word文档：.doc, .docx
- Excel表格：.xlsx, .xls, .csv
- PDF文档：.pdf
- 图片文件：.png, .jpg, .jpeg（支持OCR识别）
- 数据文件：.json, .xml
- 思维导图：.xmind
- 压缩包：.zip

## 系统要求

### 1. 硬件要求
- CPU：4核及以上
- 内存：8GB及以上
- 硬盘：10GB可用空间

### 2. 软件要求
- Windows 10/11 或 Windows Server 2016+
- Python 3.8+
- Redis Stack 6.2+

## 安装步骤

### 1. 安装Python
访问 https://www.python.org/downloads/ 下载并安装Python 3.8或更高版本

### 2. 安装Redis Stack
1. 下载Redis Stack：https://redis.io/downloads/
2. 安装并启动Redis Stack服务
3. 默认配置：
   - host: 127.0.0.1
   - port: 6380
   - password: RedUssTest

### 3. 配置智普API Key（可选）
1. 访问 https://open.bigmodel.cn 注册账号
2. 获取API Key
3. 在系统中输入 `config` 命令配置API Key

## 启动方式

### 方式一：双击运行（推荐）
直接双击 `run.bat` 文件启动系统

### 方式二：命令行启动
```bash
python query_tool.py
```

## 使用说明

### 基本查询
直接输入问题描述，例如：
```
请输入问题 > 用户开户失败怎么办？
```

### 按类型查询
使用 `type:` 前缀指定问题类型：
```
请输入问题 > type:开户报错 用户办理失败
```

### 精确查询
输入订单号或手机号进行精确查询：
```
请输入问题 > 1325122268818964
```

### 常用命令
- `help` - 显示帮助信息
- `categories` - 显示问题分类列表
- `stats` - 显示知识库统计信息
- `config` - 配置智普API Key
- `init` - 初始化知识库（全量重建）
- `rebuild` - 重建知识库（增量更新）
- `quit` / `exit` - 退出系统

## 系统配置

### 配置文件位置
`config.ini`

### 主要配置项
```ini
[redis]
host = 127.0.0.1
port = 6380
password = RedUssTest

[zhipu]
api_key = your_api_key_here
model = glm-4-flash

[data]
data_dir = D:\工作文档\cbss2.0体验版\沃工单问题定位
```

## 问题分类

系统支持以下问题分类：
1. 开户报错
2. 套餐变更
3. 移机改号
4. 销户问题
5. 合约问题
6. 费用问题
7. 服务状态
8. 终端问题
9. 跨域业务
10. 实名认证
11. 副卡问题
12. 亲情业务
13. 产品受理
14. 系统报错
15. 其他问题

## 技术架构

### 核心技术
- **向量存储**：Redis Stack（RediSearch + RedisJSON）
- **文本向量化**：本地模型 text2vec-base-chinese
- **AI分析**：智谱AI大模型（GLM-4）
- **OCR识别**：RapidOCR / PaddleOCR / Tesseract

### 系统组件
- `query_tool.py` - 交互式查询工具
- `knowledge_base.py` - 知识库核心功能
- `vector_store.py` - 向量存储管理
- `file_parser.py` - 文件解析器
- `zhipu_llm.py` - 智普大模型接口
- `ocr_helper.py` - OCR识别辅助

## 故障排除

### 1. Redis连接失败
- 检查Redis Stack服务是否已启动
- 检查config.ini中的Redis配置是否正确

### 2. 模型加载失败
- 检查本地模型路径是否正确
- 确保模型文件完整

### 3. 智普API调用失败
- 检查API Key是否配置正确
- 检查网络连接是否正常

### 4. 文件解析失败
- 检查文件是否损坏
- 检查文件编码是否为UTF-8

## 更新日志

### V3.0
- 新增智普大模型AI分析功能
- 优化向量搜索算法
- 支持更多文件格式
- 改进OCR识别功能
- 新增增量更新机制
- 优化用户交互体验

## 联系方式

如有问题或建议，请联系系统管理员。

## 许可证

本系统仅供内部使用。
