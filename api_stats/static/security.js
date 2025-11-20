// 安全防护日志JavaScript

let currentTab = 'malicious';
let maliciousData = [];
let blacklistData = [];

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', function() {
    loadSecurityStats();
    loadMaliciousRequests();
    
    // 每30秒自动刷新
    setInterval(() => {
        loadSecurityStats();
        if (currentTab === 'malicious') {
            loadMaliciousRequests();
        } else {
            loadBlacklist();
        }
    }, 30000);
});

// 切换标签页
function switchTab(tab) {
    currentTab = tab;
    
    // 更新标签按钮状态
    document.querySelectorAll('.tab-button').forEach((btn, index) => {
        btn.classList.remove('active');
        
        // 根据tab设置active状态
        if ((tab === 'malicious' && index === 0) || (tab === 'blacklist' && index === 1)) {
            btn.classList.add('active');
        }
    });
    
    // 切换内容
    document.getElementById('malicious-tab').style.display = tab === 'malicious' ? 'block' : 'none';
    document.getElementById('blacklist-tab').style.display = tab === 'blacklist' ? 'block' : 'none';
    
    // 加载对应数据
    if (tab === 'malicious') {
        loadMaliciousRequests();
    } else {
        loadBlacklist();
    }
}

// 加载安全统计
async function loadSecurityStats() {
    try {
        const response = await fetch('/security/stats', {
            credentials: 'same-origin'  // 发送cookie
        });
        if (!response.ok) {
            console.error('API响应错误:', response.status, response.statusText);
            return;
        }
        const data = await response.json();
        
        document.getElementById('malicious-count').textContent = data.total_malicious_requests || 0;
        document.getElementById('blacklist-count').textContent = data.blacklist_count || 0;
    } catch (error) {
        console.error('加载安全统计失败:', error);
    }
}

// 加载恶意请求列表
async function loadMaliciousRequests() {
    const loading = document.getElementById('malicious-loading');
    const table = document.getElementById('malicious-table');
    const tbody = document.getElementById('malicious-table-body');
    
    loading.style.display = 'block';
    table.style.display = 'none';
    
    try {
        const limit = document.getElementById('malicious-page-size').value;
        const response = await fetch(`/security/malicious_requests?limit=${limit}`, {
            credentials: 'same-origin'  // 发送cookie
        });
        
        if (!response.ok) {
            console.error('API响应错误:', response.status, response.statusText);
            loading.innerHTML = `<p style="color: red;">加载失败: ${response.status} ${response.statusText}</p>`;
            return;
        }
        
        const data = await response.json();
        console.log('恶意请求数据:', data);
        
        maliciousData = data.records || [];
        
        // 应用筛选
        const filter = document.getElementById('threat-type-filter').value;
        let filteredData = maliciousData;
        if (filter !== 'all') {
            filteredData = maliciousData.filter(r => r.threat_type === filter);
        }
        
        // 渲染表格
        tbody.innerHTML = '';
        filteredData.forEach(record => {
            const row = document.createElement('tr');
            const threatClass = record.threat_type === 'suspicious_path' ? 'badge-warning' : 'badge-danger';
            
            row.innerHTML = `
                <td>${record.id}</td>
                <td>${record.timestamp}</td>
                <td>${record.client_ip}</td>
                <td>${record.method}</td>
                <td title="${record.path}">${truncate(record.path, 30)}</td>
                <td><span class="badge ${threatClass}">${record.threat_type}</span></td>
                <td title="${record.threat_details}">${truncate(record.threat_details, 40)}</td>
                <td title="${record.user_agent}">${truncate(record.user_agent, 20)}</td>
                <td><button class="btn-small" onclick="showMaliciousDetail(${record.id})">详情</button></td>
            `;
            tbody.appendChild(row);
        });
        
        if (filteredData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #999;">暂无数据</td></tr>';
        }
        
        loading.style.display = 'none';
        table.style.display = 'table';
    } catch (error) {
        console.error('加载恶意请求失败:', error);
        loading.innerHTML = `<p style="color: red;">加载失败: ${error.message}</p>`;
    }
}

