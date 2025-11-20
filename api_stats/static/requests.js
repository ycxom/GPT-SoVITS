// Requests List JavaScript

let allRequests = [];
let currentPage = 1;
let pageSize = 20;
let sortField = 'id';
let sortOrder = 'desc';

async function loadRequests() {
    try {
        document.getElementById('loading').style.display = 'block';
        document.getElementById('requests-table').style.display = 'none';
        
        const response = await fetch('/stats/recent?limit=1000');
        const data = await response.json();
        allRequests = data.requests || [];
        
        const filterStatus = document.getElementById('filter-status').value;
        if (filterStatus !== 'all') {
            allRequests = allRequests.filter(r => {
                if (filterStatus === 'success') return r.success;
                if (filterStatus === 'failed') return !r.success;
                return true;
            });
        }
        
        currentPage = 1;
        renderTable();
        
        document.getElementById('loading').style.display = 'none';
        document.getElementById('requests-table').style.display = 'table';
    } catch (error) {
        console.error('加载失败:', error);
        document.getElementById('loading').innerHTML = '<p style="color: #ef4444;">加载失败: ' + error.message + '</p>';
    }
}

function sortData(field) {
    if (sortField === field) {
        sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        sortField = field;
        sortOrder = 'desc';
    }
    
    allRequests.sort((a, b) => {
        let aVal = a[field];
        let bVal = b[field];
        
        if (aVal === null || aVal === undefined) aVal = '';
        if (bVal === null || bVal === undefined) bVal = '';
        
        if (sortOrder === 'asc') {
            return aVal > bVal ? 1 : -1;
        } else {
            return aVal < bVal ? 1 : -1;
        }
    });
    
    renderTable();
}

function renderTable() {
    const tbody = document.getElementById('table-body');
    tbody.innerHTML = '';
    
    document.querySelectorAll('th.sortable').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
        if (th.dataset.sort === sortField) {
            th.classList.add('sort-' + sortOrder);
        }
    });
    
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    const pageData = allRequests.slice(start, end);
    
    pageData.forEach(req => {
        const row = document.createElement('tr');
        const statusClass = req.success ? 'status-success' : 'status-failed';
        const statusText = req.success ? '✓ 成功' : '✗ 失败';
        
        row.innerHTML = `
            <td>${req.id}</td>
            <td style="white-space: nowrap;">${req.timestamp}</td>
            <td><code>${req.client_ip || 'N/A'}</code></td>
            <td><code>${req.api_key}</code></td>
            <td>${req.model_name || 'N/A'}</td>
            <td>${req.text_length}</td>
            <td>${req.text_lang || 'N/A'}</td>
            <td>${req.media_type || 'N/A'}</td>
            <td>${req.processing_time}s</td>
            <td>${req.tts_time ? req.tts_time + 's' : '-'}</td>
            <td class="${statusClass}">${statusText}</td>
            <td>
                <button class="btn-detail" onclick="showDetail(${req.id})">查看详情</button>
            </td>
        `;
        tbody.appendChild(row);
    });
    
    renderPagination();
}

function renderPagination() {
    const pagination = document.getElementById('pagination');
    const totalPages = Math.ceil(allRequests.length / pageSize);
    
    let html = '';
    html += `<button onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>« 上一页</button>`;
    
    const maxButtons = 7;
    let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);
    
    if (endPage - startPage < maxButtons - 1) {
        startPage = Math.max(1, endPage - maxButtons + 1);
    }
    
    if (startPage > 1) {
        html += `<button onclick="changePage(1)">1</button>`;
        if (startPage > 2) html += '<span>...</span>';
    }
    
    for (let i = startPage; i <= endPage; i++) {
        html += `<button onclick="changePage(${i})" class="${i === currentPage ? 'current' : ''}">${i}</button>`;
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) html += '<span>...</span>';
        html += `<button onclick="changePage(${totalPages})">${totalPages}</button>`;
    }
    
    html += `<button onclick="changePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>下一页 »</button>`;
    html += `<span style="margin-left: 20px; color: #666;">共 ${allRequests.length} 条记录，第 ${currentPage}/${totalPages} 页</span>`;
    
    pagination.innerHTML = html;
}

function changePage(page) {
    const totalPages = Math.ceil(allRequests.length / pageSize);
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    renderTable();
}

function changePageSize() {
    pageSize = parseInt(document.getElementById('page-size').value);
    currentPage = 1;
    renderTable();
}

async function showDetail(requestId) {
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
                ${data.error_message ? `<p><strong>错误:</strong> <span style="color: #ef4444;">${data.error_message}</span></p>` : ''}
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
                <div class="text-content">${escapeHtml(data.text_full || data.text_preview)}</div>
                <p style="margin-top: 10px; color: #666; font-size: 0.9em;">
                    <strong>字符数:</strong> ${data.text_length}
                    ${!data.text_full && data.text_length > 100 ? 
                        '<br><em style="color: #f59e0b;">⚠️ 旧记录，仅显示前100字符</em>' : 
                        '<br><em style="color: #10b981;">✓ 完整内容</em>'}
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
        alert('加载详情失败: ' + error.message);
    }
}

function closeModal() {
    const modal = document.getElementById('detail-modal');
    modal.classList.remove('show');
    modal.classList.add('hide');
    
    // 等待动画完成后隐藏
    setTimeout(() => {
        modal.style.display = 'none';
        modal.classList.remove('hide');
    }, 300);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function exportData() {
    const csv = generateCSV();
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `api_requests_${new Date().toISOString().slice(0,10)}.csv`;
    link.click();
}

function generateCSV() {
    const headers = ['ID', '时间', 'IP地址', 'API Key', '模型', '文本长度', '语言', '格式', '总时间', 'TTS时间', '状态'];
    let csv = headers.join(',') + '\\n';
    
    allRequests.forEach(req => {
        const row = [
            req.id,
            req.timestamp,
            req.client_ip || 'N/A',
            req.api_key,
            req.model_name || 'N/A',
            req.text_length,
            req.text_lang || 'N/A',
            req.media_type || 'N/A',
            req.processing_time,
            req.tts_time || '',
            req.success ? '成功' : '失败'
        ];
        csv += row.map(v => `"${v}"`).join(',') + '\\n';
    });
    
    return csv;
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            sortData(th.dataset.sort);
        });
    });
    
    document.getElementById('detail-modal').addEventListener('click', (e) => {
        if (e.target.id === 'detail-modal') {
            closeModal();
        }
    });
    
    loadRequests();
});
