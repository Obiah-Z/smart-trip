import { resolveAssetUrl } from './api'

export function buildPlanExportFilename({
  destinationLabel = 'smart-trip',
  dayCount = 0,
  generatedAt = new Date(),
} = {}) {
  const safeDestination = sanitizeFileName(destinationLabel || 'smart-trip')
  const dateLabel = formatDateStamp(generatedAt)
  const dayLabel = dayCount ? `${dayCount}日` : '行程'
  return `${safeDestination}_${dayLabel}_方案_${dateLabel}.html`
}

export function buildPlanExportHtml(payload = {}) {
  const {
    title = '旅行方案',
    destinationLabel = '待确认目的地',
    dayCount = 0,
    generatedAt = new Date(),
    summaryHtml = '',
    summaryTags = [],
    planFocusChips = [],
    planHighlights = [],
    tripSnapshotCards = [],
    dailyGuide = [],
    days = [],
    hotelCards = [],
    attractionCards = [],
    foodCards = [],
    budget = {},
    budgetInsights = [],
    tripTips = [],
    primaryHotelName = '待生成',
    paceLabel = '均衡',
    totalBudget = null,
    summaryTagsText = '',
    budgetSummaryLine = '',
    taskTypeLabel = '旅行规划',
  } = payload

  const itinerary = dailyGuide.length ? dailyGuide : days
  const summaryBlock = summaryHtml || '<p>暂无摘要，系统已根据当前方案整理出可直接查看的旅行信息。</p>'
  const overviewCards = [
    {
      label: '目的地',
      value: destinationLabel,
      note: taskTypeLabel,
    },
    {
      label: '出行天数',
      value: dayCount ? `${dayCount} 天` : '待确认',
      note: dayCount ? '按天拆分安排' : '可继续补充后更新',
    },
    {
      label: '预计总花费',
      value: formatMoney(totalBudget),
      note: budgetSummaryLine || '系统会综合预算与偏好整理',
    },
    {
      label: '出行节奏',
      value: paceLabel,
      note: summaryTagsText || '按你的要求整理',
    },
  ]

  const coverChips = compactList([
    destinationLabel,
    dayCount ? `${dayCount} 天游览` : '',
    paceLabel ? `${paceLabel}节奏` : '',
    primaryHotelName && primaryHotelName !== '待生成' ? primaryHotelName : '',
    ...summaryTags.slice(0, 3),
  ])

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${escapeHtml(title)}</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f7fb;
      --bg-soft: #f8fbff;
      --surface: rgba(255, 255, 255, 0.94);
      --surface-strong: #ffffff;
      --surface-muted: #f8fafc;
      --border: #e5e7eb;
      --border-strong: #d1d5db;
      --text: #111827;
      --text-subtle: #374151;
      --text-muted: #6b7280;
      --primary: #2563eb;
      --primary-dark: #1d4ed8;
      --primary-soft: #eff6ff;
      --accent: #0f766e;
      --accent-soft: #ecfdf5;
      --shadow-soft: 0 14px 40px rgba(15, 23, 42, 0.07);
      --shadow-card: 0 10px 26px rgba(15, 23, 42, 0.06);
      --radius-xl: 24px;
      --radius-lg: 18px;
      --radius-md: 14px;
      font-family: "IBM Plex Sans", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 28%),
        radial-gradient(circle at top right, rgba(15, 118, 110, 0.09), transparent 30%),
        linear-gradient(180deg, var(--bg-soft) 0%, var(--bg) 100%);
      color: var(--text);
    }

    .page {
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }

    .cover,
    .section {
      background: var(--surface);
      border: 1px solid var(--border);
      box-shadow: var(--shadow-soft);
      backdrop-filter: blur(12px);
    }

    .cover {
      padding: 24px;
      border-radius: var(--radius-xl);
      overflow: hidden;
    }

    .cover-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 18px;
    }

    .eyebrow {
      margin: 0 0 8px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 11px;
      font-weight: 700;
      color: var(--primary);
    }

    h1,
    h2,
    h3,
    h4,
    p {
      margin: 0;
    }

    .title {
      font-size: clamp(28px, 4vw, 42px);
      line-height: 1.15;
      letter-spacing: -0.02em;
    }

    .subtitle {
      margin-top: 10px;
      font-size: 15px;
      color: var(--text-subtle);
      line-height: 1.8;
      max-width: 820px;
    }

    .hero-note {
      margin-top: 14px;
      padding: 14px 16px;
      border-radius: var(--radius-md);
      background: linear-gradient(180deg, #ffffff, var(--primary-soft));
      border: 1px solid rgba(37, 99, 235, 0.14);
      color: var(--text-subtle);
      line-height: 1.8;
    }

    .chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 16px;
    }

    .chip {
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border-radius: 999px;
      background: var(--primary-soft);
      border: 1px solid rgba(37, 99, 235, 0.14);
      color: var(--primary-dark);
      font-size: 12px;
      font-weight: 600;
    }

    .section {
      margin-top: 18px;
      padding: 22px;
      border-radius: var(--radius-xl);
    }

    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 12px;
      margin-bottom: 14px;
    }

    .section-title {
      font-size: 22px;
      line-height: 1.25;
    }

    .section-copy {
      margin-top: 6px;
      color: var(--text-muted);
      line-height: 1.7;
      font-size: 14px;
    }

    .summary-box {
      padding: 18px 20px;
      border-radius: var(--radius-lg);
      background: linear-gradient(180deg, #ffffff, #f8fafc);
      border: 1px solid var(--border);
      color: var(--text-subtle);
      line-height: 1.85;
      overflow: hidden;
    }

    .summary-box p + p,
    .summary-box p + ul,
    .summary-box ul + p,
    .summary-box h1 + p,
    .summary-box h2 + p,
    .summary-box h3 + p,
    .summary-box h4 + p,
    .summary-box h1 + ul,
    .summary-box h2 + ul,
    .summary-box h3 + ul,
    .summary-box h4 + ul {
      margin-top: 10px;
    }

    .summary-box h1,
    .summary-box h2,
    .summary-box h3,
    .summary-box h4 {
      margin-bottom: 10px;
      color: var(--text);
      line-height: 1.35;
    }

    .summary-box h1 { font-size: 1.22rem; }
    .summary-box h2 { font-size: 1.08rem; }
    .summary-box h3,
    .summary-box h4 { font-size: 1rem; }

    .summary-box ul {
      margin: 0;
      padding-left: 20px;
    }

    .summary-box li + li {
      margin-top: 6px;
    }

    .summary-box strong {
      color: var(--text);
    }

    .summary-box code {
      padding: 2px 6px;
      border-radius: 8px;
      background: var(--primary-soft);
      color: var(--primary-dark);
      font-size: 0.92em;
    }

    .metric-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }

    .metric-card {
      padding: 16px;
      border-radius: var(--radius-lg);
      background: linear-gradient(180deg, #ffffff, var(--surface-muted));
      border: 1px solid var(--border);
      box-shadow: var(--shadow-card);
    }

    .metric-label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--text-muted);
    }

    .metric-value {
      margin-top: 8px;
      font-size: 18px;
      line-height: 1.35;
      font-weight: 700;
      color: var(--text);
      word-break: break-word;
    }

    .metric-note {
      margin-top: 8px;
      font-size: 13px;
      color: var(--text-muted);
      line-height: 1.6;
    }

    .focus-grid,
    .budget-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .highlight-strip,
    .tip-list,
    .budget-insight-list {
      display: grid;
      gap: 12px;
    }

    .highlight-pill,
    .tip-item,
    .insight-item {
      padding: 14px 16px;
      border-radius: var(--radius-lg);
      background: var(--surface-strong);
      border: 1px solid var(--border);
      box-shadow: var(--shadow-card);
    }

    .highlight-pill p,
    .tip-item p,
    .insight-item p {
      color: var(--text-subtle);
      line-height: 1.75;
    }

    .trip-preview-grid,
    .recommendation-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }

    .trip-card,
    .recommendation-card,
    .day-card {
      border-radius: var(--radius-lg);
      background: var(--surface-strong);
      border: 1px solid var(--border);
      box-shadow: var(--shadow-card);
      overflow: hidden;
    }

    .trip-card-media {
      position: relative;
      min-height: 132px;
      background: linear-gradient(180deg, #f1f5f9, #e5e7eb);
      border-bottom: 1px solid var(--border);
    }

    .trip-card-media img {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .media-placeholder {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: inherit;
      padding: 18px;
      color: var(--text-muted);
      text-align: center;
      line-height: 1.6;
    }

    .media-badge {
      position: absolute;
      top: 12px;
      left: 12px;
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border-radius: 999px;
      background: rgba(15, 23, 42, 0.76);
      color: #f8fafc;
      font-size: 12px;
      font-weight: 600;
    }

    .trip-card-body,
    .card-body {
      padding: 14px;
    }

    .recommendation-card {
      display: grid;
      grid-template-columns: 104px minmax(0, 1fr);
      align-items: stretch;
    }

    .recommendation-card .trip-card-media {
      min-height: 104px !important;
      height: 100%;
      border-bottom: 0;
      border-right: 1px solid var(--border);
    }

    .recommendation-card .card-body {
      padding: 12px;
    }

    .card-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
    }

    .card-title {
      font-size: 16px;
      line-height: 1.45;
    }

    .card-badge {
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border-radius: 999px;
      background: var(--surface-muted);
      border: 1px solid var(--border);
      color: var(--text-subtle);
      font-size: 12px;
      font-weight: 600;
    }

    .card-meta,
    .day-meta,
    .card-summary {
      margin-top: 8px;
      color: var(--text-muted);
      line-height: 1.7;
      font-size: 13px;
    }

    .card-summary {
      color: var(--text-subtle);
      font-size: 14px;
      display: -webkit-box;
      overflow: hidden;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
    }

    .card-chip-row,
    .day-chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }

    .day-list {
      display: grid;
      gap: 14px;
    }

    .day-card {
      padding: 16px;
    }

    .day-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }

    .day-chip {
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      border: 1px solid rgba(15, 118, 110, 0.16);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
    }

    .day-title {
      margin-top: 8px;
      font-size: 18px;
      line-height: 1.4;
    }

    .day-route {
      margin-top: 10px;
      color: var(--text-subtle);
      line-height: 1.75;
    }

    .day-note,
    .day-hint {
      margin-top: 10px;
      color: var(--text-muted);
      line-height: 1.7;
    }

    .budget-item {
      padding: 14px 16px;
      border-radius: var(--radius-lg);
      background: var(--surface-strong);
      border: 1px solid var(--border);
      box-shadow: var(--shadow-card);
    }

    .budget-item .metric-value {
      margin-top: 6px;
      font-size: 17px;
    }

    .footer {
      margin-top: 20px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
      color: var(--text-muted);
      text-align: center;
      font-size: 12px;
      line-height: 1.7;
    }

    .export-empty {
      padding: 14px 16px;
      border-radius: var(--radius-lg);
      border: 1px dashed var(--border-strong);
      color: var(--text-muted);
      background: rgba(255, 255, 255, 0.55);
    }

    @media (max-width: 960px) {
      .metric-grid,
      .focus-grid,
      .budget-grid,
      .trip-preview-grid,
      .recommendation-grid {
        grid-template-columns: 1fr;
      }

      .recommendation-card {
        grid-template-columns: 1fr;
      }

      .recommendation-card .trip-card-media {
        min-height: 150px !important;
        border-right: 0;
        border-bottom: 1px solid var(--border);
      }

      .cover-top,
      .section-head,
      .day-head,
      .card-head {
        flex-direction: column;
        align-items: flex-start;
      }
    }

    @media print {
      body {
        background: #fff;
      }

      .page {
        max-width: none;
        padding: 0;
      }

      .cover,
      .section,
      .metric-card,
      .trip-card,
      .recommendation-card,
      .day-card,
      .highlight-pill,
      .tip-item,
      .insight-item,
      .budget-item {
        box-shadow: none;
      }

      .cover,
      .section {
        break-inside: avoid;
      }
    }
  </style>
