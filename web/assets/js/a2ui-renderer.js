/**
 * A2UI 卡片渲染器 — 将 A2UI JSON 转换为 HTML DOM
 *
 * 支持所有 8 种卡片类型，使用 vanilla JavaScript (ES6)，
 * 无外部依赖。样式由 a2ui-cards.css 提供。
 *
 * 使用方法:
 *   A2UIRenderer.render(cardJSON, document.getElementById('chat-container'));
 *
 * @version 1.0.0
 */
const A2UIRenderer = (() => {
  'use strict';

  // ═══════════════════════════════════════════
  // 工具函数
  // ═══════════════════════════════════════════

  /** 安全转字符串 */
  const esc = (v, fallback = '') => {
    if (v === null || v === undefined) return fallback;
    return String(v);
  };

  /** 安全转数字 */
  const safeNum = (v, fallback = 0) => {
    const n = Number(v);
    return Number.isNaN(n) ? fallback : n;
  };

  /** 安全转列表 */
  const safeList = (v) => (Array.isArray(v) ? v : []);

  /** 格式化金额 */
  const fmtMoney = (v) => `¥${safeNum(v).toFixed(2)}`;

  /** 格式化百分比 */
  const fmtPct = (v) => `${(safeNum(v) * 100).toFixed(1)}%`;

  /** 格式化整数百分比 */
  const fmtIntPct = (v) => `${Math.round(safeNum(v) * 100)}%`;

  /** 创建 DOM 元素 */
  const el = (tag, className, attrs = {}, children = []) => {
    const elem = document.createElement(tag);
    if (className) elem.className = className;
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'textContent') {
        elem.textContent = v;
      } else if (k === 'innerHTML') {
        elem.innerHTML = v;
      } else if (k.startsWith('data-')) {
        elem.setAttribute(k.replace('data-', 'data-'), v);
      } else if (k === 'ariaLabel') {
        elem.setAttribute('aria-label', v);
      } else if (k === 'role') {
        elem.setAttribute('role', v);
      } else {
        elem.setAttribute(k, v);
      }
    }
    for (const child of children) {
      if (typeof child === 'string') {
        elem.appendChild(document.createTextNode(child));
      } else if (child instanceof Node) {
        elem.appendChild(child);
      }
    }
    return elem;
  };

  // ═══════════════════════════════════════════
  // 卡片工厂
  // ═══════════════════════════════════════════

  /**
   * 创建标准卡片容器
   */
  const cardWrapper = (card, title, subtitle, accentColorClass, contentEls, actionEls) => {
    const wrapper = el('div', `a2ui-card a2ui-${card.type.replace(/_/g, '-')}`, {
      role: 'article',
      ariaLabel: title,
    });

    // 头部
    const header = el('div', 'a2ui-card-header');
    if (accentColorClass) {
      header.appendChild(el('div', `a2ui-accent-bar ${accentColorClass}`));
    }
    const headerText = el('div', 'a2ui-card-header-text');
    headerText.appendChild(el('div', 'a2ui-card-title', { textContent: title }));
    if (subtitle) {
      headerText.appendChild(el('div', 'a2ui-card-subtitle', { textContent: subtitle }));
    }
    header.appendChild(headerText);
    wrapper.appendChild(header);

    // 内容区
    const body = el('div', 'a2ui-card-body');
    contentEls.forEach(c => body.appendChild(c));
    wrapper.appendChild(body);

    // 操作按钮
    if (actionEls && actionEls.length > 0) {
      const actions = el('div', 'a2ui-card-actions');
      actionEls.forEach(a => actions.appendChild(a));
      wrapper.appendChild(actions);
    }

    return wrapper;
  };

  /**
   * 创建按钮
   */
  const createBtn = (label, action, data, variant = 'primary') => {
    const btn = el('button', `a2ui-btn a2ui-btn-${variant}`, {
      textContent: label,
      'data-action': action,
      'data-payload': JSON.stringify(data),
      type: 'button',
      ariaLabel: label,
    });
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const payload = JSON.parse(btn.getAttribute('data-payload') || '{}');
      A2UIRenderer._dispatchAction(action, payload);
    });
    return btn;
  };

  /**
   * 状态标签
   */
  const statusBadge = (status, progress) => {
    let cls = 'a2ui-badge';
    let label = status;

    if (progress !== undefined && progress !== null) {
      if (progress >= 1) { cls += ' a2ui-badge-success'; label = '已完成'; }
      else if (progress > 0) { cls += ' a2ui-badge-warning'; label = '进行中'; }
      else { cls += ' a2ui-badge-muted'; label = '待开始'; }
    } else {
      switch ((status || '').toLowerCase()) {
        case 'paid': case 'completed': case 'pass': case 'delivered': case 'in_stock':
          cls += ' a2ui-badge-success'; break;
        case 'pending': case 'shipped': case 'ordered': case 'in_progress':
          cls += ' a2ui-badge-warning'; break;
        case 'overdue': case 'fail': case 'cancelled': case 'disputed': case 'out_of_stock':
          cls += ' a2ui-badge-danger'; break;
        default:
          cls += ' a2ui-badge-muted';
      }
    }

    return el('span', cls, { textContent: label, ariaLabel: `状态: ${label}` });
  };

  /**
   * 信息行 (label: value)
   */
  const infoRow = (label, value, opts = {}) => {
    const { valueCls = '', bold = false } = opts;
    const row = el('div', 'a2ui-info-row');
    row.appendChild(el('span', 'a2ui-info-label', { textContent: label }));
    const valSpan = el('span', `a2ui-info-value${bold ? ' a2ui-info-value-bold' : ''}${valueCls ? ' ' + valueCls : ''}`, { textContent: value });
    row.appendChild(valSpan);
    return row;
  };

  /**
   * 标签 chip
   */
  const tagChip = (label, cls = '') => {
    return el('span', `a2ui-tag ${cls}`, { textContent: label });
  };

  // ═══════════════════════════════════════════
  // 具体卡片渲染器
  // ═══════════════════════════════════════════

  /**
   * 设计方案卡片
   */
  const renderDesignPlan = (card, data) => {
    const projectName = esc(data.project_name, '设计方案');
    const floorLayout = esc(data.floor_layout);
    const totalArea = safeNum(data.total_area);
    const style = esc(data.style);
    const timeline = esc(data.estimated_timeline);
    const preview3d = esc(data.preview_3d_url);
    const rooms = safeList(data.rooms);

    const content = [];

    // 风格和工期标签
    if (style || timeline) {
      const tagsRow = el('div', 'a2ui-tags-row');
      if (style) tagsRow.appendChild(tagChip(style, 'a2ui-tag-design'));
      if (timeline) tagsRow.appendChild(tagChip(`工期 ${timeline}`, 'a2ui-tag-design'));
      content.push(tagsRow);
    }

    // 房间网格
    if (rooms.length > 0) {
      const sectionTitle = el('div', 'a2ui-section-title', { textContent: '房间分布' });
      content.push(sectionTitle);

      const grid = el('div', 'a2ui-room-grid');
      rooms.forEach(r => {
        const name = esc(r.name);
        const area = safeNum(r.area);
        const orientation = esc(r.orientation);
        const tile = el('div', 'a2ui-room-tile');
        tile.appendChild(el('div', 'a2ui-room-name', { textContent: name }));
        tile.appendChild(el('div', 'a2ui-room-area', { textContent: `${area.toFixed(1)}㎡` }));
        if (orientation) tile.appendChild(el('div', 'a2ui-room-orientation', { textContent: orientation }));
        grid.appendChild(tile);
      });
      content.push(grid);
    }

    const actions = [];
    if (preview3d) {
      actions.push(createBtn('查看3D', 'view_3d', { preview_3d_url: preview3d }, 'primary'));
    }

    return cardWrapper(card, projectName,
      `${floorLayout} · ${totalArea.toFixed(1)}㎡`,
      'a2ui-accent-design',
      content, actions);
  };

  /**
   * 预算明细卡片
   */
  const renderBudget = (card, data) => {
    const projectName = esc(data.project_name, '预算明细');
    const total = safeNum(data.total);
    const subtotal = safeNum(data.subtotal);
    const taxAmount = safeNum(data.tax_amount);
    const items = safeList(data.items);
    const warrantyMonths = safeNum(data.warranty_months);
    const warrantyScope = esc(data.warranty_scope);
    const paymentStages = safeList(data.payment_stages);

    const content = [];

    // 费用汇总
    content.push(_summaryLine('小计', subtotal));
    if (taxAmount > 0) {
      content.push(_summaryLine(`税费（${(taxAmount / subtotal * 100).toFixed(1)}%）`, taxAmount));
    }
    content.push(el('hr', 'a2ui-divider'));
    content.push(_summaryLine('合计', total, true));

    // 预算明细表格
    if (items.length > 0) {
      content.push(el('div', 'a2ui-section-title', { textContent: '费用明细' }));
      const table = el('div', 'a2ui-budget-table');
      items.slice(0, 5).forEach(item => {
        const row = el('div', 'a2ui-budget-row');
        // 分类标签
        const cat = esc(item.category);
        const name = esc(item.name);
        const qty = safeNum(item.quantity);
        const unit = esc(item.unit);
        const amount = safeNum(item.amount);

        const nameCol = el('div', 'a2ui-budget-name');
        if (cat) nameCol.appendChild(tagChip(cat, 'a2ui-tag-category'));
        nameCol.appendChild(el('span', 'a2ui-budget-item-name', { textContent: name }));
        row.appendChild(nameCol);

        const qtyCol = el('span', 'a2ui-budget-qty', { textContent: qty > 0 ? `${qty.toFixed(0)}${unit}` : '' });
        row.appendChild(qtyCol);

        const amtCol = el('span', 'a2ui-budget-amount', { textContent: fmtMoney(amount) });
        row.appendChild(amtCol);
        table.appendChild(row);
      });
      content.push(table);
      if (items.length > 5) {
        content.push(el('div', 'a2ui-more-hint', { textContent: `… 共 ${items.length} 项` }));
      }
    }

    // 质保信息
    if (warrantyMonths > 0) {
      const warranty = el('div', 'a2ui-warranty-info');
      warranty.innerHTML = `<span class="a2ui-warranty-icon">🛡️</span> 质保 ${warrantyMonths} 个月${warrantyScope ? ' · ' + warrantyScope : ''}`;
      content.push(warranty);
    }

    // 付款阶段
    if (paymentStages.length > 0) {
      content.push(el('div', 'a2ui-section-title', { textContent: '付款计划' }));
      paymentStages.forEach(stage => {
        const stageRow = el('div', 'a2ui-payment-stage-row');
        const dot = el('span', 'a2ui-stage-dot');
        if (esc(stage.status) === 'paid') dot.classList.add('a2ui-stage-dot-paid');
        stageRow.appendChild(dot);
        stageRow.appendChild(el('span', 'a2ui-stage-name', { textContent: esc(stage.stage) }));
        stageRow.appendChild(el('span', 'a2ui-stage-ratio', { textContent: `${Math.round(safeNum(stage.ratio) * 100)}%` }));
        stageRow.appendChild(el('span', 'a2ui-stage-amount', { textContent: fmtMoney(safeNum(stage.amount)) }));
        stageRow.appendChild(statusBadge(esc(stage.status)));
        content.push(stageRow);
      });
    }

    const actions = [createBtn('查看详情', 'view_budget_detail', data, 'primary')];
    return cardWrapper(card, projectName, `合计 ${fmtMoney(total)}`, 'a2ui-accent-budget', content, actions);
  };

  /** 预算摘要行 */
  const _summaryLine = (label, amount, isTotal = false) => {
    const row = el('div', `a2ui-summary-line${isTotal ? ' a2ui-summary-total' : ''}`);
    row.appendChild(el('span', 'a2ui-summary-label', { textContent: label }));
    row.appendChild(el('span', 'a2ui-summary-value', { textContent: fmtMoney(amount) }));
    return row;
  };

  /**
   * 施工进度卡片
   */
  const renderProgress = (card, data) => {
    const projectName = esc(data.project_name, '施工进度');
    const overall = safeNum(data.overall_progress);
    const phases = safeList(data.phases);
    const crewInfo = data.crew_info || {};
    const nextMs = data.next_milestone || {};

    const content = [];

    // 总体进度条
    const progressSection = el('div', 'a2ui-progress-section');
    const progressHeader = el('div', 'a2ui-progress-header');
    progressHeader.appendChild(el('span', 'a2ui-progress-label', { textContent: '总体进度' }));
    progressHeader.appendChild(el('span', 'a2ui-progress-pct', { textContent: fmtPct(overall) }));
    progressSection.appendChild(progressHeader);

    const bar = el('div', 'a2ui-progress-bar');
    bar.setAttribute('role', 'progressbar');
    bar.setAttribute('aria-valuenow', String(Math.round(overall * 100)));
    bar.setAttribute('aria-valuemin', '0');
    bar.setAttribute('aria-valuemax', '100');
    const fill = el('div', 'a2ui-progress-fill');
    fill.style.width = fmtPct(overall);
    bar.appendChild(fill);
    progressSection.appendChild(bar);
    content.push(progressSection);

    // 班组信息
    if (Object.keys(crewInfo).length > 0) {
      const crew = el('div', 'a2ui-crew-info');
      const leader = esc(crewInfo.leader);
      const teamSize = safeNum(crewInfo.team_size, 0);
      const specs = safeList(crewInfo.specialties);

      let crewHtml = '';
      if (leader) crewHtml += `<span class="a2ui-crew-leader">👷 班组长: ${leader}</span>`;
      if (teamSize > 0) crewHtml += `<span class="a2ui-crew-size">团队 ${teamSize} 人</span>`;
      crew.innerHTML = crewHtml;

      if (specs.length > 0) {
        const tags = el('div', 'a2ui-tags-row');
        specs.forEach(s => tags.appendChild(tagChip(s, 'a2ui-tag-construction')));
        crew.appendChild(tags);
      }
      content.push(crew);
    }

    // 下一里程碑
    if (Object.keys(nextMs).length > 0) {
      const ms = el('div', 'a2ui-milestone');
      ms.innerHTML = `<span class="a2ui-milestone-icon">🚩</span> 下一里程碑: <strong>${esc(nextMs.name)}</strong>`;
      if (esc(nextMs.date)) {
        ms.appendChild(el('div', 'a2ui-milestone-date', { textContent: esc(nextMs.date) }));
      }
      content.push(ms);
    }

    // 阶段列表
    if (phases.length > 0) {
      content.push(el('div', 'a2ui-section-title', { textContent: '阶段进度' }));
      phases.forEach(phase => {
        const name = esc(phase.name);
        const prog = safeNum(phase.progress);
        const status = esc(phase.status);

        const row = el('div', 'a2ui-phase-row');
        const icon = prog >= 1 ? '✅' : prog > 0 ? '⏳' : '○';
        row.appendChild(el('span', 'a2ui-phase-icon', { textContent: icon }));
        row.appendChild(el('span', 'a2ui-phase-name', { textContent: name }));
        row.appendChild(el('span', 'a2ui-phase-pct', { textContent: fmtIntPct(prog) }));
        row.appendChild(statusBadge(status, prog));
        content.push(row);
      });
    }

    const actions = [createBtn('查看详情', 'view_progress_detail', data, 'primary')];
    return cardWrapper(card, projectName, `总体进度 ${fmtPct(overall)}`, 'a2ui-accent-construction', content, actions);
  };

  /**
   * 采购订单卡片
   */
  const renderProcurement = (card, data) => {
    const orderId = esc(data.order_id);
    const totalAmount = safeNum(data.total_amount);
    const deliveryDate = esc(data.delivery_date);
    const status = esc(data.status);
    const supplier = data.supplier || {};
    const items = safeList(data.items);

    const content = [];

    // 供应商
    if (Object.keys(supplier).length > 0) {
      const supRow = el('div', 'a2ui-supplier-row');
      supRow.appendChild(el('span', 'a2ui-supplier-name', { textContent: `🏪 ${esc(supplier.name)}` }));
      supRow.appendChild(statusBadge(status));
      content.push(supRow);
    }

    // 物料列表
    if (items.length > 0) {
      items.forEach(item => {
        const row = el('div', 'a2ui-order-item-row');
        const info = el('div', 'a2ui-order-item-info');
        info.appendChild(el('div', 'a2ui-order-item-name', { textContent: esc(item.name) }));
        if (esc(item.specs)) {
          info.appendChild(el('div', 'a2ui-order-item-specs', { textContent: esc(item.specs) }));
        }
        row.appendChild(info);
        row.appendChild(el('span', 'a2ui-order-item-qty', { textContent: `×${safeNum(item.quantity).toFixed(0)} ${esc(item.unit)}` }));
        content.push(row);
      });
    }

    // 总额 + 交货日期
    content.push(el('hr', 'a2ui-divider'));
    const bottom = el('div', 'a2ui-order-bottom');
    const totalCol = el('div', 'a2ui-order-total');
    totalCol.appendChild(el('div', 'a2ui-order-total-label', { textContent: '订单总额' }));
    totalCol.appendChild(el('div', 'a2ui-order-total-amount', { textContent: fmtMoney(totalAmount) }));
    bottom.appendChild(totalCol);
    if (deliveryDate) {
      const dateCol = el('div', 'a2ui-order-date');
      dateCol.appendChild(el('div', 'a2ui-order-date-label', { textContent: '预计交货' }));
      dateCol.appendChild(el('div', 'a2ui-order-date-value', { textContent: deliveryDate }));
      bottom.appendChild(dateCol);
    }
    content.push(bottom);

    const actions = [createBtn('查看详情', 'view_order_detail', data, 'primary')];
    return cardWrapper(card, '采购订单', orderId ? `#${orderId}` : '', 'a2ui-accent-procurement', content, actions);
  };

  /**
   * 质检报告卡片
   */
  const renderQAReport = (card, data) => {
    const projectName = esc(data.project_name, '质检报告');
    const inspector = esc(data.inspector);
    const inspectionDate = esc(data.inspection_date);
    const fixDeadline = esc(data.fix_deadline);
    const overallResult = esc(data.overall_result);
    const passedCount = safeNum(data.passed_count);
    const failedCount = safeNum(data.failed_count);
    const checkpoints = safeList(data.checkpoints);

    const isPassed = overallResult === 'pass';
    const totalCount = passedCount + failedCount;
    const passRate = totalCount > 0 ? (passedCount / totalCount * 100).toFixed(0) : '0';

    const content = [];

    // 总体结果
    const resultBox = el('div', `a2ui-qa-result ${isPassed ? 'a2ui-qa-passed' : 'a2ui-qa-failed'}`);
    const resultText = isPassed ? '✅ 验收通过' : '❌ 需整改';
    resultBox.innerHTML = `
      <span class="a2ui-qa-result-icon">${isPassed ? '✅' : '❌'}</span>
      <div class="a2ui-qa-result-text">
        <div class="a2ui-qa-result-title">${resultText}</div>
        <div class="a2ui-qa-result-stats">通过 ${passedCount} / 不通过 ${failedCount}</div>
      </div>
      <span class="a2ui-qa-pct">${passRate}%</span>
    `;
    content.push(resultBox);

    // 整改期限
    if (!isPassed && fixDeadline) {
      const deadline = el('div', 'a2ui-qa-deadline');
      deadline.innerHTML = `⏰ 整改截止: <strong>${fixDeadline}</strong>`;
      content.push(deadline);
    }

    // 检查点列表
    if (checkpoints.length > 0) {
      content.push(el('div', 'a2ui-section-title', { textContent: '检查点' }));
      checkpoints.forEach(cp => {
        const name = esc(cp.name);
        const result = esc(cp.result);
        const standard = esc(cp.standard);
        const actual = esc(cp.actual);

        const icon = result === 'pass' ? '✅' : result === 'fail' ? '❌' : '❓';
        const row = el('div', 'a2ui-checkpoint-row');
        row.appendChild(el('span', 'a2ui-checkpoint-icon', { textContent: icon }));

        const info = el('div', 'a2ui-checkpoint-info');
        info.appendChild(el('div', 'a2ui-checkpoint-name', { textContent: name }));
        if (standard || actual) {
          info.appendChild(el('div', 'a2ui-checkpoint-detail', { textContent: `标准: ${standard}${actual ? ' · 实测: ' + actual : ''}` }));
        }
        row.appendChild(info);
        row.appendChild(statusBadge(result));
        content.push(row);
      });
    }

    const actions = [createBtn('查看详情', 'view_qa_detail', data, 'primary')];
    return cardWrapper(card, projectName, `${inspector} · ${inspectionDate}`, 'a2ui-accent-quality', content, actions);
  };

  /**
   * 结算汇总卡片
   */
  const renderSettlement = (card, data) => {
    const projectName = esc(data.project_name, '结算汇总');
    const totalAmount = safeNum(data.total_amount);
    const paidAmount = safeNum(data.paid_amount);
    const balanceAmount = safeNum(data.balance_amount);
    const paymentHistory = safeList(data.payment_history);
    const nextPayment = data.next_payment || {};

    const content = [];

    // 金额概览
    const moneyGrid = el('div', 'a2ui-money-grid');
    moneyGrid.appendChild(_moneyBox('合同总额', totalAmount, 'a2ui-money-total'));
    moneyGrid.appendChild(_moneyBox('已付金额', paidAmount, 'a2ui-money-paid'));
    moneyGrid.appendChild(_moneyBox('待付余额', balanceAmount, 'a2ui-money-balance'));
    content.push(moneyGrid);

    // 待付信息
    if (Object.keys(nextPayment).length > 0) {
      const nextPay = el('div', 'a2ui-next-payment');
      nextPay.innerHTML = `
        <span class="a2ui-next-pay-icon">💳</span>
        下一笔付款: <strong>${fmtMoney(safeNum(nextPayment.amount))}</strong>
        ${nextPayment.due_date ? `<div class="a2ui-next-pay-date">到期日: ${esc(nextPayment.due_date)}</div>` : ''}
        ${nextPayment.condition ? `<div class="a2ui-next-pay-condition">条件: ${esc(nextPayment.condition)}</div>` : ''}
      `;
      content.push(nextPay);
    }

    // 付款历史
    if (paymentHistory.length > 0) {
      content.push(el('div', 'a2ui-section-title', { textContent: '付款历史' }));
      paymentHistory.slice(0, 5).forEach(p => {
        const row = el('div', 'a2ui-payment-history-row');
        row.appendChild(el('span', 'a2ui-payment-date', { textContent: esc(p.date) }));
        row.appendChild(el('span', 'a2ui-payment-method', { textContent: esc(p.method) }));
        row.appendChild(el('span', 'a2ui-payment-amount', { textContent: fmtMoney(safeNum(p.amount)) }));
        row.appendChild(statusBadge(esc(p.status)));
        content.push(row);
      });
    }

    const actions = [createBtn('查看详情', 'view_settlement_detail', data, 'primary')];
    return cardWrapper(card, projectName, null, 'a2ui-accent-settlement', content, actions);
  };

  /** 金额盒子 */
  const _moneyBox = (label, amount, cls) => {
    const box = el('div', `a2ui-money-box ${cls}`);
    box.appendChild(el('div', 'a2ui-money-label', { textContent: label }));
    box.appendChild(el('div', 'a2ui-money-value', { textContent: `¥${Math.round(amount)}` }));
    return box;
  };

  /**
   * 材料详情卡片
   */
  const renderMaterial = (card, data) => {
    const name = esc(data.name, '材料详情');
    const category = esc(data.category);
    const specs = esc(data.specs);
    const ecoLevel = esc(data.eco_level);
    const unitPrice = safeNum(data.unit_price);
    const unit = esc(data.unit, '㎡');
    const supplier = esc(data.supplier);
    const stockStatus = esc(data.stock_status);
    const description = esc(data.description);
    const certifications = safeList(data.certifications);

    const content = [];

    // 价格行
    const priceRow = el('div', 'a2ui-material-price-row');
    priceRow.appendChild(el('span', 'a2ui-material-price', { textContent: fmtMoney(unitPrice) }));
    priceRow.appendChild(el('span', 'a2ui-material-unit', { textContent: `/${unit}` }));
    priceRow.appendChild(statusBadge(stockStatus));
    content.push(priceRow);

    // 规格信息
    if (specs) content.push(infoRow('规格', specs));
    if (ecoLevel) content.push(infoRow('环保等级', ecoLevel, { valueCls: 'a2ui-text-success', bold: true }));
    if (supplier) content.push(infoRow('供应商', supplier));

    // 认证标签
    if (certifications.length > 0) {
      const tagsRow = el('div', 'a2ui-tags-row');
      certifications.forEach(c => tagsRow.appendChild(tagChip(c, 'a2ui-tag-cert')));
      content.push(tagsRow);
    }

    // 描述
    if (description) {
      content.push(el('div', 'a2ui-material-desc', { textContent: description }));
    }

    const actions = [createBtn('查看详情', 'view_material_detail', data, 'primary')];
    return cardWrapper(card, name, category || null, 'a2ui-accent-master', content, actions);
  };

  /**
   * 系统告警卡片
   */
  const renderAlert = (card, data) => {
    const title = esc(data.title);
    const message = esc(data.message);
    const severity = esc(data.severity, 'info');
    const sourceAgent = esc(data.source_agent);
    const rawActions = safeList(data.actions);

    const sevInfo = _getSeverityStyle(severity);

    const wrapper = el('div', `a2ui-card a2ui-alert a2ui-alert-${severity}`, {
      role: 'alert',
      ariaLabel: `${sevInfo.label}: ${title}`,
    });

    // 头部
    const header = el('div', 'a2ui-alert-header');
    header.appendChild(el('span', 'a2ui-alert-badge', { textContent: sevInfo.label }));
    if (sourceAgent) {
      header.appendChild(el('span', 'a2ui-alert-source', { textContent: sourceAgent }));
    }
    wrapper.appendChild(header);

    // 标题
    if (title) {
      wrapper.appendChild(el('div', 'a2ui-alert-title', { textContent: title }));
    }

    // 消息
    if (message) {
      wrapper.appendChild(el('div', 'a2ui-alert-message', { textContent: message }));
    }

    // 操作按钮
    if (rawActions.length > 0) {
      const actionsRow = el('div', 'a2ui-alert-actions');
      rawActions.forEach(a => {
        const label = esc(a.label);
        if (!label) return;
        const btn = createBtn(label, esc(a.action), data, 'outline');
        btn.classList.add(`a2ui-alert-btn-${severity}`);
        actionsRow.appendChild(btn);
      });
      wrapper.appendChild(actionsRow);
    }

    return wrapper;
  };

  const _getSeverityStyle = (severity) => {
    switch (severity) {
      case 'critical': return { label: '严重', cls: 'critical' };
      case 'error': return { label: '错误', cls: 'error' };
      case 'warning': return { label: '警告', cls: 'warning' };
      default: return { label: '信息', cls: 'info' };
    }
  };

  /**
   * 未知类型卡片 (fallback)
   */
  const renderUnknown = (card, data) => {
    const type = esc(card.type, 'unknown');
    const wrapper = el('div', 'a2ui-card a2ui-unknown', { role: 'article' });
    const header = el('div', 'a2ui-card-header');
    header.appendChild(el('div', 'a2ui-card-title', { textContent: '未知卡片类型' }));
    wrapper.appendChild(header);
    const body = el('div', 'a2ui-card-body');
    body.appendChild(el('pre', 'a2ui-unknown-json', { textContent: JSON.stringify(data, null, 2) }));
    wrapper.appendChild(body);
    return wrapper;
  };

  // ═══════════════════════════════════════════
  // 公开 API
  // ═══════════════════════════════════════════

  /** 事件回调注册 */
  let _actionCallback = null;

  return {
    /**
     * 注册全局动作回调
     * @param {function} callback - (action: string, payload: object) => void
     */
    onAction(callback) {
      _actionCallback = callback;
    },

    /**
     * 内部触发动作
     */
    _dispatchAction(action, payload) {
      if (typeof _actionCallback === 'function') {
        _actionCallback(action, payload);
      }
    },

    /**
     * 将 A2UI JSON 渲染到指定容器
     * @param {object} card - A2UI 卡片 JSON
     * @param {HTMLElement} container - 目标DOM容器
     */
    render(card, container) {
      if (!card || !container) return;

      const type = card.type || 'unknown';
      const data = card.data || {};

      let element;
      switch (type) {
        case 'design_plan':
          element = renderDesignPlan(card, data);
          break;
        case 'budget_breakdown':
          element = renderBudget(card, data);
          break;
        case 'construction_progress':
          element = renderProgress(card, data);
          break;
        case 'procurement_order':
          element = renderProcurement(card, data);
          break;
        case 'qa_report':
          element = renderQAReport(card, data);
          break;
        case 'settlement_summary':
          element = renderSettlement(card, data);
          break;
        case 'material_card':
          element = renderMaterial(card, data);
          break;
        case 'alert_card':
          element = renderAlert(card, data);
          break;
        default:
          element = renderUnknown(card, data);
      }

      if (element) {
        container.appendChild(element);
        // 触发进入动画
        requestAnimationFrame(() => {
          element.classList.add('a2ui-visible');
        });
      }
    },

    /**
     * 批量渲染卡片列表到容器
     * @param {object[]} cards - A2UI 卡片 JSON 数组
     * @param {HTMLElement} container - 目标DOM容器
     * @param {boolean} clear - 是否先清空容器
     */
    renderBatch(cards, container, clear = false) {
      if (!container) return;
      if (clear) container.innerHTML = '';
      if (!Array.isArray(cards)) return;
      cards.forEach(card => this.render(card, container));
    },

    /**
     * 解析并渲染来自 SSE/Wire 格式的 A2UI 数据
     * @param {string} jsonStr - JSON 字符串，格式 {"version":"1.0.0","cards":[...]}
     * @param {HTMLElement} container
     */
    renderWire(jsonStr, container) {
      try {
        const parsed = JSON.parse(jsonStr);
        const cards = parsed.cards || [];
        this.renderBatch(cards, container, false);
      } catch (e) {
        console.error('[A2UI] 解析 Wire 格式失败:', e);
      }
    },
  };
})();
