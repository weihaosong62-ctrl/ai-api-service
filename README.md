# AI API Service

> GPT-4 级别 API，价格只要 OpenAI 的 1/3。DeepSeek V4 驱动，一行代码切换。

## 定价

| 套餐 | 价格 | Token | 适合 |
|------|------|-------|------|
| Starter | $9/月 | 100万 | 个人开发者测试 |
| Pro | $29/月 | 500万 | 小团队 / 项目 |
| Max | $99/月 | 2000万 | 商业应用 |

## 快速接入

```bash
pip install openai
```

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-aichat-xxxx",  # 购买后获得
    base_url="https://grooving-revenge-tiger.ngrok-free.dev/v1"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

## cURL

```bash
curl https://grooving-revenge-tiger.ngrok-free.dev/v1/chat/completions \
  -H "Authorization: Bearer sk-aichat-xxxx" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"Hello!"}]}'
```

## 为什么选择我们

| | OpenAI | Claude | **我们** |
|------|--------|--------|--------|
| 模型等级 | GPT-4 | Claude 4 | **DeepSeek V4（同级）** |
| 价格 | $20/月 | $20/月 | **$9/月起** |
| Token 量 | 限制 | 限制 | **100万起** |
| SDK 兼容 | OpenAI | 不兼容 | **完全兼容 OpenAI** |

## 获取 API Key

👉 [立即购买](https://grooving-revenge-tiger.ngrok-free.dev)

PayPal 安全支付，支付完成后秒得 API Key。

## 兼容性

- ✅ OpenAI Python SDK
- ✅ LangChain
- ✅ Dify
- ✅ 所有 OpenAI 生态工具
- ✅ 支持 deepseek-chat 和 deepseek-reasoner

## 常见问题

**Q：和 DeepSeek 官方什么区别？**  
A：底层模型一样，我们提供更灵活的套餐定价，PayPal 支付更方便。

**Q：超额了怎么办？**  
A：API 返回 429 提示额度用完，购买新套餐继续用。

**Q：能退款吗？**  
A：24 小时内 Key 未被调用，全额退款。
