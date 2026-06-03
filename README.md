# BioPipe Lite

轻量级生物信息学分析平台，基于 Flask 构建，提供差异表达分析、聚类分析、生存分析等功能，并自动生成可视化图表。


## 目录

- [系统架构](#系统架构)
- [功能模块](#功能模块)
- [技术栈](#技术栈)
- [安装与部署](#安装与部署)
- [配置说明](#配置说明)
- [数据库模型](#数据库模型)
- [接口定义](#接口定义)
- [分析模块 API](#分析模块-api)
- [输入数据格式](#输入数据格式)
- [项目结构](#项目结构)
- [注意事项](#注意事项)
- [License](#license)

---

## 系统架构

```
用户请求 → Flask App → 任务队列（threading） → 分析模块 → 结果输出
                ↓
            SQLite（任务元数据）
                ↓
            文件系统（上传文件 / 结果目录）
```

当前版本采用基于 `threading.Thread` 的后台任务执行机制。分析任务在独立线程中运行，通过线程锁保证 Matplotlib 绘图的线程安全。结果文件（CSV + PNG）持久化至 `static/results/task_{id}/` 目录，通过 Flask `send_from_directory` 提供下载。

---

## 功能模块

| 模块 | 说明 | 输出 |
|------|------|------|
| `differential` | 两组样本独立 t 检验 + Bonferroni 校正 | 火山图、差异基因列表 |
| `clustering` | K-Means / 层次聚类 + PCA 降维 | PCA 散点图、热图、树状图 |
| `survival` | Kaplan-Meier 曲线、Log-rank 检验、Cox 回归 | KM 曲线、Cox 摘要 |
| `gene_survival` | 按单个基因表达中位数分层后执行生存分析 | KM 曲线（高/低表达组） |

---

## 技术栈

- **Web 框架**: Flask 2.3.x, Flask-SQLAlchemy 3.0.x, Werkzeug
- **数据库**: SQLite（通过 SQLAlchemy ORM 操作）
- **科学计算**: NumPy, SciPy, Pandas
- **机器学习**: scikit-learn（StandardScaler, PCA, KMeans, AgglomerativeClustering）
- **生存分析**: lifelines（KaplanMeierFitter, CoxPHFitter, logrank_test）
- **可视化**: Matplotlib（Agg 后端）, Seaborn
- **WSGI 服务器**: Gunicorn

---

## 安装与部署

### 环境要求

- Python >= 3.9

### 安装步骤

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 生成测试数据（可选）
python generate_test_data.py

# 4. 启动服务
python app.py              # 开发模式，http://127.0.0.1:5000
gunicorn -w 4 -b 0.0.0.0:5000 app:app  # 生产模式
```

---

## 配置说明

配置集中定义于 `config.py` 的 `Config` 类中：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `SECRET_KEY` | str | `'dev-key-change-in-production'` | Flask 会话安全密钥，生产环境必须替换 |
| `SQLALCHEMY_DATABASE_URI` | str | `sqlite:///biopipe.db` | 数据库连接地址 |
| `SQLALCHEMY_TRACK_MODIFICATIONS` | bool | `False` | 关闭 SQLAlchemy 对象追踪，降低内存开销 |
| `UPLOAD_FOLDER` | str | `./uploads` | 用户上传文件存储目录 |
| `RESULT_FOLDER` | str | `./static/results` | 分析结果输出目录（需位于 static 下以便通过 Web 访问） |
| `MAX_CONTENT_LENGTH` | int | `16 * 1024 * 1024` | 最大上传文件大小，默认 16MB |
| `ALLOWED_EXTENSIONS` | set | `{'csv', 'tsv', 'txt'}` | 允许上传的文件扩展名 |

---

## 数据库模型

### `AnalysisTask`

存储分析任务的生命周期元数据。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK | 任务唯一标识 |
| `task_name` | String(100) | NOT NULL | 用户自定义任务名称 |
| `analysis_type` | String(50) | NOT NULL | 分析类型：`differential` / `clustering` / `survival` / `gene_survival` |
| `status` | String(20) | DEFAULT `'pending'` | 任务状态：`pending` / `running` / `completed` / `failed` |
| `created_at` | DateTime | DEFAULT `utcnow` | 创建时间 |
| `completed_at` | DateTime | NULLABLE | 完成时间 |
| `input_file` | String(200) | NOT NULL | 上传文件绝对路径 |
| `result_path` | String(200) | NULLABLE | 结果目录绝对路径 |
| `error_message` | Text | NULLABLE | 失败时的异常堆栈 |

---

## 接口定义

### Web 路由

| 路由 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 上传表单页 |
| `/upload` | POST | 接收文件上传，创建任务并启动后台分析线程 |
| `/tasks` | GET | 任务列表页 |
| `/tasks/<int:task_id>/delete` | POST | 删除指定任务，同时清理上传文件和结果目录 |
| `/result/<int:task_id>` | GET | 结果展示页（仅 `status='completed'` 可访问） |
| `/download/<int:task_id>/<path:filename>` | GET | 下载结果文件（CSV / PNG） |

### 上传接口参数

`POST /upload` 接收 `multipart/form-data`：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `file` | File | 是 | 数据文件，扩展名需在 `ALLOWED_EXTENSIONS` 中 |
| `task_name` | String | 是 | 任务名称 |
| `analysis_type` | String | 是 | 分析类型，四选一 |

### 文件类型检测

平台通过文件扩展名自动识别分隔符：

- `.csv` — 逗号分隔 `,`
- `.tsv` / `.txt` — 制表符分隔 `\t`

检测逻辑封装于 `analysis.read_dataframe(filepath)`，供所有分析模块统一调用。

---

## 分析模块 API

### `analysis.differential.run_differential_analysis`

```python
def run_differential_analysis(
    input_path: str,
    output_dir: str,
    group_col: str = 'group',
    control_label: str = 'control',
    treatment_label: str = 'treatment'
) -> dict
```

**参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `input_path` | str | — | 输入文件路径 |
| `output_dir` | str | — | 结果输出目录 |
| `group_col` | str | `'group'` | 分组列名 |
| `control_label` | str | `'control'` | 对照组标签 |
| `treatment_label` | str | `'treatment'` | 处理组标签 |

**返回**

```python
{
    'result_csv': str,      # 差异分析结果文件路径
    'plot_path': str,       # 火山图路径
    'n_significant': int,   # 显著差异基因数
    'total_genes': int      # 总基因数
}
```

**算法**

1. 按 `group_col` 拆分为对照组与处理组
2. 逐基因执行 `scipy.stats.ttest_ind`
3. 计算 `log2FoldChange = log2(treatment_mean + 1) - log2(control_mean + 1)`
4. Bonferroni 校正：`padj = min(pvalue * n_genes, 1.0)`
5. 显著性判定：`padj < 0.05` 且 `|log2FC| > 1`

---

### `analysis.clustering.run_clustering_analysis`

```python
def run_clustering_analysis(
    input_path: str,
    output_dir: str,
    n_clusters: int = 3,
    method: str = 'kmeans'
) -> dict
```

**参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `input_path` | str | — | 输入文件路径 |
| `output_dir` | str | — | 结果输出目录 |
| `n_clusters` | int | `3` | 聚类数目 |
| `method` | str | `'kmeans'` | 聚类方法：`kmeans` / `hierarchical` |

**返回**

```python
{
    'result_csv': str,                # 聚类分配表路径
    'plot_paths': dict,               # {'pca': ..., 'heatmap': ..., 'dendrogram': ...}
    'n_clusters': int,
    'cluster_sizes': dict,            # {cluster_id: count}
    'pca_variance_ratio': list,       # [PC1_var, PC2_var]
    'method': str
}
```

**算法**

1. 转置矩阵使行为样本、列为基因
2. `StandardScaler` 标准化
3. 聚类：`KMeans(n_init=10)` 或 `AgglomerativeClustering`
4. PCA 降维至 2 维用于可视化
5. 热图取 Top 50 高变异基因，按聚类标签排序

---

### `analysis.survival.run_survival_analysis`

```python
def run_survival_analysis(
    input_path: str,
    output_dir: str,
    time_col: str = 'time',
    event_col: str = 'event',
    group_col: str = 'group'
) -> dict
```

**参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `input_path` | str | — | 输入文件路径 |
| `output_dir` | str | — | 结果输出目录 |
| `time_col` | str | `'time'` | 生存时间列名 |
| `event_col` | str | `'event'` | 事件指示列名（1=事件，0=删失） |
| `group_col` | str | `'group'` | 分组列名 |

**返回**

```python
{
    'n_total': int,
    'n_events': int,
    'n_censored': int,
    'median_survival': float,
    'plot_paths': dict,            # {'km_overall': ..., 'km_group': ..., 'km_multi': ...}
    'logrank_pvalue': float,       # 仅两组时存在
    'cox_hr': float,               # 仅两组时存在
    'cox_pvalue': float,           # 仅两组时存在
    'summary_csv': str
}
```

**算法**

1. `KaplanMeierFitter` 拟合总体生存曲线
2. 若存在 `group_col` 且恰好两组：
   - 分别拟合各组 KM 曲线
   - `logrank_test` 检验组间差异
   - `CoxPHFitter` 拟合 Cox 比例风险模型
3. 若存在 `group_col` 且多组：仅绘制多条 KM 曲线

---

### `analysis.survival.run_gene_survival_analysis`

```python
def run_gene_survival_analysis(
    input_path: str,
    output_dir: str,
    gene_col: str,
    time_col: str = 'time',
    event_col: str = 'event',
    cutoff: str = 'median'
) -> dict
```

**参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `input_path` | str | — | 输入文件路径 |
| `output_dir` | str | — | 结果输出目录 |
| `gene_col` | str | — | 目标基因列名 |
| `time_col` | str | `'time'` | 生存时间列名 |
| `event_col` | str | `'event'` | 事件指示列名 |
| `cutoff` | str | `'median'` | 分层方式：`median` / `tertile` |

**流程**

1. 按 `gene_col` 中位值（或三分位数）将样本划分为 `High` / `Low`（或 `Low` / `Medium` / `High`）
2. 将分层结果写入 `expression_group` 列
3. 调用 `run_survival_analysis` 以 `expression_group` 作为分组变量执行标准生存分析

---

## 输入数据格式

### 差异表达分析

- **行**: 样本
- **列**: 基因表达值 + `group` 列
- **必需列**: `group`（取值为 `control` / `treatment`）

```
sample   gene1   gene2   gene3   ...   group
S001     2.3     5.1     0.2     ...   control
S002     3.1     4.8     1.1     ...   treatment
```

### 聚类分析

- **行**: 样本
- **列**: 基因表达值（纯数值矩阵）

```
sample   gene1   gene2   gene3   ...
S001     2.3     5.1     0.2     ...
S002     3.1     4.8     1.1     ...
```

### 生存分析

- **行**: 患者
- **必需列**: `time`（生存时间）、`event`（1=事件发生，0=删失）、`group`（分组标签）
- **可选列**: 基因表达等协变量

```
patient   time   event   group       gene1   gene2   ...
P001      365    1       high_risk   2.3     5.1     ...
P002      720    0       low_risk    3.1     4.8     ...
```

---

## 项目结构

```
biopipe-lite/
├── app.py                      # Flask 应用主入口，定义 Web 路由
├── config.py                   # 全局配置（数据库、上传目录、文件限制等）
├── models.py                   # SQLAlchemy ORM 模型定义
├── tasks.py                    # 后台任务调度与执行，含 Matplotlib 线程锁
├── requirements.txt            # Python 依赖清单
├── generate_test_data.py       # 测试数据生成脚本，支持 CSV / TSV 两种格式
├── analysis/                   # 分析算法模块
│   ├── __init__.py             # read_dataframe() — 根据扩展名自动识别分隔符
│   ├── differential.py         # 差异表达分析（t 检验 + Bonferroni + 火山图）
│   ├── clustering.py           # 聚类分析（K-Means / 层次聚类 + PCA + 热图）
│   └── survival.py             # 生存分析（KM 曲线 + Log-rank + Cox 回归）
├── templates/                  # Jinja2 HTML 模板
│   ├── upload.html             # 文件上传与分析类型选择页
│   ├── tasks.html              # 任务列表与删除操作页
│   └── result.html             # 结果摘要、图表展示与文件下载页
├── static/                     # 静态资源
│   ├── css/
│   ├── js/
│   └── results/                # 分析结果输出目录（task_N/ 子目录）
├── test_data/                  # 测试数据集
│   ├── *_test.csv
│   └── *_test.tsv
└── biopipe.db                  # SQLite 数据库文件
```

---

## 注意事项

1. **Matplotlib 线程安全**

   Matplotlib 的 Agg 后端并非线程安全。当多个分析任务并发执行时，可能在 `savefig()` 阶段触发内部异常。本系统在 `tasks.py` 中通过 `_analysis_lock`（`threading.Lock`）对分析函数调用进行加锁，确保绘图操作串行执行。

2. **结果文件路径**

   `RESULT_FOLDER` 必须位于 `static/` 目录下，以便结果图片通过 Flask `url_for('static', filename=...)` 直接提供 Web 访问。路径分隔符在 Windows 环境下已通过 `replace('\\', '/')` 处理。

3. **生产环境**

   - 必须将 `config.py` 中的 `SECRET_KEY` 替换为加密安全的随机字符串。
   - 开发服务器 `app.run(debug=True)` 仅用于本地调试，生产环境应使用 Gunicorn 等 WSGI 服务器。
   - 当前版本使用 `threading.Thread` 执行后台任务，生产环境建议替换为 Celery / RQ 等专用任务队列。

4. **文件大小限制**

   通过 `MAX_CONTENT_LENGTH` 控制，默认 16MB。超过此限制的上传请求将返回 413。

---

## License

MIT License