</head>
<body>
  <main class="page">
    <section class="cover">
      <div class="cover-top">
        <div>
          <p class="eyebrow">Smart Trip</p>
          <h1 class="title">${escapeHtml(destinationLabel)} ${dayCount ? `${dayCount} 日旅行方案` : '旅行方案'}</h1>
          <p class="subtitle">这是一份面向旅行决策的格式化方案页，保留了你最需要直接参考的信息，方便查看、保存和转发。</p>
        </div>
        <span class="chip">${escapeHtml(taskTypeLabel)}</span>
      </div>
      <div class="hero-note">
        ${summaryBlock}
      </div>
      <div class="chip-row">
        ${coverChips.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join('')}
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2 class="section-title">方案概览</h2>
          <p class="section-copy">把当前旅行计划里最先需要看的信息放在前面，便于快速判断是否符合预期。</p>
        </div>
      </div>
      <div class="metric-grid">
        ${overviewCards
          .map(
            (item) => `
              <article class="metric-card">
                <span class="metric-label">${escapeHtml(item.label)}</span>
                <div class="metric-value">${escapeHtml(item.value)}</div>
                <p class="metric-note">${escapeHtml(item.note)}</p>
              </article>
            `,
          )
          .join('')}
      </div>
    </section>

    ${
      planFocusChips.length
        ? `
      <section class="section">
        <div class="section-head">
          <div>
            <h2 class="section-title">这份方案会重点照顾</h2>
            <p class="section-copy">这些标签对应的是系统在生成方案时优先纳入的约束与偏好。</p>
          </div>
        </div>
        <div class="chip-row">
          ${planFocusChips.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join('')}
        </div>
      </section>`
        : ''
    }

    ${
      planHighlights.length
        ? `
      <section class="section">
        <div class="section-head">
          <div>
            <h2 class="section-title">先看几个重点</h2>
            <p class="section-copy">这些内容适合先扫一遍，快速建立整趟旅行的感受。</p>
          </div>
        </div>
        <div class="highlight-strip">
          ${planHighlights
            .map(
              (item) => `
                <article class="highlight-pill">
                  <p>${escapeHtml(item)}</p>
                </article>
              `,
            )
            .join('')}
        </div>
      </section>`
        : ''
    }

    ${
      tripSnapshotCards.length
        ? `
      <section class="section">
        <div class="section-head">
          <div>
            <h2 class="section-title">旅行预览</h2>
            <p class="section-copy">先用几个代表性卡片感受住宿、景点和餐饮的整体调性。</p>
          </div>
        </div>
        <div class="trip-preview-grid">
          ${tripSnapshotCards
            .map(
              (card) => `
                <article class="trip-card">
                  <div class="trip-card-media">
                    ${
                      card.imageUrl
                        ? `<img src="${escapeHtml(resolveAssetUrl(card.imageUrl))}" alt="${escapeHtml(card.imageAlt || card.title || '旅行预览')}" />`
                        : `<div class="media-placeholder">${escapeHtml(card.placeholder || '暂无图片')}</div>`
                    }
                    ${card.imageLabel ? `<span class="media-badge">${escapeHtml(card.imageLabel)}</span>` : ''}
                  </div>
                  <div class="trip-card-body">
                    <div class="card-head">
                      <h3 class="card-title">${escapeHtml(card.title || '')}</h3>
                      ${card.badge ? `<span class="card-badge">${escapeHtml(card.badge)}</span>` : ''}
                    </div>
                    ${card.meta ? `<p class="card-meta">${escapeHtml(card.meta)}</p>` : ''}
                    ${card.summary ? `<p class="card-summary">${escapeHtml(card.summary)}</p>` : ''}
                    ${
                      Array.isArray(card.chips) && card.chips.length
                        ? `<div class="card-chip-row">${card.chips.map((chip) => `<span class="chip">${escapeHtml(chip)}</span>`).join('')}</div>`
                        : ''
                    }
                  </div>
                </article>
              `,
            )
            .join('')}
        </div>
      </section>`
        : ''
    }

    <section class="section">
      <div class="section-head">
        <div>
          <h2 class="section-title">按天安排</h2>
          <p class="section-copy">用时间线方式展开每一天的主题、活动和区域信息，方便快速浏览。</p>
        </div>
      </div>
      ${
        itinerary.length
          ? `
        <div class="day-list">
          ${itinerary
            .map(
              (day) => `
                <article class="day-card">
                  <div class="day-head">
                    <div>
                      <span class="day-chip">Day ${escapeHtml(day.day ?? '')}</span>
                      <h3 class="day-title">${escapeHtml(day.theme || `第 ${day.day} 天`)}</h3>
                    </div>
                    <span class="chip">${escapeHtml(day.area || '区域待定')}</span>
                  </div>
                  ${day.note ? `<p class="day-note">${escapeHtml(day.note)}</p>` : ''}
                  <p class="day-route">${escapeHtml((day.activities || day.route || []).join(' → ') || '暂无安排')}</p>
                  <div class="day-chip-row">
                    ${day.highlights?.length ? day.highlights.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join('') : ''}
                  </div>
                  <div class="day-meta">
                    ${day.estimatedDurationHours ? `约 ${escapeHtml(String(day.estimatedDurationHours))} 小时` : '时长待定'}
                    ${day.estimatedTickets ? ` · 门票约 ${escapeHtml(formatMoney(day.estimatedTickets))}` : ''}
                    ${day.mealHint ? `<div class="day-hint">${escapeHtml(day.mealHint)}</div>` : ''}
                  </div>
                </article>
              `,
            )
            .join('')}
        </div>`
          : `<p class="export-empty">当前没有可展开的按天安排。</p>`
      }
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2 class="section-title">预算与提醒</h2>
          <p class="section-copy">预算拆分和出行提醒放在最后，方便在确认方案后快速检查风险点。</p>
        </div>
      </div>

      <div class="budget-grid">
        <article class="budget-item">
          <span class="metric-label">交通</span>
          <div class="metric-value">${escapeHtml(formatMoney(budget.transport))}</div>
        </article>
        <article class="budget-item">
          <span class="metric-label">住宿</span>
          <div class="metric-value">${escapeHtml(formatMoney(budget.accommodation))}</div>
        </article>
        <article class="budget-item">
          <span class="metric-label">餐饮</span>
          <div class="metric-value">${escapeHtml(formatMoney(budget.food))}</div>
        </article>
        <article class="budget-item">
          <span class="metric-label">门票</span>
          <div class="metric-value">${escapeHtml(formatMoney(budget.tickets))}</div>
        </article>
      </div>

      ${
        budgetInsights.length
          ? `
        <div class="budget-insight-list" style="margin-top: 12px;">
          ${budgetInsights
            .map(
              (item) => `
                <article class="insight-item">
                  <strong>${escapeHtml(item.label || '')}</strong>
                  <p>${escapeHtml(item.value || '')}${item.detail ? ` · ${escapeHtml(item.detail)}` : ''}</p>
                </article>
              `,
            )
            .join('')}
        </div>`
          : ''
      }

      ${
        tripTips.length
          ? `
        <div class="tip-list" style="margin-top: 12px;">
          ${tripTips
            .map(
              (item) => `
                <article class="tip-item">
                  <p>${escapeHtml(item)}</p>
                </article>
              `,
            )
            .join('')}
        </div>`
          : ''
      }
    </section>

    <div class="footer">
      <p>本页由当前旅行方案导出生成，适合保存、转发或打印。</p>
      <p>生成时间：${escapeHtml(formatDateTime(generatedAt))}</p>
    </div>
  </main>
</body>
</html>`
}

export function downloadPlanExportHtml(html, filename) {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function previewPlanExportHtml(html, filename) {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const win = window.open(url, '_blank', 'noopener,noreferrer')
  if (!win) {
    URL.revokeObjectURL(url)
    downloadPlanExportHtml(html, filename)
    return false
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  return true
}

function formatMoney(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '待定'
  return `¥${value}`
}

function formatDateStamp(date) {
  const value = date instanceof Date ? date : new Date(date)
  if (Number.isNaN(value.getTime())) return 'unknown-date'
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}${month}${day}`
}

function formatDateTime(date) {
  const value = date instanceof Date ? date : new Date(date)
  if (Number.isNaN(value.getTime())) return '未知时间'
  return value.toLocaleString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function sanitizeFileName(value) {
  return String(value || 'smart-trip')
    .trim()
    .replace(/[\\/:*?"<>|]+/g, '-')
    .replace(/\s+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function compactList(items = []) {
  return items
    .map((item) => String(item || '').trim())
    .filter(Boolean)
}
