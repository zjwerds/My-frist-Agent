from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.services.stats_service import get_stats
from app.services import config_file

router = APIRouter(prefix="/api")


@router.get("/stats")
def stats():
    cfg = config_file.read_config()
    api_key = cfg.get("api_key") if cfg else None
    base_url = cfg.get("base_url") if cfg else None
    return get_stats(api_key=api_key, base_url=base_url)


# Floating widget HTML page — loaded in an always-on-top Electron BrowserWindow
FLOATING_WIDGET_HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
  background: transparent;
  color: #e0e0e0;
  overflow: hidden;
  user-select: none;
  -webkit-app-region: drag;
}
#app {
  background: rgba(22, 22, 42, 0.92);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(42, 42, 74, 0.6);
  border-radius: 12px;
  margin: 4px;
  padding: 16px;
}
.header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(42, 42, 74, 0.5);
}
.header .icon { font-size: 20px; }
.header .title { font-size: 14px; font-weight: 600; color: #d0d0d0; }
.header .count-badge {
  margin-left: auto;
  font-size: 10px;
  color: #888;
}
.close-btn {
  -webkit-app-region: no-drag;
  background: none;
  border: none;
  color: #666;
  font-size: 16px;
  cursor: pointer;
  padding: 0 0 0 6px;
  line-height: 1;
}
.close-btn:hover { color: #f87171; }
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  font-size: 13px;
}
.row .label { color: #999; }
.row .value { color: #e0e0e0; font-weight: 500; }
.section-title {
  font-size: 11px;
  color: #666;
  margin: 10px 0 4px 0;
}
.token-box {
  background: rgba(30, 30, 58, 0.5);
  border-radius: 8px;
  padding: 8px 12px;
  margin-top: 4px;
}
.token-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 3px 0;
}
.token-row .label { color: #888; }
.token-row .value { color: #ccc; }
.token-divider {
  border: none;
  border-top: 1px solid rgba(42, 42, 74, 0.4);
  margin: 4px 0;
}
.token-total .label { color: #aaa; font-weight: 500; }
.token-total .value { color: #e0e0e0; font-weight: 600; }
.cache-rate { color: #4ade80; }
.footer {
  text-align: center;
  margin-top: 10px;
  font-size: 10px;
  color: #555;
}
.loading {
  text-align: center;
  padding: 40px 0;
  color: #888;
  font-size: 13px;
}
</style>
</head>
<body>
<div id="app">
  <div class="header">
    <span class="icon">🍳</span>
    <span class="title">煎蛋状态</span>
    <span class="count-badge" id="sessionCount"></span>
    <button class="close-btn" onclick="window.close()">✕</button>
  </div>
  <div id="content">
    <div class="loading">加载中...</div>
  </div>
  <div class="footer">可拖动 • 置顶显示</div>
</div>
<script>
const CONTENT = document.getElementById('content');
const SESSION = document.getElementById('sessionCount');

function formatNum(n) { return Number(n).toLocaleString('zh-CN'); }

async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) throw new Error('fetch failed');
    const s = await res.json();
    SESSION.textContent = s.session_count + ' 次请求';
    CONTENT.innerHTML = `
      <div class="row">
        <span class="label">💰 余额</span>
        <span class="value">${s.balance ? '¥' + parseFloat(s.balance).toFixed(2) : '--'}</span>
      </div>
      <div class="section-title">📊 Token 用量</div>
      <div class="token-box">
        <div class="token-row">
          <span class="label">Prompt</span>
          <span class="value">${formatNum(s.total_prompt_tokens)}</span>
        </div>
        <div class="token-row">
          <span class="label">Completion</span>
          <span class="value">${formatNum(s.total_completion_tokens)}</span>
        </div>
        <hr class="token-divider">
        <div class="token-row token-total">
          <span class="label">总计</span>
          <span class="value">${formatNum(s.total_tokens)}</span>
        </div>
      </div>
      <div class="row" style="margin-top:8px">
        <span class="label">⚡ 缓存命中率</span>
        <span class="value ${s.cache_hit_rate > 0.3 ? 'cache-rate' : ''}">${(s.cache_hit_rate * 100).toFixed(1)}%</span>
      </div>
    `;
  } catch {
    CONTENT.innerHTML = '<div class="loading" style="color:#f87171">连接失败</div>';
  }
}

fetchStats();
setInterval(fetchStats, 30000);
</script>
</body>
</html>
"""


@router.get("/stats/widget", response_class=HTMLResponse)
def stats_widget():
    return HTMLResponse(content=FLOATING_WIDGET_HTML)