// 加载黑名单
async function loadBlacklist() {
    const loading = document.getElementById('blacklist-loading');
    const table = document.getElementById('blacklist-table');
    const tbody = document.getElementById('blacklist-table-body');
    
    loading.style.display = 'block';
    table.style.display = 'none';
    
    try {
        const response = await fetch('/security/blacklist', {
            credentials: 'same-origin'  // 发送cookie
        });
        
        if (!response.ok) {
            console.error('API响应错误:', response.status, response.statusText);
            loading.innerHTML = `<p style="color: red;">加载失败: ${response.status} ${response.statusText}</p>`;
            return;
        }
        
        const data = await response.json();
        console.log('黑名单数据:', data);
        
        blacklistData = data.records || [];
        
        // 渲染表格
        tbody.innerHTML = '';
        blacklistData.forEach(record => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${record.id}</td>
                <td>${record.ip_address}</td>
                <td><span class="badge badge-danger">${record.threat_count}</span></td>
                <td>${record.reason}</td>
                <td>${record.first_seen}</td>
                <td>${record.last_seen}</td>
                <td><span class="badge badge-warning">已黑名单</span></td>
                <td><button class="btn-small btn-primary" onclick="unblockIP('${record.ip_address}')">解除</button></td>
            `;
            tbody.appendChild(row);
        });
        
        if (blacklistData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #999;">黑名单为空</td></tr>';
        }
        
        loading.style.display = 'none';
        table.style.display = 'table';
    } catch (error) {
        console.error('加载黑名单失败:', error);
        loading.innerHTML = `<p style="color: red;">加载失败: ${error.message}</p>`;
    }
}

// 显示恶意请求详情
function showMaliciousDetail(id) {
    console.log('showMaliciousDetail called with id:', id);
    console.log('maliciousData:', maliciousData);
    
    const record = maliciousData.find(r => r.id === id);
    if (!record) {
        console.error('Record not found for id:', id);
        return;
    }
    
    const modal = document.getElementById('detail-modal');
    const content = document.getElementById('detail-content');
    
    if (!modal || !content) {
        console.error('Modal elements not found');
        return;
    }
    
    content.innerHTML = `
        <div class="detail-grid" style="color: white;">
            <div class="detail-item">
                <strong style="color: white;">ID:</strong>
                <span style="color: white;">${record.id}</span>
            </div>
            <div class="detail-item">
                <strong style="color: white;">时间:</strong>
                <span style="color: white;">${record.timestamp}</span>
            </div>
            <div class="detail-item">
                <strong style="color: white;">IP地址:</strong>
                <span style="color: white;">${record.client_ip}</span>
            </div>
            <div class="detail-item">
                <strong style="color: white;">HTTP方法:</strong>
                <span style="color: white;">${record.method}</span>
            </div>
            <div class="detail-item">
                <strong style="color: white;">请求路径:</strong>
                <span style="color: white;">${record.path}</span>
            </div>
            <div class="detail-item">
                <strong style="color: white;">查询字符串:</strong>
                <span style="color: white;">${record.query_string || '无'}</span>
            </div>
            <div class="detail-item">
                <strong style="color: white;">威胁类型:</strong>
                <span class="badge ${record.threat_type === 'suspicious_path' ? 'badge-warning' : 'badge-danger'}">${record.threat_type}</span>
            </div>
            <div class="detail-item">
                <strong style="color: white;">威胁详情:</strong>
                <span style="color: white;">${record.threat_details}</span>
            </div>
            <div class="detail-item">
                <strong style="color: white;">完整URL:</strong>
                <span style="color: white; word-break: break-all;">${record.full_url || '无'}</span>
            </div>
            <div class="detail-item">
                <strong style="color: white;">User-Agent:</strong>
                <span style="color: white; word-break: break-all;">${record.user_agent}</span>
            </div>
            <div class="detail-item">
                <strong style="color: white;">请求体:</strong>
                <span style="color: white; word-break: break-all;">${record.request_body || '无'}</span>
            </div>
            <div class="detail-item">
                <strong style="color: white;">处理动作:</strong>
                <span class="badge badge-danger">${record.action_taken}</span>
            </div>
        </div>
    `;
    
    // 显示模态框（与common.js兼容）
    modal.style.display = 'flex';
    setTimeout(() => {
        modal.classList.add('show');
    }, 10);
}

// 解除IP黑名单
async function unblockIP(ip) {
    if (!confirm(`确定要解除 ${ip} 的黑名单吗？`)) {
        return;
    }
    
    try {
        const response = await fetch(`/security/unblock_ip?ip_address=${ip}`, {
            method: 'POST',
            credentials: 'same-origin'  // 发送cookie
        });
        const data = await response.json();
        alert(data.message);
        loadBlacklist();
        loadSecurityStats();
    } catch (error) {
        console.error('解除黑名单失败:', error);
        alert('解除黑名单失败');
    }
}

// closeModal函数已在common.js中定义，这里不需要重复定义

// 导出恶意请求数据
function exportMaliciousData() {
    const filter = document.getElementById('threat-type-filter').value;
    let data = maliciousData;
    if (filter !== 'all') {
        data = maliciousData.filter(r => r.threat_type === filter);
    }
    
    const csv = convertToCSV(data, [
        'id', 'timestamp', 'client_ip', 'method', 'path', 
        'threat_type', 'threat_details', 'user_agent'
    ]);
    downloadCSV(csv, 'malicious_requests.csv');
}

// 导出黑名单数据
function exportBlacklistData() {
    const csv = convertToCSV(blacklistData, [
        'id', 'ip_address', 'threat_count', 'reason', 
        'first_seen', 'last_seen'
    ]);
    downloadCSV(csv, 'ip_blacklist.csv');
}

// 转换为CSV
function convertToCSV(data, fields) {
    const header = fields.join(',');
    const rows = data.map(item => 
        fields.map(field => `"${item[field] || ''}"`).join(',')
    );
    return [header, ...rows].join('\n');
}

// 下载CSV
function downloadCSV(csv, filename) {
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
}

// 截断文本
function truncate(str, length) {
    if (!str) return '';
    return str.length > length ? str.substring(0, length) + '...' : str;
}

// 点击模态框外部关闭
window.onclick = function(event) {
    const modal = document.getElementById('detail-modal');
    if (event.target === modal) {
        closeModal();
    }
}
