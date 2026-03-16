# 硬件数据手册解析归档 Agent (hw_datasheet_agent)

专为嵌入式硬件工程师打造的自动化工具，自动解析硬件芯片/模组数据手册、通信协议文档，生成结构化、标准化的技术归档文档，大幅降低硬件开发前期的文档整理成本。

## 核心功能

- **多格式文档兼容**：支持 PDF/DOCX/TXT 格式的硬件手册智能加载与解析
- **配置化管理**：API Key、输入输出路径、生成格式全配置化，无需修改代码
- **多格式归档输出**：支持 Markdown/Word/Excel/CSV 四种格式的归档文档生成
- **命令行增强**：支持通过命令行指定待解析文档，无需修改配置文件
- **长文档分块解析**：智能分块处理超长文档，支持 128k 上下文
- **Agent 架构**：独立 Agent 具有自主决策能力，支持异常重试、降级策略
- **深度数据审核**：结构完整性检查 + 表格格式检查 + 关键数据一致性校验
- **工程化能力**：完整的日志系统、进度可视化、异常处理兜底

## 快速开始

### 1. 环境准备

- Python 3.10 及以上版本
- 有效的 LLM API Key（支持 OpenAI/DeepSeek/通义千问/文心一言等）

### 2. 安装依赖

```bash
# 克隆仓库
git clone https://github.com/yzlx-zm/hardware_datasheet_read_agent.git
cd hardware_datasheet_read_agent

# 安装依赖库
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 配置文件

#### Windows (PowerShell)

```powershell
copy config.yaml.example config.yaml
```

#### Linux / macOS

```bash
cp config.yaml.example config.yaml
```

然后打开 `config.yaml`，填入你的 API Key，按需调整其他配置项。

### 4. 放入待解析文档

将需要解析的硬件数据手册或通信协议文档放入 `input_docs` 目录。

### 5. 运行使用

#### 基本用法

```bash
python hw_datasheet_agent.py
```

#### 高级用法

```bash
# 解析指定文档
python hw_datasheet_agent.py -f FS5708-PALM.pdf

# 自定义输出名称
python hw_datasheet_agent.py -f FS5708-PALM.pdf -o "FS5708掌静脉模组通信协议归档"

# 启用深度审核
python hw_datasheet_agent.py -f FS5708-PALM.pdf --enable-review

# 严格模式（审核不通过则终止）
python hw_datasheet_agent.py -f FS5708-PALM.pdf --strict-review

# 禁用审核
python hw_datasheet_agent.py -f FS5708-PALM.pdf --no-review
```

### 6. 查看结果

生成的归档文档会自动保存在 `output_archive` 目录下，按时间戳创建子文件夹：

```
output_archive/FS5708-PALM_通信协议归档_20260316_110136/
├── FS5708-PALM_通信协议归档.md          # Markdown 格式
├── FS5708-PALM_通信协议归档.docx        # Word 格式
├── FS5708-PALM_通信协议归档_指令集_错误码.xlsx  # Excel 格式
├── FS5708-PALM_通信协议归档_数据帧结构.csv     # CSV 格式
├── FS5708-PALM_通信协议归档_核心指令集.csv
├── FS5708-PALM_通信协议归档_错误码汇总.csv
├── audit_report.json                    # 审核报告（JSON）
└── audit_report.md                      # 审核报告（Markdown）
```

## 项目目录结构

```
hardware_datasheet_read_agent/
├── input_docs/          # 待解析的硬件文档存放目录
├── output_archive/      # 自动生成：归档文档输出目录
├── agent_logs/          # 自动生成：程序运行日志目录
├── agent/               # Agent 决策层
│   ├── state_manager.py # 状态管理器（保存原文、章节、LLM交互）
│   └── core_agent.py    # 核心 Agent 类
├── reviewer/            # 审核层
│   ├── data_reviewer.py # 审核器主类
│   ├── audit_report.py  # 审核报告生成
│   └── checks/          # 检查器
│       ├── structure_check.py       # 结构完整性检查
│       ├── table_check.py           # 表格格式检查
│       └── data_consistency_check.py # 数据一致性检查
├── config/              # 配置模块
│   └── constants.py     # 常量定义
├── config.yaml          # 私密配置文件（不上传 Git）
├── config.yaml.example  # 配置文件模板
├── hw_datasheet_agent.py# 主程序入口
├── requirements.txt     # 项目依赖库列表
└── README.md            # 项目说明文档
```

## 配置文件说明

`config.yaml` 核心配置项：

| 配置项                      | 说明                                                          |
|-----------------------------|---------------------------------------------------------------|
| `llm.api_key`               | LLM API Key                                                   |
| `llm.model_name`            | 模型名称，如 `gpt-4o-mini`/`deepseek-chat`                    |
| `llm.base_url`              | API 接口地址                                                  |
| `llm.temperature`           | 模型温度参数，硬件文档建议 0.05                               |
| `document.input_dir`        | 待解析文档的根目录，默认 `input_docs`                         |
| `document.input_file`       | 默认解析的文档文件名                                          |
| `document.output_base_name` | 输出文档基础名称，留空则自动根据输入文件名生成                |
| `document.output_formats`   | 输出格式列表，支持 `markdown`/`word`/`excel`/`csv`            |
| `archive.use_timestamp_folder` | 是否按时间戳创建归档子文件夹                             |
| `review.enabled`            | 是否启用深度审核                                              |
| `review.strict_mode`        | 严格模式：审核不通过则终止                                    |
| `review.checks.structure`   | 结构完整性检查（9章节是否完整）                               |
| `review.checks.table_format`| 表格格式检查（Markdown表格语法）                              |
| `review.checks.data_consistency` | 数据一致性检查（关键数据与原文比对）                     |

## 审核功能说明

审核功能会对生成的归档内容进行三维度检查：

| 检查项 | 说明 |
|--------|------|
| **结构完整性** | 检查9个固定章节是否完整、非空 |
| **表格格式** | 检查Markdown表格语法正确性 |
| **数据一致性** | 抽查波特率、帧头、寄存器地址等关键数据是否与原文一致 |

### 审核报告示例

```json
{
  "overall_score": 0.93,
  "passed": true,
  "check_results": [
    {"name": "structure", "passed": true, "score": 0.78},
    {"name": "table_format", "passed": true, "score": 1.0},
    {"name": "data_consistency", "passed": true, "score": 1.0}
  ]
}
```

## 归档文档结构

生成的归档文档遵循固定的9章节结构：

1. 文档概述
2. 物理层通信参数
3. 链路层数据帧结构（表格）
4. 核心指令集汇总（表格）
5. 校验算法定义
6. 模块全生命周期工作时序
7. 特殊时序与约束标记
8. 典型交互示例
9. 错误码汇总表（表格）

## 许可证

本项目仅供学习和开发使用，请勿用于商业用途。
