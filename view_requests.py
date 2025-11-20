#!/usr/bin/env python3
"""
查看API请求详细内容的脚本
"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_stats import get_stats_manager


def view_all_requests(limit=20):
    """查看所有请求的详细信息"""
    stats_manager = get_stats_manager()
    
    print("=" * 80)
    print("API 请求详细内容查看器")
    print("=" * 80)
    
    # 获取最近的请求
    recent = stats_manager.get_recent_requests(limit)
    
    if not recent:
        print("\n❌ 暂无请求记录")
        print("\n提示：请先发送一些API请求，然后再运行此脚本")
        return
    
    print(f"\n找到 {len(recent)} 条请求记录\n")
    
    for i, req in enumerate(recent, 1):
        print(f"\n{'='*80}")
        print(f"请求 #{i} (ID: {req['id']})")
        print(f"{'='*80}")
        
        # 基本信息
        print(f"\n📋 基本信息:")
        print(f"  时间: {req['timestamp']}")
        print(f"  IP地址: {req['client_ip'] or 'N/A'}")
        print(f"  API Key: {req['api_key']}")
        status = "✓ 成功" if req['success'] else "✗ 失败"
        print(f"  状态: {status}")
        
        if req['error_message']:
            print(f"  错误信息: {req['error_message']}")
        
        # 请求参数
        print(f"\n⚙️  请求参数:")
        print(f"  模型: {req['model_name'] or 'N/A'}")
        print(f"  文本长度: {req['text_length']} 字符")
        print(f"  语言: {req['text_lang'] or 'N/A'}")
        print(f"  输出格式: {req['media_type'] or 'N/A'}")
        print(f"  处理时间: {req['processing_time']}秒")
        
        # 文本内容
        if req.get('text_preview'):
            print(f"\n📝 文本内容:")
            print(f"  {'-'*76}")
            print(f"  {req['text_preview']}")
            print(f"  {'-'*76}")
            if req['text_length'] > 100:
                print(f"  (仅显示前100个字符，完整文本共{req['text_length']}字符)")
        
        # 参考音频信息
        if req.get('ref_audio_path'):
            print(f"\n🎵 参考音频:")
            print(f"  音频路径: {req['ref_audio_path']}")
            if req.get('prompt_text'):
                print(f"  提示文本: {req['prompt_text']}")
    
    print(f"\n{'='*80}")
    print(f"共显示 {len(recent)} 条请求记录")
    print(f"{'='*80}\n")


def view_single_request(request_id):
    """查看单个请求的详细信息"""
    stats_manager = get_stats_manager()
    
    print("=" * 80)
    print(f"查看请求 ID: {request_id}")
    print("=" * 80)
    
    detail = stats_manager.get_request_detail(request_id)
    
    if not detail:
        print(f"\n❌ 未找到请求ID为 {request_id} 的记录")
        return
    
    # 基本信息
    print(f"\n📋 基本信息:")
    print(f"  请求ID: {detail['id']}")
    print(f"  时间: {detail['timestamp']}")
    print(f"  IP地址: {detail['client_ip'] or 'N/A'}")
    print(f"  API Key: {detail['api_key']}")
    
    status = "✓ 成功" if detail['success'] else "✗ 失败"
    print(f"  状态: {status}")
    
    if detail['error_message']:
        print(f"  错误信息: {detail['error_message']}")
    
    # 请求参数
    print(f"\n⚙️  请求参数:")
    print(f"  模型: {detail['model_name'] or 'N/A'}")
    print(f"  文本长度: {detail['text_length']} 字符")
    print(f"  语言: {detail['text_lang'] or 'N/A'}")
    print(f"  输出格式: {detail['media_type'] or 'N/A'}")
    print(f"  处理时间: {detail['processing_time']}秒")
    
    # 文本内容
    if detail.get('text_preview'):
        print(f"\n📝 文本内容:")
        print(f"  {'-'*76}")
        print(f"  {detail['text_preview']}")
        print(f"  {'-'*76}")
        if detail['text_length'] > 100:
            print(f"  (仅显示前100个字符，完整文本共{detail['text_length']}字符)")
    
    # 参考音频信息
    if detail.get('ref_audio_path'):
        print(f"\n🎵 参考音频:")
        print(f"  音频路径: {detail['ref_audio_path']}")
        if detail.get('prompt_text'):
            print(f"  提示文本: {detail['prompt_text']}")
    
    print(f"\n{'='*80}\n")


def view_failed_requests():
    """查看所有失败的请求"""
    stats_manager = get_stats_manager()
    
    print("=" * 80)
    print("失败的请求记录")
    print("=" * 80)
    
    # 获取最近的请求
    recent = stats_manager.get_recent_requests(100)
    failed = [r for r in recent if not r['success']]
    
    if not failed:
        print("\n✅ 没有失败的请求记录")
        return
    
    print(f"\n找到 {len(failed)} 条失败的请求\n")
    
    for i, req in enumerate(failed, 1):
        print(f"\n失败请求 #{i} (ID: {req['id']})")
        print(f"  时间: {req['timestamp']}")
        print(f"  IP地址: {req['client_ip'] or 'N/A'}")
        print(f"  模型: {req['model_name'] or 'N/A'}")
        print(f"  错误: {req['error_message']}")
        
        if req.get('text_preview'):
            print(f"  文本: {req['text_preview'][:50]}...")
    
    print(f"\n{'='*80}\n")


def search_requests(keyword):
    """搜索包含关键词的请求"""
    stats_manager = get_stats_manager()
    
    print("=" * 80)
    print(f"搜索关键词: {keyword}")
    print("=" * 80)
    
    # 获取所有请求
    recent = stats_manager.get_recent_requests(1000)
    
    # 搜索
    results = []
    for req in recent:
        text = req.get('text_preview', '') or ''
        model = req.get('model_name', '') or ''
        if keyword.lower() in text.lower() or keyword.lower() in model.lower():
            results.append(req)
    
    if not results:
        print(f"\n❌ 未找到包含 '{keyword}' 的请求")
        return
    
    print(f"\n找到 {len(results)} 条匹配的请求\n")
    
    for i, req in enumerate(results, 1):
        print(f"\n匹配 #{i} (ID: {req['id']})")
        print(f"  时间: {req['timestamp']}")
        print(f"  模型: {req['model_name'] or 'N/A'}")
        if req.get('text_preview'):
            print(f"  文本: {req['text_preview'][:80]}...")
    
    print(f"\n{'='*80}\n")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='查看API请求详细内容')
    parser.add_argument('-n', '--number', type=int, default=20, 
                        help='显示最近N条请求 (默认: 20)')
    parser.add_argument('-i', '--id', type=int, 
                        help='查看指定ID的请求详情')
    parser.add_argument('-f', '--failed', action='store_true', 
                        help='只显示失败的请求')
    parser.add_argument('-s', '--search', type=str, 
                        help='搜索包含关键词的请求')
    
    args = parser.parse_args()
    
    try:
        if args.id:
            # 查看单个请求
            view_single_request(args.id)
        elif args.failed:
            # 查看失败的请求
            view_failed_requests()
        elif args.search:
            # 搜索请求
            search_requests(args.search)
        else:
            # 查看所有请求
            view_all_requests(args.number)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
