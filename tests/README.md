# BeanMind 单元测试

本目录包含BeanMind项目的所有单元测试。

## 测试结构

```
tests/
├── __init__.py
├── conftest.py              # pytest配置
├── test_config.py           # 配置管理测试
├── test_database.py         # 数据库测试
├── test_jwt_utils.py        # JWT工具测试
├── test_password_utils.py   # 密码工具测试
└── test_beancount_service.py  # Beancount服务测试
```

## 运行测试

### 运行所有测试
```bash
./run_tests.sh
```

或者直接使用pytest：
```bash
pytest tests/ -v
```

### 运行特定测试文件
```bash
pytest tests/test_config.py -v
```

### 运行特定测试类
```bash
pytest tests/test_jwt_utils.py::TestJWTUtils -v
```

### 运行特定测试方法
```bash
pytest tests/test_jwt_utils.py::TestJWTUtils::test_create_access_token -v
```

### 查看测试覆盖率
```bash
pytest tests/ --cov=backend --cov-report=html
```

生成的覆盖率报告在 `htmlcov/index.html`

## 测试覆盖范围

- ✅ **配置管理** (7个测试)
  - 配置加载
  - 环境变量
  - 辅助方法

- ✅ **数据库连接** (3个测试)
  - 会话管理
  - 基本查询
  - 默认数据

- ✅ **JWT工具** (6个测试)
  - Token创建
  - Token验证
  - 过期检查

- ✅ **密码工具** (5个测试)
  - 密码加密
  - 密码验证
  - 哈希唯一性

- ✅ **Beancount服务** (6个测试)
  - 服务初始化
  - 账户查询
  - 余额计算
  - 交易列表

**总计：27个测试**

## 持续开发规范

每次修改代码后，必须：

1. ✅ 运行所有单元测试
2. ✅ 确保所有测试通过
3. ✅ 如有新功能，添加相应测试
4. ✅ 保持测试覆盖率 > 80%

## 测试最佳实践

1. 每个测试应该独立运行
2. 使用 pytest fixtures 管理测试数据
3. 测试命名要清晰描述测试内容
4. 测试应该快速执行
5. 避免测试之间的依赖关系
