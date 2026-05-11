# AI Gateway Hermes

基于多API密钥自动负载均衡与容灾设计的高性能AI服务网关，提供稳定、可扩展的AI服务接入能力。

## 项目概述

AI Gateway Hermes 是一个专为AI服务设计的网关系统，核心功能覆盖API密钥管理、智能路由、负载均衡、流量控制等，为AI服务提供统一的接入入口。

## 核心特性

### 🔧 核心能力

#### 缓存管理
- **智能缓存策略**：基于LRU（Least Recently Used）算法，实现智能缓存淘汰
- **热点数据识别**：自动识别高频访问的AI模型和API响应，优化缓存命中率
- **分布式缓存同步**：支持多节点间的缓存数据一致性保证

#### Agent会话管理
- **会话持久化**：跨请求的上下文保持
- **会话恢复**：支持会话中断后的自动恢复，确保用户体验连续性
- **多Agent协作**：支持多个AI Agent之间的协同工作，处理复杂任务

#### 智能路由
- **服务发现**：自动发现后端AI服务实例，实现动态路由
- **权重分配**：基于历史性能数据，智能分配请求权重
- **故障转移**：自动检测并隔离故障节点，确保服务可用性

### 🔐 API密钥管理

#### 密钥生成与分发
```python
# 示例：API密钥生成实现
import hashlib
import secrets
import time

class APIKeyManager:
    def __init__(self):
        self.key_store = {}
    
    def generate_key(self, user_id, permissions):
        timestamp = str(int(time.time()))
        random_part = secrets.token_hex(16)
        data = f"{user_id}:{permissions}:{timestamp}:{random_part}"
        key_hash = hashlib.sha256(data.encode()).hexdigest()
        api_key = f"aih_{key_hash[:32]}"
        
        self.key_store[api_key] = {
            'user_id': user_id,
            'permissions': permissions,
            'created_at': timestamp,
            'last_used': None,
            'usage_count': 0
        }
        
        return api_key
```

#### 权限控制
- **细粒度权限**：支持模型级别、操作级别的权限控制
- **动态权限更新**：运行时更新API密钥权限，无需重启服务
- **审计日志**：记录所有API密钥的使用情况，支持安全审计

#### 密钥轮换
- **自动轮换**：支持定期自动生成新密钥，旧密钥平滑过渡
- **手动轮换**：支持管理员手动触发密钥轮换
- **黑名单机制**：支持将特定密钥加入黑名单，立即失效

### ⚖️ 负载均衡策略

#### 基于多维度指标的智能负载均衡
```python
# 示例：多维度负载均衡算法
class LoadBalancer:
    def __init__(self):
        self.server_weights = {}
        self.response_times = {}
        self.error_rates = {}
    
    def calculate_weight(self, server_id):
        # 基于历史响应时间
        response_time_factor = 1 / (self.response_times.get(server_id, 1) + 0.1)
        
        # 基于错误率
        error_rate = self.error_rates.get(server_id, 0)
        error_factor = 1 - min(error_rate, 0.9)
        
        # 综合权重计算
        weight = response_time_factor * error_factor
        self.server_weights[server_id] = weight
        
        return weight
```

#### 多维度负载指标
- **响应时间**：实时监控各节点的平均响应时间
- **错误率**：统计各节点的错误请求比例
- **会话负载**：基于活跃会话数量评估节点负载
- **资源利用率**：监控CPU、内存、GPU等资源使用情况

#### 动态调整策略
- **自适应权重**：根据实时指标动态调整节点权重
- **流量削峰**：在流量高峰期自动启用限流机制
- **冷启动处理**：对新加入的节点采用渐进式流量引入

## 技术架构

### 系统组件
```
┌─────────────────────────────────────────────────────────────┐
│                     AI Gateway Hermes                        │
├─────────────────────────────────────────────────────────────┤
│  API Gateway Layer                                          │
│  ├─ Request Router                                          │
│  ├─ Rate Limiter                                            │
│  └─ Authentication                                          │
├─────────────────────────────────────────────────────────────┤
│  Load Balancer Layer                                        │
│  ├─ Multi-Metric LB Algorithm                                │
│  ├─ Health Check                                            │
│  └─ Fault Tolerance                                         │
├─────────────────────────────────────────────────────────────┤
│  Gateway Core Layer                                    │
│  ├─ Cache Manager                                       │
│  ├─ Agent Session Manager                                   │
│  └─ Service Discovery                                       │
├─────────────────────────────────────────────────────────────┤
│  Backend Services                                           │
│  ├─ AI Model Services                                       │
│  ├─ Data Processing Services                                │
│  └─ Analytics Services                                      │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈
- **编程语言**: Python 3.9+
- **Web框架**: FastAPI
- **数据库**: PostgreSQL (主数据), Redis (缓存)
- **消息队列**: RabbitMQ
- **容器化**: Docker & Kubernetes
- **监控**: Prometheus & Grafana

## 运行成果

- 连续稳定运行2周
- 累计处理8,127次API请求
- 总消耗Token约5.39亿
- 采用混合模型策略：deepseek-v4-flash处理8,046次请求（5.31亿Token），deepseek-v4-pro处理81次请求（746万Token）
- 单次请求平均处理6.6万-9.2万Tokens
- 零人工干预，无一次因配额耗尽导致任务中止

## 项目特色

- 🚀 **高并发**: 支持多Key并发请求，大幅提升处理效率
- 🛡️ **容灾能力**: 自动故障检测和切换，确保任务连续性
- 📊 **智能调度**: 基于多维度指标的负载均衡算法
- 🔔 **实时告警**: 配额不足时自动通知，及时补充资源
- 🔄 **自动重试**: 智能重试机制，提高成功率
- 🧠 **AI原生**: 专为AI工作负载设计，开箱即用

## 适用场景

- 大规模文档分析和处理
- 批量对话数据处理
- 长时间运行的AI任务
- 需要高可用性的AI服务
- 多Agent协作的复杂任务

## 许可证

MIT License

---

*本项目展示了一个完整的AI网关系统，通过智能调度和容灾机制解决大规模AI任务中的配额限制与负载均衡问题。*