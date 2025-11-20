// 全局图表对象
let statusPieChart = null;
let hourlyLineChart = null;
let modelPieChart = null;
let processingTimeChart = null;

// 加载统计数据
async function loadStats() {
    try {
        const response = await fetch('/stats/api');
        const data = await response.json();
        
        // 更新核心指标
        document.getElementById('total-requests').textContent = (data.total_requests || 0).toLocaleString();
        document.getElementById('success-rate').textContent = data.success_rate || 0;
        document.getElementById('avg-time').textContent = data.avg_processing_time || 0;
        document.getElementById('rpm').textContent = data.requests_per_minute || 0;
        document.getElementById('uptime').textContent = data.uptime || '-';
        
        // 更新模型统计
        updateModelStats(data.model_stats);
        
        // 更新API Key统计
        updateApiKeyStats(data.api_key_stats);
        
        // 更新每小时统计
        updateHourlyStats(data.hourly_stats);
        
        // 更新IP统计
        updateIpStats(data.ip_stats);
        
        // 更新最近请求
        updateRecentRequests(data.recent_requests);
        
        // 更新系统事件日志
        updateSystemEvents(data.system_events);
        
        // 更新最近错误
        updateRecentErrors(data.recent_errors);
        
        // 渲染图表
        renderCharts(data);
        
        // 隐藏加载动画，显示内容
        document.getElementById('loading').style.display = 'none';
        document.getElementById('content').style.display = 'block';
        
    } catch (error) {
        console.error('加载统计数据失败:', error);
        document.getElementById('loading').innerHTML = `
            <p style="color: #ef4444;">❌ 加载统计数据失败</p>
            <p style="font-size: 0.9em;">${error.message}</p>
        `;
    }
}

// 更新模型统计表格
function updateModelStats(modelStats) {
    const tbody = document.getElementById('model-stats').querySelector('tbody');
    tbody.innerHTML = '';
    
    if (modelStats && modelStats.length > 0) {
        modelStats.forEach(model => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${model.model_name || '未指定'}</strong></td>
                <td>${model.total_requests}</td>
                <td>${model.success_count}</td>
                <td>
                    ${model.success_rate.toFixed(2)}%
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${model.success_rate}%"></div>
                    </div>
                </td>
                <td>${model.avg_processing_time.toFixed(3)}s</td>
            `;
            tbody.appendChild(row);
        });
    } else {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #999;">暂无数据</td></tr>';
    }
}

// 更新API Key统计表格
function updateApiKeyStats(apiKeyStats) {
    const tbody = document.getElementById('apikey-stats').querySelector('tbody');
    tbody.innerHTML = '';
    
    if (apiKeyStats && apiKeyStats.length > 0) {
        apiKeyStats.forEach(key => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><code>${key.api_key}</code></td>
                <td>${key.total_requests}</td>
                <td>${key.success_count}</td>
                <td>
                    ${key.success_rate.toFixed(2)}%
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${key.success_rate}%"></div>
                    </div>
                </td>
                <td>${key.avg_processing_time.toFixed(3)}s</td>
            `;
            tbody.appendChild(row);
        });
    } else {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #999;">暂无数据</td></tr>';
    }
}

// 更新每小时统计表格
function updateHourlyStats(hourlyStats) {
    const tbody = document.getElementById('hourly-stats').querySelector('tbody');
    tbody.innerHTML = '';
    
    if (hourlyStats && hourlyStats.length > 0) {
        hourlyStats.forEach(hour => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${hour.hour}</td>
                <td>${hour.total_requests}</td>
                <td>${hour.success_count}</td>
                <td>${hour.success_rate.toFixed(2)}%</td>
                <td>${hour.avg_processing_time.toFixed(3)}s</td>
            `;
            tbody.appendChild(row);
        });
    } else {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #999;">暂无数据</td></tr>';
    }
}

// 更新IP统计表格
function updateIpStats(ipStats) {
    const tbody = document.getElementById('ip-stats').querySelector('tbody');
    tbody.innerHTML = '';
    
    if (ipStats && ipStats.length > 0) {
        ipStats.forEach(ip => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><code>${ip.client_ip}</code></td>
                <td>${ip.total_requests}</td>
                <td>${ip.success_count}</td>
                <td>
                    ${ip.success_rate.toFixed(2)}%
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${ip.success_rate}%"></div>
                    </div>
                </td>
                <td>${ip.avg_processing_time.toFixed(3)}s</td>
                <td>${ip.last_request_time}</td>
            `;
            tbody.appendChild(row);
        });
    } else {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #999;">暂无数据</td></tr>';
    }
}

