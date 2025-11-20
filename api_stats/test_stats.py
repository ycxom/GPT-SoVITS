"""
测试统计功能
"""

import time
import sys
import os

# 添加父目录到路径以便导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_stats.stats_manager import get_stats_manager


def test_stats_manager():
    """测试统计管理器"""
    print("=" * 60)
    print("测试统计管理器")
    print("=" * 60)
    
    # 获取统计管理器实例
    stats_manager = get_stats_manager("test_api_stats.db")
    
    # 模拟一些请求
    print("\n1. 模拟API请求...")
    test_texts = [
        "你好世界，这是一个测试文本。",
        "Hello world, this is a test.",
        "こんにちは、テストです。",
        "안녕하세요, 테스트입니다.",
        "Bonjour le monde, c'est un test."
    ]
    
    for i in range(10):
        text = test_texts[i % len(test_texts)]
        stats_manager.record_request(
            api_key=f"test_key_{i % 3}",
            model_name=f"model_{i % 2}",
            text_length=len(text),
            processing_time=0.5 + i * 0.1,
            success=i % 5 != 0,  # 每5个请求有1个失败
            error_message="Test error" if i % 5 == 0 else None,
            client_ip=f"192.168.1.{i}",
            text_lang="zh" if i % 2 == 0 else "en",
            media_type="wav",
            text_preview=text[:100] if len(text) > 100 else text,
            text_full=text,
            ref_audio_path=f"/path/to/audio_{i}.wav",
            prompt_text=f"参考文本{i}"
        )
        time.sleep(0.01)  # 模拟请求间隔
    
    print(f"   ✅ 已记录 10 条请求")
    
    # 获取统计数据
    print("\n2. 获取统计数据...")
    
    total = stats_manager.get_total_requests()
    print(f"   总请求数: {total}")
    
    success_rate = stats_manager.get_success_rate()
    print(f"   成功率: {success_rate:.2f}%")
    
    avg_time = stats_manager.get_average_processing_time()
    print(f"   平均处理时间: {avg_time:.3f}秒")
    
    rpm = stats_manager.get_requests_per_minute(1)
    print(f"   每分钟请求数: {rpm:.2f}")
    
    uptime = stats_manager.get_uptime_formatted()
    print(f"   运行时长: {uptime}")
    
    # 获取模型统计
    print("\n3. 模型统计:")
    model_stats = stats_manager.get_model_stats()
    for stat in model_stats:
        print(f"   - {stat['model_name']}: {stat['total_requests']}次请求, "
              f"成功率 {stat['success_rate']:.2f}%, "
              f"平均时间 {stat['avg_processing_time']:.3f}秒")
    
    # 获取API Key统计
    print("\n4. API Key统计:")
    key_stats = stats_manager.get_api_key_stats()
    for stat in key_stats:
        print(f"   - {stat['api_key']}: {stat['total_requests']}次请求, "
              f"成功率 {stat['success_rate']:.2f}%")
    
    # 获取最近错误
    print("\n5. 最近错误:")
    errors = stats_manager.get_recent_errors(5)
    for error in errors:
        print(f"   - [{error['timestamp']}] {error['model_name']}: {error['error_message']}")
    
    # 获取IP统计
    print("\n6. IP统计:")
    ip_stats = stats_manager.get_ip_stats()
    for stat in ip_stats[:5]:  # 只显示前5个
        print(f"   - {stat['client_ip']}: {stat['total_requests']}次请求, "
              f"成功率 {stat['success_rate']:.2f}%, "
              f"最后请求 {stat['last_request_time']}")
    
    # 获取最近请求
    print("\n7. 最近请求记录:")
    recent = stats_manager.get_recent_requests(5)
    for req in recent:
        status = "✓" if req['success'] else "✗"
        print(f"   {status} [{req['timestamp']}] {req['client_ip']} -> {req['model_name']} "
              f"({req['text_length']}字, {req['processing_time']}s)")
        if req.get('text_preview'):
            print(f"      文本预览: {req['text_preview'][:50]}...")
    
    # 测试获取请求详情
    print("\n8. 测试获取请求详情:")
    if recent:
        first_req_id = recent[0]['id']
        detail = stats_manager.get_request_detail(first_req_id)
        if detail:
            print(f"   请求ID: {detail['id']}")
            print(f"   文本预览: {detail.get('text_preview', 'N/A')}")
            print(f"   参考音频: {detail.get('ref_audio_path', 'N/A')}")
            print(f"   提示文本: {detail.get('prompt_text', 'N/A')}")
    
    # 获取仪表板数据
    print("\n9. 获取完整仪表板数据...")
    dashboard = stats_manager.get_dashboard_stats()
    print(f"   ✅ 仪表板数据包含 {len(dashboard)} 个字段")
    
    # 清理测试数据
    print("\n10. 清理测试数据...")
    import os
    if os.path.exists("test_api_stats.db"):
        os.remove("test_api_stats.db")
        print("   ✅ 测试数据库已删除")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    test_stats_manager()
