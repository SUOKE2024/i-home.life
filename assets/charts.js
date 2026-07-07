// assets/charts.js — 索克家居 PRD 竞品能力热力图
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var bg = style.getPropertyValue('--bg').trim();

  var chartEl = document.getElementById('chart-competitor');
  if (chartEl) {
    var chart = echarts.init(chartEl, null, { renderer: 'svg' });

    var competitors = ['酷家乐', '住小帮', 'Shapr3D', 'Planner 5D', 'MagicPlan', 'Procore', '索克家居'];
    var capabilities = [
      'AR 空间测量',
      '2D 精确CAD',
      '3D 建模',
      '平立剖自动生成',
      '效果图渲染',
      '物料清单(BOM)',
      'AI 预算管理',
      'AI 结算对账',
      '厨卫设计器',
      '电器点位规划',
      '土建工程量',
      '硬装设计',
      '软装搭配',
      '家具/灯具选型',
      '智能家居方案',
      '供应商比价采购',
      '施工进度管理',
      'AI 质量验收',
      '工程队匹配',
      'AI Agent 自治',
      '多模态交互',
      '鸿蒙平板',
      '移动端原生'
    ];

    // 0=缺失, 1=部分具备, 2=完全具备
    var data = [
      [0,1,2,1,2,1,0,0,0,0,0,1,1,1,0,0,0,0,0,0,0,0,0],  // 酷家乐
      [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],  // 住小帮
      [0,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2],  // Shapr3D
      [0,1,2,0,1,0,0,0,0,0,0,1,2,2,0,0,0,0,0,0,0,0,2],  // Planner 5D
      [2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2],  // MagicPlan
      [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2,0,1,0,0,0,1],  // Procore
      [2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2],  // 索克家居
    ];

    var seriesData = [];
    competitors.forEach(function(comp, ci) {
      capabilities.forEach(function(cap, cai) {
        seriesData.push([cai, ci, data[ci][cai]]);
      });
    });

    chart.setOption({
      animation: false,
      tooltip: {
        appendToBody: true,
        formatter: function(p) {
          var val = p.value[2];
          var labels = ['缺失', '部分具备', '完全具备'];
          return competitors[p.value[1]] + ' — ' + capabilities[p.value[0]] + '<br/>状态: <b>' + labels[val] + '</b>';
        }
      },
      grid: { left: 110, right: 60, top: 30, bottom: 60 },
      xAxis: {
        type: 'category',
        data: capabilities,
        axisLabel: { rotate: 45, fontSize: 10, color: ink },
        axisLine: { lineStyle: { color: rule } },
        splitLine: { show: false },
        position: 'top'
      },
      yAxis: {
        type: 'category',
        data: competitors,
        axisLabel: { fontSize: 12, fontWeight: 'bold', color: ink },
        axisLine: { lineStyle: { color: rule } },
        splitLine: { show: false }
      },
      visualMap: {
        min: 0, max: 2,
        orient: 'horizontal', left: 'center', bottom: 5,
        calculable: false,
        inRange: { color: [bg2, accent2, accent] },
        text: ['完全具备', '部分具备', '缺失'],
        textStyle: { color: muted, fontSize: 10 }
      },
      series: [{
        type: 'heatmap',
        data: seriesData,
        label: {
          show: true, color: ink, fontSize: 11,
          formatter: function(p) {
            var labels = ['✕', '△', '✓'];
            return labels[p.value[2]];
          }
        },
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.2)' } },
        itemStyle: { borderColor: bg, borderWidth: 2 }
      }]
    });

    window.addEventListener('resize', function() { chart.resize(); });
  }
})();