// 更新最近请求表格
function updateRecentRequests(recentRequests) {
    const tbody = document.getElementById('recent-requests').querySelector('tbody');
    tbody.innerHTML = '';
    
    if (recentRequests && recentRequests.length > 0) {
        recentRequests.forEach(req => {
            const row = document.createElement('tr');
            const statusBadge = req.success 
                ? '<span style="color: #10b981; font-weight: bold;">✓ 成功</span>' 
                : '<span style="color: #ef4444; font-weight: bold;">✗ 失败</span>';
            const errorInfo = req.error_message 
                ? `<br><small style="color: #ef4444;">${req.error_message}</small>` 
                : '';
            
            row.innerHTML = `
                <td style="white-space: nowrap;">${req.timestamp}</td>
                <td><code>${req.client_ip || 'N/A'}</code></td>
                <td><code>${req.api_key}</code></td>
                <td>${req.model_name || 'N/A'}</td>
                <td>${req.text_length}</td>
                <td>${req.text_lang || 'N/A'}</td>
                <td>${req.media_type || 'N/A'}</td>
                <td>${req.processing_time}s</td>
                <td>${statusBadge}${errorInfo}</td>
                <td>
                    <button class="detail-btn" onclick="showRequestDetail(${req.id})" 
                            style="background: #667eea; color: white; border: none; 
                                   padding: 5px 10px; border-radius: 4px; cursor: pointer; 
                                   font-size: 0.9em;">
                        查看详情
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } else {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: #999;">暂无数据</td></tr>';
    }
}

// 更新系统事件日志
function updateSystemEvents(systemEvents) {
    const tbody = document.getElementById('system-events').querySelector('tbody');
    tbody.innerHTML = '';
    
    if (systemEvents && systemEvents.length > 0) {
        systemEvents.forEach(event => {
            const row = document.createElement('tr');
            
            let statusColor = '#10b981';
            let statusIcon = '✓';
            if (event.status === 'failed') {
                statusColor = '#ef4444';
                statusIcon = '✗';
            } else if (event.status === 'warning') {
                statusColor = '#f59e0b';
                statusIcon = '⚠';
            }
            
            let typeIcon = '📋';
            if (event.event_type === 'model_load') typeIcon = '🔄';
            else if (event.event_type === 'model_switch') typeIcon = '🔀';
            else if (event.event_type === 'server_start') typeIcon = '🚀';
            else if (event.event_type === 'server_stop') typeIcon = '🛑';
            else if (event.event_type === 'error') typeIcon = '❌';
            
            row.innerHTML = `
                <td style="white-space: nowrap;">${event.timestamp}</td>
                <td>${typeIcon} ${event.event_type}</td>
                <td><strong>${event.event_name}</strong></td>
                <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis;">
                    ${event.details || '-'}
                </td>
                <td style="color: ${statusColor}; font-weight: bold;">
                    ${statusIcon} ${event.status}
                </td>
                <td>${event.duration ? event.duration + 's' : '-'}</td>
            `;
            tbody.appendChild(row);
        });
    } else {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #999;">暂无系统事件</td></tr>';
    }
}

// 更新最近错误
function updateRecentErrors(recentErrors) {
    const errorsDiv = document.getElementById('recent-errors');
    
    if (!recentErrors || recentErrors.length === 0) {
        errorsDiv.innerHTML = '<p style="color: #10b981; text-align: center; padding: 20px;">✅ 暂无错误记录</p>';
    } else {
        errorsDiv.innerHTML = '';
        recentErrors.forEach(error => {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.innerHTML = `
                <strong>${error.timestamp}</strong> - 
                API Key: <code>${error.api_key}</code> - 
                模型: ${error.model_name} - 
                IP: ${error.client_ip}<br>
                错误: ${error.error_message}
            `;
            errorsDiv.appendChild(errorDiv);
        });
    }
}

// 显示请求详情
async function showRequestDetail(requestId) {
    try {
        const response = await fetch(`/stats/request/${requestId}`);
        const data = await response.json();
        
        const detailHtml = `
            <div class="detail-section">
                <h3>基本信息</h3>
                <p><strong>请求ID:</strong> ${data.id}</p>
                <p><strong>时间:</strong> ${data.timestamp}</p>
                <p><strong>IP地址:</strong> <code>${data.client_ip || 'N/A'}</code></p>
                <p><strong>API Key:</strong> <code>${data.api_key}</code></p>
                <p><strong>状态:</strong> ${data.success ? 
                    '<span style="color: #10b981;">✓ 成功</span>' : 
                    '<span style="color: #ef4444;">✗ 失败</span>'}</p>
                ${data.error_message ? `<p><strong>错误信息:</strong> <span style="color: #ef4444;">${data.error_message}</span></p>` : ''}
            </div>
            
            <div class="detail-section">
                <h3>请求参数</h3>
                <p><strong>模型:</strong> ${data.model_name || 'N/A'}</p>
                <p><strong>文本长度:</strong> ${data.text_length} 字符</p>
                <p><strong>语言:</strong> ${data.text_lang || 'N/A'}</p>
                <p><strong>输出格式:</strong> ${data.media_type || 'N/A'}</p>
                <p><strong>总处理时间:</strong> ${data.processing_time}秒</p>
                ${data.tts_time ? `<p><strong>TTS合成时间:</strong> ${data.tts_time}秒</p>` : ''}
            </div>
            
            ${data.text_full || data.text_preview ? `
            <div class="detail-section">
                <h3>📝 完整文本内容</h3>
                <div class="text-content">
                    ${escapeHtml(data.text_full || data.text_preview)}
                </div>
                <p style="margin-top: 10px; font-size: 0.9em;">
                    <strong>字符数:</strong> ${data.text_length} 字符
                    ${!data.text_full && data.text_length > 100 ? 
                        '<br><em style="color: #f59e0b;">⚠️ 此为旧记录，仅显示前100个字符。新请求将显示完整内容。</em>' : 
                        '<br><em style="color: #10b981;">✓ 显示完整文本内容</em>'}
                </p>
            </div>
            ` : ''}
            
            ${data.ref_audio_path ? `
            <div class="detail-section">
                <h3>🎵 参考音频</h3>
                <p><strong>音频路径:</strong> <code>${data.ref_audio_path}</code></p>
                ${data.prompt_text ? `<p><strong>提示文本:</strong> ${escapeHtml(data.prompt_text)}</p>` : ''}
            </div>
            ` : ''}
        `;
        
        document.getElementById('detail-content').innerHTML = detailHtml;
        
        const modal = document.getElementById('detail-modal');
        modal.style.display = 'block';
        // 触发重排以启动动画
        modal.offsetHeight;
        modal.classList.add('show');
        
    } catch (error) {
        console.error('加载请求详情失败:', error);
        alert('加载请求详情失败: ' + error.message);
    }
}

// 关闭详情模态框
function closeDetailModal() {
    const modal = document.getElementById('detail-modal');
    modal.classList.remove('show');
    modal.classList.add('hide');
    
    // 等待动画完成后隐藏
    setTimeout(() => {
        modal.style.display = 'none';
        modal.classList.remove('hide');
    }, 300);
}

// HTML转义函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 渲染所有图表
function renderCharts(data) {
    renderStatusPieChart(data);
    renderHourlyLineChart(data);
    renderModelPieChart(data);
    renderProcessingTimeChart(data);
}

// 请求状态分布饼图
function renderStatusPieChart(data) {
    const ctx = document.getElementById('statusPieChart');
    if (!ctx) return;
    
    const successCount = Math.round(data.total_requests * data.success_rate / 100);
    const failedCount = data.total_requests - successCount;
    
    if (statusPieChart) {
        statusPieChart.destroy();
    }
    
    statusPieChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['成功', '失败'],
            datasets: [{
                data: [successCount, failedCount],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(239, 68, 68, 0.8)'
                ],
                borderColor: [
                    'rgba(16, 185, 129, 1)',
                    'rgba(239, 68, 68, 1)'
                ],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return label + ': ' + value + ' (' + percentage + '%)';
                        }
                    }
                }
            }
        }
    });
}

// 24小时请求趋势折线图
function renderHourlyLineChart(data) {
    const ctx = document.getElementById('hourlyLineChart');
    if (!ctx) return;
    
    const hourlyStats = data.hourly_stats || [];
    const labels = hourlyStats.map(h => h.hour);
    const totalRequests = hourlyStats.map(h => h.total_requests);
    const successRequests = hourlyStats.map(h => h.success_count);
    
    if (hourlyLineChart) {
        hourlyLineChart.destroy();
    }
    
    hourlyLineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '总请求',
                    data: totalRequests,
                    borderColor: 'rgba(102, 126, 234, 1)',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: '成功请求',
                    data: successRequests,
                    borderColor: 'rgba(16, 185, 129, 1)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0 }
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        }
    });
}

// 模型使用分布饼图
function renderModelPieChart(data) {
    const ctx = document.getElementById('modelPieChart');
    if (!ctx) return;
    
    const modelStats = data.model_stats || [];
    const labels = modelStats.map(m => m.model_name || '未指定');
    const values = modelStats.map(m => m.total_requests);
    
    const colors = [
        'rgba(102, 126, 234, 0.8)',
        'rgba(118, 75, 162, 0.8)',
        'rgba(16, 185, 129, 0.8)',
        'rgba(245, 158, 11, 0.8)',
        'rgba(239, 68, 68, 0.8)',
        'rgba(59, 130, 246, 0.8)',
        'rgba(236, 72, 153, 0.8)',
        'rgba(139, 92, 246, 0.8)'
    ];
    
    if (modelPieChart) {
        modelPieChart.destroy();
    }
    
    modelPieChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors.slice(0, labels.length),
                borderColor: colors.slice(0, labels.length).map(c => c.replace('0.8', '1')),
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return label + ': ' + value + ' (' + percentage + '%)';
                        }
                    }
                }
            }
        }
    });
}

// 处理时间趋势折线图
function renderProcessingTimeChart(data) {
    const ctx = document.getElementById('processingTimeChart');
    if (!ctx) return;
    
    const hourlyStats = data.hourly_stats || [];
    const labels = hourlyStats.map(h => h.hour);
    const avgTimes = hourlyStats.map(h => h.avg_processing_time);
    
    if (processingTimeChart) {
        processingTimeChart.destroy();
    }
    
    processingTimeChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '平均处理时间 (秒)',
                data: avgTimes,
                borderColor: 'rgba(245, 158, 11, 1)',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return '平均时间: ' + context.parsed.y.toFixed(3) + '秒';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return value.toFixed(2) + 's';
                        }
                    }
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        }
    });
}

// 点击模态框外部关闭
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('detail-modal').addEventListener('click', function(e) {
        if (e.target === this) {
            closeDetailModal();
        }
    });
    
    // 页面加载时获取数据
    loadStats();
    
    // 每30秒自动刷新
    setInterval(loadStats, 30000);
});
