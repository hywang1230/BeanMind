# 日志系统配置完成

## 问题描述
Docker 环境中日志没有写入文件，导致无法追踪问题和调试。

## 根本原因
项目中虽然使用了 Python 的 `logging` 模块，但没有配置日志处理器（handlers），导致：
1. 只有默认的控制台输出
2. 没有日志文件写入
3. 日志级别为默认的 WARNING，很多 INFO/DEBUG 日志被忽略

## 解决方案

### 1. 创建日志配置模块
**文件**: `backend/config/logging_config.py`

功能特性：
- ✅ **双输出**：同时输出到控制台和文件
- ✅ **带颜色的控制台输出**：不同日志级别使用不同颜色，易于区分
- ✅ **日志轮转**：单个日志文件最大 10MB，保留 5 个历史文件，避免磁盘占满
- ✅ **分离错误日志**：单独的 `error.log` 记录 ERROR 及以上级别
- ✅ **详细的文件日志**：包含时间、级别、模块、函数、行号等完整信息
- ✅ **简洁的控制台日志**：只显示时间、级别和消息，避免控制台混乱
- ✅ **第三方库日志降噪**：自动降低 uvicorn、fastapi、sqlalchemy 等库的日志级别

### 2. 更新配置文件
**文件**: `backend/config/settings.py`

添加配置项：
```python
LOG_LEVEL: str = "INFO"  # 日志级别
LOG_DIR: Path = Path("./logs")  # 日志目录
```

### 3. 应用启动时初始化日志
**文件**: `backend/main.py`

在应用启动的最早阶段配置日志系统，确保所有后续的日志调用都能正确工作。

### 4. Docker 环境变量支持
**文件**: `docker-compose.yml`

添加环境变量：
```yaml
- LOG_LEVEL=${LOG_LEVEL:-INFO}
```

支持通过 Docker 环境变量动态调整日志级别。

## 日志文件说明

### 文件位置
- **本地开发**: `./logs/`
- **Docker 容器**: `/app/logs/` (已挂载到宿主机 `./logs/`)

### 文件列表
| 文件名 | 说明 | 日志级别 |
|--------|------|----------|
| `beanmind.log` | 主日志文件 | ALL (DEBUG 及以上) |
| `error.log` | 错误日志文件 | ERROR 及以上 |
| `*.log.1, *.log.2...` | 历史轮转文件 | - |

### 日志轮转规则
- 单个文件最大: 10MB
- 保留历史文件数: 5 个
- 轮转后文件命名: `beanmind.log.1`, `beanmind.log.2`, ...

## 使用说明

### 1. 本地开发
默认配置即可，日志会自动写入 `./logs/` 目录。

修改日志级别（可选）：
```bash
# 在 .env 文件中设置
LOG_LEVEL=DEBUG
```

### 2. Docker 部署
日志会自动写入挂载的 `./logs/` 目录。

查看实时日志：
```bash
# 查看容器日志（控制台输出）
docker-compose logs -f beanmind

# 查看文件日志
tail -f logs/beanmind.log

# 只查看错误日志
tail -f logs/error.log
```

修改日志级别：
```bash
# 方式1: 在 .env 文件中设置
LOG_LEVEL=DEBUG

# 方式2: 在 docker-compose 启动时设置
LOG_LEVEL=DEBUG docker-compose up -d
```

### 3. 日志级别说明
| 级别 | 说明 | 使用场景 |
|------|------|----------|
| `DEBUG` | 调试信息 | 开发调试、问题排查 |
| `INFO` | 一般信息 | 生产环境（默认） |
| `WARNING` | 警告信息 | 生产环境（精简模式） |
| `ERROR` | 错误信息 | 仅关注错误 |
| `CRITICAL` | 严重错误 | 仅关注严重错误 |

## 验证测试

本地测试结果：
```bash
✅ 控制台输出正常（带颜色）
✅ beanmind.log 写入正常
✅ error.log 写入正常
✅ 日志格式正确
✅ 日志级别过滤正常
```

## 后续建议

### 1. 监控日志文件大小
虽然配置了日志轮转，但建议定期清理历史日志：
```bash
# 删除 30 天前的日志
find ./logs -name "*.log.*" -mtime +30 -delete
```

### 2. 生产环境建议
- 使用 `LOG_LEVEL=INFO` 或 `LOG_LEVEL=WARNING`
- 考虑使用外部日志收集系统（如 ELK、Loki）
- 定期备份重要日志

### 3. 日志查询技巧
```bash
# 查找特定时间的日志
grep "2025-12-31 12:" logs/beanmind.log

# 查找错误日志
grep "ERROR" logs/beanmind.log

# 统计错误数量
grep -c "ERROR" logs/beanmind.log

# 查看最近的警告
grep "WARNING" logs/beanmind.log | tail -n 20
```

## 文件变更清单

1. ✅ 新建: `backend/config/logging_config.py` - 日志配置模块
2. ✅ 修改: `backend/config/settings.py` - 添加日志配置项
3. ✅ 修改: `backend/main.py` - 初始化日志系统
4. ✅ 修改: `docker-compose.yml` - 添加日志环境变量
5. ✅ 修改: `.env.example` - 添加日志配置示例

---

**配置完成时间**: 2025-12-31
**测试状态**: 已验证 ✅
