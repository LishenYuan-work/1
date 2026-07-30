"""联网搜索模块 — 为事实核查提供实时证据"""

from ddgs import DDGS


def search_web(query: str, max_results: int = 3) -> list[dict]:
    """搜索网络，返回标题+摘要+URL"""
    try:
        results = []
        for r in DDGS().text(query, max_results=max_results):
            results.append({
                "title": r["title"],
                "body": r["body"],
                "url": r.get("href", ""),
            })
        return results
    except Exception:
        return []  # 搜索失败不阻塞核查流程


def search_factual_claims(text: str) -> list[dict]:
    """从文本中提取事实性陈述并搜索验证

    自动识别包含数字、专有名词、时间等的事实句，
    对每个句子进行联网搜索。
    """
    # 简单分句
    sentences = [s.strip() for s in text.replace("；", "。").replace("；", "。").split("。") if len(s.strip()) > 10]

    # 筛选包含事实信号的句子
    factual_signals = [
        "亿", "万", "%", "年", "月", "日", "美元", "元",
        "增长", "下降", "超过", "达到", "占", "排名", "统计",
        "表明", "显示", "证实", "发现", "报告", "研究",
        "第一", "首个", "最大", "最小", "首次",
        "美国", "中国", "全球", "世界", "国家",
    ]
    factual_sentences = [
        s for s in sentences
        if any(signal in s for signal in factual_signals)
    ]

    # 每个事实句做一次搜索，去重后返回
    all_results: list[dict] = []
    seen_urls = set()
    for sentence in factual_sentences[:6]:  # 最多 6 个事实句
        query = sentence[:120]  # 用前 120 字作为搜索词
        for r in search_web(query, max_results=2):
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                r["query"] = query
                all_results.append(r)

    return all_results


def format_search_results(results: list[dict]) -> str:
    """将搜索结果格式化为 Agent 可读的文本"""
    if not results:
        return "（未找到相关网络资料）"

    lines = []
    for i, r in enumerate(results[:15], 1):
        lines.append(f"[{i}] {r['title']}\n    {r['body'][:200]}\n    来源: {r.get('url', 'N/A')}")
    return "\n\n".join(lines)
