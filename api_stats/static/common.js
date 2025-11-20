// 背景图片缓存管理
(function() {
    const CACHE_KEY = 'stats_bg_data';
    const CACHE_TIME_KEY = 'stats_bg_time';
    const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24小时
    
    const now = Date.now();
    const cachedTime = localStorage.getItem(CACHE_TIME_KEY);
    
    function setBackground(dataUrl) {
        const applyBg = function() {
            document.body.style.opacity = '0';
            document.body.style.backgroundImage = `linear-gradient(rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.6)), url(${dataUrl})`;
            setTimeout(() => {
                document.body.style.transition = 'opacity 1s ease-in-out';
                document.body.style.opacity = '1';
            }, 50);
        };
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', applyBg);
        } else {
            applyBg();
        }
    }
    
    if (cachedTime && (now - parseInt(cachedTime)) < CACHE_DURATION) {
        const cachedData = localStorage.getItem(CACHE_KEY);
        if (cachedData) {
            setBackground(cachedData);
            return;
        }
    }
    
    fetch('https://www.loliapi.com/acg/')
        .then(response => response.blob())
        .then(blob => {
            const reader = new FileReader();
            reader.onloadend = function() {
                const dataUrl = reader.result;
                try {
                    localStorage.setItem(CACHE_KEY, dataUrl);
                    localStorage.setItem(CACHE_TIME_KEY, now.toString());
                } catch (e) {
                    console.warn('图片太大，无法缓存');
                }
                setBackground(dataUrl);
            };
            reader.readAsDataURL(blob);
        })
        .catch(err => console.error('加载背景失败:', err));
})();


// ==================== 公共工具函数 ====================

// HTML转义函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 显示请求详情（通用）
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
        modal.offsetHeight; // 触发重排以启动动画
        modal.classList.add('show');
        
    } catch (error) {
        console.error('加载请求详情失败:', error);
        alert('加载请求详情失败: ' + error.message);
    }
}

// 关闭详情模态框（通用）
function closeDetailModal() {
    const modal = document.getElementById('detail-modal');
    modal.classList.remove('show');
    modal.classList.add('hide');
    
    setTimeout(() => {
        modal.style.display = 'none';
        modal.classList.remove('hide');
    }, 300);
}

// 为了兼容性，添加别名
const closeModal = closeDetailModal;
const showDetail = showRequestDetail;
