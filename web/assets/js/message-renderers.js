/* ============================================
 * 索克家居 · 消息渲染器
 * 7 类消息卡片 + Agent 协作链路
 * ============================================ */

const MessageRenderers = {
  // 文本消息
  renderText(msg) {
    const agentInfo = msg.agent ? AgentRouter.getAgentInfo(msg.agent) : null;
    const isUser = !msg.agent || msg.is_self;
    const cls = isUser ? 'user' : `agent agent-${msg.agent || 'master'}`;
    const defaultName = isUser ? '我' : `${agentInfo.emoji} ${agentInfo.name} Agent`;
    const displayName = msg.display_name || defaultName;
    const meta = isUser
      ? `<div class="msg-meta"><strong>${this._escape(displayName)}</strong> · ${this._fmtTime(msg.timestamp)}</div>`
      : `<div class="msg-meta"><strong style="color:${agentInfo.color}">${this._escape(displayName)}</strong> · ${this._fmtTime(msg.timestamp)}</div>`;
    return `<div class="msg ${cls}">${meta}<div class="msg-bubble">${this._escape(msg.content)}</div>${this._renderCollab(msg)}</div>`;
  },

  // 任务卡片
  renderTaskCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo(msg.agent || 'construction');
    const tasks = (msg.payload.tasks || []).map(t => {
      const statusCls = t.status === 'done' ? 'done' : (t.status === 'in_progress' ? 'in-progress' : '');
      const icon = t.status === 'done' ? '✓' : (t.status === 'in_progress' ? '…' : '');
      return `<div class="task-item ${statusCls}"><span class="task-check">${icon}</span><span>${this._escape(t.name)}</span></div>`;
    }).join('');
    return `<div class="msg agent agent-${msg.agent || 'construction'}">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">📋 ${this._escape(msg.payload.title || '今日任务')}</div>
        <div class="task-list">${tasks}</div>
      </div>
      ${this._renderCollab(msg)}
    </div>`;
  },

  // 照片消息
  renderPhotoMessage(msg) {
    const isUser = msg.is_self || (!msg.agent && msg.from === 'user');
    const cls = isUser ? 'user' : `agent agent-${msg.agent || 'construction'}`;
    const photos = (msg.payload.photos || []).map(p =>
      `<div class="photo-thumb" style="background-image:url('${this._escape(p.url)}')" role="img" aria-label="${this._escape(p.caption || '现场照片')}" tabindex="0"></div>`
    ).join('');
    return `<div class="msg ${cls}">
      <div class="msg-meta"><strong>${isUser ? '我' : (AgentRouter.getAgentInfo(msg.agent).name + ' Agent')}</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-bubble">
        ${msg.payload.note ? `<div>${this._escape(msg.payload.note)}</div>` : ''}
        <div class="photo-grid">${photos}</div>
      </div>
    </div>`;
  },

  // 审批卡片
  renderApprovalCard(msg, currentUserRole) {
    const agentInfo = AgentRouter.getAgentInfo('master');
    const payload = msg.payload || {};
    const showApprove = currentUserRole === 'owner';
    const actionBtn = showApprove
      ? `<div class="approval-actions">
          <button class="approval-btn approve" data-approval-id="${payload.id}" data-decision="approve">同意</button>
          <button class="approval-btn reject" data-approval-id="${payload.id}" data-decision="reject">整改</button>
        </div>`
      : `<div class="approval-actions">
          <button class="approval-btn ack" data-approval-id="${payload.id}" data-decision="ack">已知悉</button>
        </div>`;
    return `<div class="msg agent agent-master">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}${payload.mention ? ' @' + payload.mention : ''}</div>
      <div class="msg-card" style="border:1px solid var(--accent)">
        <div class="msg-card-title">⚠ 待决策 · ${this._escape(payload.title || '')}</div>
        ${payload.problem ? `<div class="msg-card-row"><span>问题</span><strong>${this._escape(payload.problem)}</strong></div>` : ''}
        ${payload.impact_cost ? `<div class="msg-card-row"><span>预算影响</span><strong style="color:var(--warning)">+¥${payload.impact_cost}</strong></div>` : ''}
        ${payload.impact_days ? `<div class="msg-card-row"><span>工期影响</span><strong>+${payload.impact_days} 天</strong></div>` : ''}
        ${payload.detail ? `<div style="font-size:11px;color:var(--text-secondary);margin-top:6px">${this._escape(payload.detail)}</div>` : ''}
        ${actionBtn}
      </div>
    </div>`;
  },

  // 文档消息
  renderDocumentMessage(msg) {
    const agentInfo = AgentRouter.getAgentInfo(msg.agent || 'design');
    const f = msg.payload || {};
    return `<div class="msg agent agent-${msg.agent || 'design'}">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">📎 ${this._escape(f.name || '文档')}</div>
        ${f.size ? `<div class="msg-card-row"><span>大小</span><strong>${this._escape(f.size)}</strong></div>` : ''}
        <a href="${this._escape(f.url || '#')}" target="_blank" rel="noopener" style="display:block;margin-top:6px;font-size:11px;color:var(--accent);text-decoration:none">查看 →</a>
      </div>
    </div>`;
  },

  // 预算卡片
  renderBudgetCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('budget');
    const p = msg.payload || {};
    const percent = p.total ? Math.round((p.spent || 0) / p.total * 100) : 0;
    return `<div class="msg agent agent-budget">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">📊 预算概览</div>
        <div class="msg-card-row"><span>总预算</span><strong>¥${(p.total || 0).toLocaleString()}</strong></div>
        <div class="msg-card-row"><span>已支出</span><strong>¥${(p.spent || 0).toLocaleString()}（${percent}%）</strong></div>
        <div class="msg-card-row"><span>剩余</span><strong style="color:var(--success)">¥${(p.remaining || 0).toLocaleString()}</strong></div>
        <div class="progress-bar"><div class="progress-bar-fill" style="width:${percent}%"></div></div>
        ${p.note ? `<div style="font-size:10px;color:var(--text-muted);margin-top:4px">${this._escape(p.note)}</div>` : ''}
      </div>
    </div>`;
  },

  // F15 支付进度卡片
  renderPaymentCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('settlement');
    const p = msg.payload || {};
    const stages = p.stages || p.schedule || [];
    const totalPaid = p.total_paid != null ? p.total_paid : stages.reduce((s, st) => s + (st.paid_amount || 0), 0);
    const totalAmount = p.total_amount != null ? p.total_amount : stages.reduce((s, st) => s + (st.total_amount || 0), 0);
    const percent = totalAmount > 0 ? Math.round(totalPaid / totalAmount * 100) : 0;

    const STAGE_LABEL = { deposit: '首付', progress: '进度款', final: '尾款', warranty: '质保金' };
    const STATUS_ICON = { paid: '✓', partial: '◐', pending: '○', overdue: '!' };
    const STATUS_CLS = { paid: 'paid', partial: 'partial', pending: 'pending', overdue: 'overdue' };

    const stageRows = stages.map(st => {
      const label = STAGE_LABEL[st.stage_code] || st.stage_code || st.milestone_code || '阶段';
      const icon = STATUS_ICON[st.status] || '○';
      const cls = STATUS_CLS[st.status] || 'pending';
      const stagePercent = st.total_amount > 0 ? Math.round((st.paid_amount || 0) / st.total_amount * 100) : 0;
      return `<div class="payment-stage ${cls}">
        <span class="payment-stage-icon">${icon}</span>
        <span class="payment-stage-name">${this._escape(label)}</span>
        <span class="payment-stage-amount">¥${(st.paid_amount || 0).toLocaleString()} / ¥${(st.total_amount || 0).toLocaleString()}</span>
        <span class="payment-stage-percent">${stagePercent}%</span>
      </div>`;
    }).join('');

    return `<div class="msg agent agent-settlement">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">💳 支付进度</div>
        <div class="msg-card-row"><span>已付</span><strong style="color:var(--success)">¥${(totalPaid || 0).toLocaleString()}</strong></div>
        <div class="msg-card-row"><span>总额</span><strong>¥${(totalAmount || 0).toLocaleString()}</strong></div>
        <div class="msg-card-row"><span>进度</span><strong>${percent}%</strong></div>
        <div class="progress-bar"><div class="progress-bar-fill" style="width:${percent}%"></div></div>
        ${stageRows ? `<div class="payment-stages">${stageRows}</div>` : ''}
        ${p.invoice_count ? `<div class="msg-card-row"><span>已开票</span><strong>${p.invoice_count} 张 · ¥${(p.invoiced_amount || 0).toLocaleString()}</strong></div>` : ''}
        ${p.note ? `<div style="font-size:10px;color:var(--text-muted);margin-top:4px">${this._escape(p.note)}</div>` : ''}
      </div>
    </div>`;
  },

  // 比价卡片
  renderQuoteCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('procurement');
    const p = msg.payload || {};
    const quotes = (p.quotes || []).map(q =>
      `<div class="msg-card-row"><span>${this._escape(q.supplier)}</span><strong>¥${(q.price || 0).toLocaleString()}${q.recommended ? ' ⭐' : ''}</strong></div>`
    ).join('');
    return `<div class="msg agent agent-procurement">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">🛒 ${this._escape(p.product || '比价报告')}</div>
        ${quotes}
        <div class="msg-card-row"><span>推荐</span><strong style="color:var(--accent)">${this._escape(p.recommendation || '')}</strong></div>
      </div>
    </div>`;
  },

  // BOM 物料清单卡片（F6/F7）
  renderBOMCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('procurement');
    const p = msg.payload || {};
    const items = p.items || [];
    const rows = items.slice(0, 8).map((it, idx) => {
      const mat = it.material || {};
      const cat = mat.category || {};
      return `<div class="msg-card-row">
        <span>${idx + 1}. ${this._escape(mat.name || mat.sku || '物料')} <small style="color:var(--text-muted)">[${this._escape(cat.name || cat.code || '')}]</small></span>
        <strong>×${it.quantity} ${this._escape(mat.unit || '')} · ¥${(it.total_price || 0).toLocaleString()}</strong>
      </div>`;
    }).join('');
    const more = items.length > 8 ? `<div style="font-size:10px;color:var(--text-muted);margin-top:4px">… 共 ${items.length} 项，<a href="#" data-bom-export="${this._escape(p.project_id || '')}" style="color:var(--accent);text-decoration:none">导出 Excel</a></div>` : (p.project_id ? `<div style="font-size:10px;margin-top:4px"><a href="#" data-bom-export="${this._escape(p.project_id)}" style="color:var(--accent);text-decoration:none">📥 导出 Excel</a></div>` : '');
    return `<div class="msg agent agent-procurement">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">📦 ${this._escape(p.title || 'BOM 物料清单')}</div>
        ${rows || '<div class="msg-card-row"><span>暂无物料</span></div>'}
        <div class="msg-card-row"><span>合计</span><strong style="color:var(--warning)">¥${(p.total_price || 0).toLocaleString()}</strong></div>
        ${more}
      </div>
    </div>`;
  },

  // 结算卡片（F14）
  renderSettlementCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('settlement');
    const p = msg.payload || {};
    const lines = p.lines || [];
    const linesHtml = lines.slice(0, 6).map((it, idx) => {
      const anomalyBadge = it.is_anomaly
        ? `<small style="color:var(--warning);margin-left:4px">⚠ ${this._escape(it.anomaly_type || '异常')}</small>`
        : '';
      const variance = (it.actual_amount || 0) - (it.contract_amount || 0) - (it.change_amount || 0);
      const varianceStr = variance !== 0
        ? `<small style="color:${variance > 0 ? 'var(--warning)' : 'var(--success)'}"> 偏差 ¥${variance.toLocaleString()}</small>`
        : '';
      return `<div class="msg-card-row">
        <span>${idx + 1}. ${this._escape(it.name || '未命名')}${anomalyBadge}${varianceStr}</span>
        <strong>¥${(it.actual_amount || it.contract_amount || 0).toLocaleString()}</strong>
      </div>`;
    }).join('');
    const moreLines = lines.length > 6 ? `<div style="font-size:10px;color:var(--text-muted);margin-top:4px">… 共 ${lines.length} 项</div>` : '';
    const statusText = {
      draft: '草稿', confirmed: '已确认', review: '待复核', flagged: '已标记异常',
    }[p.status] || p.status || '草稿';
    const reviewBadge = p.review_required
      ? `<div class="msg-card-row"><span>复核状态</span><strong style="color:var(--warning)">⚠ 需人工复核</strong></div>`
      : '';
    const anomalyBadge = p.critical_anomaly_count > 0
      ? `<div class="msg-card-row"><span>异常</span><strong style="color:var(--warning)">${p.critical_anomaly_count} 严重 / ${p.anomaly_count} 总</strong></div>`
      : (p.anomaly_count > 0 ? `<div class="msg-card-row"><span>异常</span><strong>${p.anomaly_count} 警告</strong></div>` : '');
    const deductionRow = p.suggested_deduction > 0
      ? `<div class="msg-card-row"><span>建议扣款</span><strong style="color:var(--warning)">-¥${(p.suggested_deduction || 0).toLocaleString()}</strong></div>`
      : '';
    const exportLink = p.project_id
      ? `<div style="font-size:10px;margin-top:4px"><a href="#" data-settlement-export="${this._escape(p.project_id)}" style="color:var(--accent);text-decoration:none">📤 导出对账单</a></div>`
      : '';
    const confirmBtn = (p.status === 'draft' || p.status === 'flagged') && !p.review_required && p.project_id
      ? `<div class="approval-actions">
          <button class="approval-btn approve" data-settlement-confirm="${this._escape(p.project_id)}">确认结算</button>
        </div>`
      : '';
    const reviewBtn = p.review_required && p.project_id
      ? `<div class="approval-actions">
          <button class="approval-btn approve" data-settlement-approve-review="${this._escape(p.project_id)}">通过复核</button>
        </div>`
      : '';
    return `<div class="msg agent agent-settlement">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">🧾 结算单 · ${this._escape(p.milestone || 'completion')} · ${this._escape(statusText)}</div>
        <div class="msg-card-row"><span>合同金额</span><strong>¥${(p.contract_amount || 0).toLocaleString()}</strong></div>
        <div class="msg-card-row"><span>实际金额</span><strong>¥${(p.actual_amount || 0).toLocaleString()}</strong></div>
        <div class="msg-card-row"><span>应付金额</span><strong style="color:var(--accent)">¥${(p.payable_amount || 0).toLocaleString()}</strong></div>
        ${anomalyBadge}
        ${deductionRow}
        ${reviewBadge}
        ${linesHtml ? `<div style="margin-top:6px;border-top:1px dashed var(--border);padding-top:6px">${linesHtml}</div>` : ''}
        ${moreLines}
        ${exportLink}
        ${confirmBtn}
        ${reviewBtn}
      </div>
    </div>`;
  },

  // 里程碑结算卡片（F14）
  renderMilestoneCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('settlement');
    const p = msg.payload || {};
    return `<div class="msg agent agent-settlement">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">🧾 ${this._escape(p.milestone_name || '里程碑结算')}</div>
        <div class="msg-card-row"><span>合同金额</span><strong>¥${(p.contract_amount || 0).toLocaleString()}</strong></div>
        <div class="msg-card-row"><span>付款比例</span><strong>${((p.payment_ratio || 0) * 100).toFixed(0)}%</strong></div>
        <div class="msg-card-row"><span>基础应付</span><strong>¥${(p.base_payable || 0).toLocaleString()}</strong></div>
        ${p.change_amount ? `<div class="msg-card-row"><span>变更</span><strong>+¥${(p.change_amount || 0).toLocaleString()}</strong></div>` : ''}
        ${p.deduction_amount ? `<div class="msg-card-row"><span>扣款</span><strong>-¥${(p.deduction_amount || 0).toLocaleString()}</strong></div>` : ''}
        ${p.paid_amount ? `<div class="msg-card-row"><span>已付</span><strong>-¥${(p.paid_amount || 0).toLocaleString()}</strong></div>` : ''}
        <div class="msg-card-row"><span>本次应付</span><strong style="color:var(--accent)">¥${(p.total_payable || 0).toLocaleString()}</strong></div>
        ${p.description ? `<div style="font-size:10px;color:var(--text-muted);margin-top:4px">${this._escape(p.description)}</div>` : ''}
      </div>
    </div>`;
  },

  // 采购订单卡片
  renderOrderCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('procurement');
    const o = msg.payload || {};
    const lines = (o.lines || []).map((l, idx) =>
      `<div class="msg-card-row"><span>${idx + 1}. ${this._escape(l.material_name || l.material_id || '物料')}</span><strong>×${l.quantity} · ¥${(l.total_price || 0).toLocaleString()}</strong></div>`
    ).join('');
    const statusMap = {
      draft: '草稿', pending: '待确认', confirmed: '已确认',
      shipped: '已发货', delivered: '已送达', completed: '已完成', cancelled: '已取消',
    };
    const statusText = statusMap[o.status] || o.status || '草稿';
    const statusColor = o.status === 'completed' ? 'var(--success)' :
                        o.status === 'cancelled' ? 'var(--danger)' :
                        o.status === 'shipped' || o.status === 'delivered' ? 'var(--accent)' : 'var(--warning)';
    return `<div class="msg agent agent-procurement">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">🛍️ 采购订单 ${o.id ? '<small style="color:var(--text-muted)">#' + this._escape(o.id.slice(0, 8)) + '</small>' : ''}</div>
        ${o.supplier_name ? `<div class="msg-card-row"><span>供应商</span><strong>${this._escape(o.supplier_name)}</strong></div>` : ''}
        ${lines}
        <div class="msg-card-row"><span>合计</span><strong style="color:var(--warning)">¥${(o.total_amount || 0).toLocaleString()}</strong></div>
        <div class="msg-card-row"><span>状态</span><strong style="color:${statusColor}">${statusText}</strong></div>
        ${o.note ? `<div style="font-size:10px;color:var(--text-muted);margin-top:4px">${this._escape(o.note)}</div>` : ''}
      </div>
    </div>`;
  },

  // 采购订单列表卡片（多订单汇总）
  renderOrderListCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('procurement');
    const p = msg.payload || {};
    const orders = p.orders || [];
    if (orders.length === 0) return '';
    const cards = orders.slice(0, 5).map(o => {
      const statusMap = {
        draft: '草稿', pending: '待确认', confirmed: '已确认',
        shipped: '已发货', delivered: '已送达', completed: '已完成', cancelled: '已取消',
      };
      const statusText = statusMap[o.status] || o.status || '草稿';
      const statusColor = o.status === 'completed' ? 'var(--success)' :
                          o.status === 'cancelled' ? 'var(--danger)' :
                          o.status === 'shipped' || o.status === 'delivered' ? 'var(--accent)' : 'var(--warning)';
      return `<div class="msg-card-row">
        <span>#${this._escape((o.id || '').slice(0, 8))} ${o.supplier_name ? '· ' + this._escape(o.supplier_name) : ''}</span>
        <strong style="color:${statusColor}">¥${(o.total_amount || 0).toLocaleString()} · ${statusText}</strong>
      </div>`;
    }).join('');
    const more = orders.length > 5 ? `<div style="font-size:10px;color:var(--text-muted);margin-top:4px">… 共 ${orders.length} 个订单</div>` : '';
    return `<div class="msg agent agent-procurement">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">📋 采购订单列表</div>
        ${cards}
        ${more}
      </div>
    </div>`;
  },

  // 担保支付卡片（F34）
  renderEscrowCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('procurement');
    const p = msg.payload || {};
    const STATUS_LABEL = {
      pending: '待付款',
      buyer_paid: '买家已付款',
      supplier_received: '已释放给供应商',
      refunded: '已退款',
      disputed: '争议中',
    };
    const statusLabel = STATUS_LABEL[p.status] || p.status || '未知';
    const statusColor = p.status === 'supplier_received' ? 'var(--success)'
      : (p.status === 'refunded' ? 'var(--warning)'
        : (p.status === 'disputed' ? 'var(--warning)' : 'var(--accent)'));
    return `<div class="msg agent agent-procurement">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">🛡 担保支付 · ${this._escape(p.escrow_no || '')}</div>
        <div class="msg-card-row"><span>订单金额</span><strong>¥${(p.total_amount || 0).toLocaleString()}</strong></div>
        <div class="msg-card-row"><span>担保手续费</span><strong>¥${(p.escrow_fee || 0).toLocaleString()}</strong></div>
        <div class="msg-card-row"><span>状态</span><strong style="color:${statusColor}">${this._escape(statusLabel)}</strong></div>
        ${p.dispute_reason ? `<div class="msg-card-row"><span>争议原因</span><strong>${this._escape(p.dispute_reason)}</strong></div>` : ''}
      </div>
    </div>`;
  },

  // 物流追踪卡片（F34）
  renderLogisticsCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('procurement');
    const p = msg.payload || {};
    const STATUS_LABEL = {
      pending: '待发货',
      shipped: '已发货',
      in_transit: '运输中',
      delivered: '已签收',
      exception: '异常',
    };
    const statusLabel = STATUS_LABEL[p.status] || p.status || '未知';
    const history = (p.tracking_history || []).slice(-3).map(h =>
      `<div class="msg-card-row"><span>${this._escape(h.location || '—')}</span><strong>${this._escape(h.description || h.status || '')}</strong></div>`
    ).join('');
    const carrierLabel = { sf_express: '顺丰', yt_express: '圆通', zto: '中通', sto: '申通', jd_logistics: '京东物流', debon: '德邦', self_delivery: '自送' }[p.carrier] || p.carrier || '';
    return `<div class="msg agent agent-procurement">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">🚚 物流追踪 · ${this._escape(p.tracking_no || '')}</div>
        <div class="msg-card-row"><span>承运商</span><strong>${this._escape(carrierLabel)}</strong></div>
        ${p.ship_from ? `<div class="msg-card-row"><span>发货地</span><strong>${this._escape(p.ship_from)}</strong></div>` : ''}
        ${p.ship_to ? `<div class="msg-card-row"><span>收货地</span><strong>${this._escape(p.ship_to)}</strong></div>` : ''}
        <div class="msg-card-row"><span>状态</span><strong style="color:var(--accent)">${this._escape(statusLabel)}</strong></div>
        ${history}
      </div>
    </div>`;
  },

  // 样品索要卡片（F34）
  renderSampleCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('procurement');
    const p = msg.payload || {};
    const STATUS_LABEL = {
      requested: '已申请',
      shipped: '已寄出',
      received: '已收到',
      rejected: '已拒绝',
    };
    const statusLabel = STATUS_LABEL[p.status] || p.status || '未知';
    const statusColor = p.status === 'received' ? 'var(--success)'
      : (p.status === 'rejected' ? 'var(--warning)' : 'var(--accent)');
    return `<div class="msg agent agent-procurement">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">🎨 样品索要 · ${this._escape(p.sample_type || '实物')}</div>
        ${p.material_name ? `<div class="msg-card-row"><span>物料</span><strong>${this._escape(p.material_name)}</strong></div>` : ''}
        <div class="msg-card-row"><span>状态</span><strong style="color:${statusColor}">${this._escape(statusLabel)}</strong></div>
        ${p.notes ? `<div class="msg-card-row"><span>备注</span><strong>${this._escape(p.notes)}</strong></div>` : ''}
      </div>
    </div>`;
  },

  // 系统通知
  renderSystemNotice(msg) {
    return `<div class="date-separator"><span>${this._escape(msg.content || '')}</span></div>`;
  },

  // ── 新增：任务申领卡片（设计师/工长选择） ──

  renderTaskClaimCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('master');
    const p = msg.payload || {};
    const candidates = (p.candidates || []).sort((a, b) => b.composite_score - a.composite_score).map((c, idx) => {
      const medal = idx === 0 ? '🥇' : (idx === 1 ? '🥈' : (idx === 2 ? '🥉' : `${idx + 1}`));
      const scoreBreakdown = c.score_breakdown || {};
      return `<div class="candidate-item" data-candidate-id="${this._escape(c.user_id)}">
        <span class="candidate-rank">${medal}</span>
        <span class="candidate-name">${this._escape(c.user_name || '候选人')}</span>
        <span class="candidate-score">⭐ ${(c.rating_score || 0).toFixed(1)}</span>
        <span class="candidate-points">积分 ${scoreBreakdown.points || 0}</span>
        <span class="candidate-exp">经验 ${scoreBreakdown.experience_years || 0}年</span>
        <span class="candidate-done">完成 ${scoreBreakdown.completed_projects || 0}个</span>
        <button class="candidate-select-btn" data-candidate-id="${this._escape(c.user_id)}" data-task-id="${this._escape(p.task_id || '')}">选择</button>
      </div>`;
    }).join('');

    const claimRoleLabel = { designer: '设计师', contractor: '工长', supplier: '供应商' };
    const roleLabel = claimRoleLabel[p.claim_role] || p.claim_role || '未知';

    return `<div class="msg agent agent-master">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card" style="border:1px solid var(--accent)">
        <div class="msg-card-title">📋 ${this._escape(p.title || '任务待分配')}</div>
        ${p.description ? `<div class="msg-card-desc">${this._escape(p.description)}</div>` : ''}
        <div class="msg-card-row"><span>任务类型</span><strong>${this._escape(roleLabel)}</strong></div>
        <div class="msg-card-row"><span>项目</span><strong>${this._escape(p.project_name || '—')}</strong></div>
        <div class="msg-card-row"><span>申领人数</span><strong>${candidates.length}人</strong></div>
        ${candidates ? `<div class="candidate-list">${candidates}</div>` : '<div style="font-size:11px;color:var(--text-muted);padding:8px 0">暂无申领者</div>'}
        ${p.claim_deadline ? `<div class="msg-card-row"><span>截止</span><strong>${this._escape(p.claim_deadline)}</strong></div>` : ''}
      </div>
    </div>`;
  },

  // ── 新增：产品发布卡片（供应商发布产品/服务） ──

  renderProductCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('procurement');
    const p = msg.payload || {};
    const tags = (p.tags || []).map(t => `<span class="product-tag">#${this._escape(t)}</span>`).join(' ');

    return `<div class="msg agent agent-procurement">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card product-card">
        <div class="msg-card-title">📦 ${this._escape(p.name || '产品')}</div>
        <div class="msg-card-row"><span>类别</span><strong>${this._escape(p.category || '—')}</strong></div>
        ${p.price_range ? `<div class="msg-card-row"><span>价格</span><strong style="color:var(--warning)">${this._escape(p.price_range)}</strong></div>` : ''}
        ${p.description ? `<div class="product-desc">${this._escape(p.description)}</div>` : ''}
        ${tags ? `<div class="product-tags">${tags}</div>` : ''}
        ${p.supplier_name ? `<div class="msg-card-row"><span>供应商</span><strong>${this._escape(p.supplier_name)}</strong></div>` : ''}
        <div class="product-actions">
          <button class="approval-btn approve" data-product-id="${this._escape(p.product_id || '')}" data-product-action="publish">确认发布</button>
          <button class="approval-btn" data-product-id="${this._escape(p.product_id || '')}" data-product-action="edit">编辑</button>
        </div>
      </div>
    </div>`;
  },

  // ── 新增：总控任务协调卡片 ──

  renderOrchestratorTaskCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('master');
    const p = msg.payload || {};
    const taskStatusMap = {
      pending: { label: '待处理', color: 'var(--text-muted)' },
      claimed: { label: '已申领', color: 'var(--accent)' },
      in_progress: { label: '进行中', color: 'var(--warning)' },
      completed: { label: '已完成', color: 'var(--success)' },
      failed: { label: '失败', color: 'var(--danger)' },
    };
    const status = taskStatusMap[p.status] || { label: p.status || '未知', color: 'var(--text-muted)' };

    return `<div class="msg agent agent-master">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card">
        <div class="msg-card-title">🔗 ${this._escape(p.title || '任务更新')}</div>
        <div class="msg-card-row"><span>任务类型</span><strong>${this._escape(p.task_type || '—')}</strong></div>
        <div class="msg-card-row"><span>状态</span><strong style="color:${status.color}">${status.label}</strong></div>
        ${p.assigned_user_name ? `<div class="msg-card-row"><span>负责人</span><strong>${this._escape(p.assigned_user_name)}</strong></div>` : ''}
        ${p.priority ? `<div class="msg-card-row"><span>优先级</span><strong>${'⭐'.repeat(Math.min(p.priority, 5))}</strong></div>` : ''}
      </div>
    </div>`;
  },

  // ── 新增：积分展示卡片 ──

  renderPointsCard(msg) {
    const agentInfo = AgentRouter.getAgentInfo('master');
    const p = msg.payload || {};
    const levelMap = {
      bronze: { label: '🥉 铜牌', color: '#CD7F32' },
      silver: { label: '🥈 银牌', color: '#C0C0C0' },
      gold: { label: '🥇 金牌', color: '#FFD700' },
      platinum: { label: '💎 铂金', color: '#E5E4E2' },
      diamond: { label: '👑 钻石', color: '#B9F2FF' },
    };
    const level = levelMap[p.level] || { label: p.level || '—', color: 'var(--text-secondary)' };

    return `<div class="msg agent agent-master">
      <div class="msg-meta"><strong style="color:${agentInfo.color}">${agentInfo.emoji} ${agentInfo.name} Agent</strong> · ${this._fmtTime(msg.timestamp)}</div>
      <div class="msg-card points-card">
        <div class="msg-card-title">💰 积分信息</div>
        <div class="points-level" style="color:${level.color}">${level.label}</div>
        <div class="msg-card-row"><span>当前积分</span><strong style="color:var(--accent)">${(p.balance || 0).toLocaleString()}</strong></div>
        <div class="msg-card-row"><span>累计获得</span><strong>${(p.total_earned || 0).toLocaleString()}</strong></div>
        <div class="msg-card-row"><span>年度获得</span><strong>${(p.year_earned || 0).toLocaleString()}</strong></div>
        ${p.rank ? `<div class="msg-card-row"><span>年度排名</span><strong>第${p.rank}名</strong></div>` : ''}
        ${p.description ? `<div class="points-desc">${this._escape(p.description)}</div>` : ''}
      </div>
    </div>`;
  },

  // ── 营销叙事卡片（落地页专用，3 种变体：brand/stat/cta） ──
  renderNarrativeCard(msg) {
    const p = msg.payload || {};
    const variant = p.variant || 'brand';
    const tag = p.tag || '演示';
    const senderName = p.display_name || '🏠 索克家居';

    // 变体：品牌主张
    if (variant === 'brand') {
      return `<div class="msg agent agent-master">
        <div class="msg-meta"><strong style="color:var(--agent-master)">${this._escape(senderName)}</strong> · ${this._fmtTime(msg.timestamp)}</div>
        <div class="msg-card narrative-card">
          <span class="narrative-tag">${this._escape(tag)}</span>
          <div class="narrative-title">${this._escape(p.title || '')}</div>
          ${p.body ? `<div class="narrative-body">${this._escape(p.body)}</div>` : ''}
          ${p.agents ? `<div class="narrative-agents">${p.agents.map(a => {
            const info = AgentRouter.getAgentInfo(a);
            return `<span class="narrative-agent-chip" style="border-color:${info.color}">${info.emoji} ${info.name}</span>`;
          }).join('')}</div>` : ''}
        </div>
      </div>`;
    }

    // 变体：核心数据
    if (variant === 'stat') {
      return `<div class="msg agent agent-master">
        <div class="msg-meta"><strong style="color:var(--agent-master)">${this._escape(senderName)}</strong> · ${this._fmtTime(msg.timestamp)}</div>
        <div class="msg-card narrative-card narrative-stat">
          <span class="narrative-tag">${this._escape(tag)}</span>
          <div class="narrative-title">${this._escape(p.title || '')}</div>
          ${p.stat_value != null ? `<div class="narrative-stat-value">${this._escape(p.stat_value)}</div>` : ''}
          ${p.stat_label ? `<div class="narrative-stat-label">${this._escape(p.stat_label)}</div>` : ''}
          ${p.body ? `<div class="narrative-body">${this._escape(p.body)}</div>` : ''}
        </div>
      </div>`;
    }

    // 变体：转化引导 CTA
    if (variant === 'cta') {
      return `<div class="msg agent agent-master">
        <div class="msg-meta"><strong style="color:var(--agent-master)">${this._escape(senderName)}</strong> · ${this._fmtTime(msg.timestamp)}</div>
        <div class="msg-card narrative-card narrative-cta">
          <span class="narrative-tag">${this._escape(tag)}</span>
          <div class="narrative-title">${this._escape(p.title || '')}</div>
          ${p.body ? `<div class="narrative-body">${this._escape(p.body)}</div>` : ''}
          ${p.cta_text ? `<button class="btn btn-primary narrative-cta-btn" data-narrative-cta="${this._escape(p.cta_action || 'login')}" ${p.cta_href ? `data-href="${this._escape(p.cta_href)}"` : ''}>${this._escape(p.cta_text)}</button>` : ''}
        </div>
      </div>`;
    }

    return '';
  },

  // 通用错误状态渲染
  renderSystemMessage(type, text) {
    const variants = {
      error: { icon: '⚠️', color: 'var(--danger)' },
      warning: { icon: '📡', color: 'var(--warning)' },
      success: { icon: '✅', color: 'var(--success)' },
      info: { icon: 'ℹ️', color: 'var(--info)' },
    };
    const v = variants[type] || variants.info;
    return `<div class="msg system" style="text-align:center;margin:8px 12px">
      <div class="msg-bubble" style="color:${v.color};font-size:12px;background:${v.color}10;border:1px solid ${v.color}30;padding:8px 16px">
        ${v.icon} ${text}
      </div></div>`;
  },

  // Agent 协作链路（消息底部）
  _renderCollab(msg) {
    if (!msg.collaboration || !msg.collaboration.length) return '';
    const links = msg.collaboration.map(c =>
      `↳ 已 @${AgentRouter.getAgentInfo(c.agent).emoji} ${AgentRouter.getAgentInfo(c.agent).name} Agent ${c.action || ''}`
    ).join('<br>');
    return `<div class="msg-collab" tabindex="0" role="button" aria-label="展开协作详情">${links}</div>`;
  },

  // 按消息类型分发
  render(msg, currentUserRole) {
    switch (msg.type) {
      case 'text': return this.renderText(msg);
      case 'task_card': return this.renderTaskCard(msg);
      case 'photo': return this.renderPhotoMessage(msg);
      case 'approval': return this.renderApprovalCard(msg, currentUserRole);
      case 'document': return this.renderDocumentMessage(msg);
      case 'budget': return this.renderBudgetCard(msg);
      case 'payment': return this.renderPaymentCard(msg);
      case 'quote': return this.renderQuoteCard(msg);
      case 'bom': return this.renderBOMCard(msg);
      case 'procurement_order': return this.renderOrderCard(msg);
      case 'procurement_orders': return this.renderOrderListCard(msg);
      case 'escrow': return this.renderEscrowCard(msg);
      case 'logistics': return this.renderLogisticsCard(msg);
      case 'sample': return this.renderSampleCard(msg);
      case 'settlement': return this.renderSettlementCard(msg);
      case 'milestone_settlement': return this.renderMilestoneCard(msg);
      case 'system': return this.renderSystemNotice(msg);
      case 'task_claim': return this.renderTaskClaimCard(msg);
      case 'product_card': return this.renderProductCard(msg);
      case 'orchestrator_task': return this.renderOrchestratorTaskCard(msg);
      case 'points_card': return this.renderPointsCard(msg);
      case 'narrative': return this.renderNarrativeCard(msg);
      default: return this.renderText(msg);
    }
  },

  // 工具
  _fmtTime(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  },
  _escape(s) {
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  },
};

// 暴露到全局
window.MessageRenderers = MessageRenderers;
