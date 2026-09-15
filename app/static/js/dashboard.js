let typeChart, statusChart;

const TAG_CLASS = {
  "SLA 초과": "sla-over",
  "SLA 임박": "sla-warning",
  "긴급": "urgent",
  "장기 미처리": "long-pending",
};

function renderUrgentList(list) {
  const el = document.getElementById("urgent-list");
  if (!list || list.length === 0) {
    el.innerHTML = '<p style="color:#888;font-size:13px;">현재 즉시 확인이 필요한 이슈가 없습니다.</p>';
    return;
  }
  el.innerHTML = list.map((i) => `
    <div class="urgent-item">
      <div>
        <a href="/issues/${i.id}">${i.issue_number}</a>
        &nbsp;${i.title} &middot; ${i.issue_type}
        &nbsp;<span class="badge-priority ${i.priority}">${i.priority_display}</span>
        &nbsp;<span class="tag-pill ${TAG_CLASS[i.tag] || ''}">${i.tag}</span>
        &nbsp;<span class="assignee">${i.assignee_name}</span>
      </div>
      <div class="elapsed">${i.elapsed || ""}</div>
    </div>
  `).join("");
}

function renderAssigneeRows(rows) {
  const el = document.getElementById("assignee-rows");
  if (!rows || rows.length === 0) {
    el.innerHTML = '<p style="color:#888;font-size:13px;">등록된 담당자가 없습니다.</p>';
    return;
  }
  const max = Math.max(1, ...rows.map((r) => r.in_progress));
  el.innerHTML = rows.map((r) => `
    <div class="assignee-row">
      <div class="name">${r.name}</div>
      <div class="assignee-track"><div class="assignee-fill" style="width:${Math.round((r.in_progress / max) * 100)}%"></div></div>
      <div style="width:30px;text-align:right;">${r.in_progress}</div>
      <div class="over">${r.sla_over > 0 ? "SLA " + r.sla_over : ""}</div>
    </div>
  `).join("");
}

function renderCharts(data) {
  const typeCtx = document.getElementById("typeChart");
  const statusCtx = document.getElementById("statusChart");

  const typeLabels = data.type_chart.map((d) => d.label);
  const typeValues = data.type_chart.map((d) => d.value);
  const statusLabels = data.status_chart.map((d) => d.label);
  const statusValues = data.status_chart.map((d) => d.value);

  if (!typeChart) {
    typeChart = new Chart(typeCtx, {
      type: "bar",
      data: { labels: typeLabels, datasets: [{ data: typeValues, backgroundColor: "#3454d1", borderRadius: 4 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
    });
  } else {
    typeChart.data.labels = typeLabels;
    typeChart.data.datasets[0].data = typeValues;
    typeChart.update();
  }

  if (!statusChart) {
    statusChart = new Chart(statusCtx, {
      type: "doughnut",
      data: {
        labels: statusLabels,
        datasets: [{
          data: statusValues,
          backgroundColor: ["#9aa3b8", "#3454d1", "#1c6fc7", "#c8862a", "#c8862a", "#2e9e6d", "#c8ccd6"],
        }],
      },
      options: { plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } } } },
    });
  } else {
    statusChart.data.labels = statusLabels;
    statusChart.data.datasets[0].data = statusValues;
    statusChart.update();
  }
}

function applyDashboardData(data) {
  document.getElementById("kpi-total").textContent = data.kpi.total;
  document.getElementById("kpi-in-progress").textContent = data.kpi.in_progress;
  document.getElementById("kpi-urgent").textContent = data.kpi.urgent;
  document.getElementById("kpi-sla").textContent = data.kpi.sla_over;
  document.getElementById("kpi-sla-warning").textContent = data.kpi.sla_warning;
  document.getElementById("kpi-waiting-vendor").textContent = data.kpi.waiting_vendor;
  document.getElementById("kpi-waiting-customer").textContent = data.kpi.waiting_customer;
  document.getElementById("kpi-long-pending").textContent = data.kpi.long_pending;
  document.getElementById("kpi-unassigned").textContent = data.kpi.unassigned;
  renderUrgentList(data.action_needed);
  renderAssigneeRows(data.assignee_rows);
  renderCharts(data);
}

applyDashboardData(initialData);

async function pollDashboard() {
  try {
    const res = await fetch("/api/dashboard/summary");
    if (res.ok) {
      const data = await res.json();
      applyDashboardData(data);
    }
  } catch (e) {
    /* ignore transient network errors */
  }
}

setInterval(pollDashboard, 10000);
