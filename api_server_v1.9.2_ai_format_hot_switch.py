# -*- coding: utf-8 -*-
"""
RESTful API 服务
提供HTTP接口访问知识库功能
支持文件全内容查看和关键词高亮
"""

from flask import Flask, request, jsonify, render_template_string, send_file
from flask_cors import CORS
from typing import Dict, Any, List, Optional
import json
import time
from datetime import datetime
import os
import re
import logging

app = Flask(__name__)
CORS(app)

kb = None
llm = None
query_tool = None
auto_updater = None


def init_app(knowledge_base, llm_instance=None, query_tool_instance=None):
    """初始化应用"""
    global kb, llm, query_tool, auto_updater
    kb = knowledge_base
    llm = llm_instance
    query_tool = query_tool_instance
    
    # 启动自动更新任务
    try:
        from auto_update import AutoUpdater
        from config import DATA_DIR
        
        auto_updater = AutoUpdater(kb, DATA_DIR)
        auto_updater.start()
        print("自动文件监控已启动")
    except Exception as e:
        print(f"自动文件监控启动失败: {e}")


@app.route('/')
def index():
    """首页"""
    html = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>知识库查询系统</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Microsoft YaHei', Arial, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #333; margin-bottom: 20px; text-align: center; }
        
        .search-box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .search-input { width: calc(100% - 100px); padding: 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px; }
        .search-input:focus { outline: none; border-color: #1890ff; box-shadow: 0 0 0 2px rgba(24,144,255,0.2); }
        textarea.search-input { resize: vertical; min-height: 80px; line-height: 1.5; }
        .search-btn { background: #1890ff; color: white; border: none; padding: 12px 30px; border-radius: 4px; cursor: pointer; margin-left: 10px; }
        .search-btn:hover { background: #40a9ff; }
        
        .results { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .result-item { border-bottom: 1px solid #eee; padding: 15px 0; cursor: pointer; }
        .result-item:last-child { border-bottom: none; }
        .result-item:hover { background: #f9f9f9; }
        .result-title { font-weight: bold; color: #1890ff; margin-bottom: 5px; font-size: 16px; cursor: pointer; }
        .result-title:hover { text-decoration: underline; color: #40a9ff; }
        .result-meta { color: #666; font-size: 14px; margin-bottom: 8px; }
        .result-content { color: #333; line-height: 1.6; font-size: 14px; }
        .result-actions { margin-top: 10px; }
        .btn-view { background: #52c41a; color: white; border: none; padding: 6px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
        .btn-view:hover { background: #73d13d; }
        .btn-open { background: #1890ff; color: white; border: none; padding: 6px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; margin-left: 10px; }
        .btn-open:hover { background: #40a9ff; }
        .action-btn { background: #1890ff; color: white; border: none; padding: 8px 20px; border-radius: 4px; cursor: pointer; font-size: 14px; margin: 5px 0; }
        .action-btn:hover { background: #40a9ff; }
        
        .stats { display: flex; gap: 20px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); flex: 1; text-align: center; }
        .stat-number { font-size: 32px; color: #1890ff; font-weight: bold; }
        .stat-label { color: #666; margin-top: 5px; }
        
        .system-info { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px; }
        .info-section { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); min-width: 0; }
        .info-section h3 { color: #333; margin: 0 0 15px 0; font-size: 16px; border-bottom: 2px solid #1890ff; padding-bottom: 10px; }
        .info-content { color: #666; line-height: 1.8; }
        .info-content ul { padding-left: 20px; margin: 10px 0; }
        .info-content li { margin: 8px 0; }
        .info-content p { margin: 10px 0; }
        
        #config-info { grid-column: 1 / -1; }
        
        .config-form { padding: 5px 0; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .config-form h4 { color: #333; margin: 15px 0 8px 0; font-size: 16px; border-bottom: 1px solid #eee; padding-bottom: 5px; grid-column: 1 / -1; }
        .config-form h4:first-child { margin-top: 0; }
        .form-group { margin-bottom: 12px; }
        .form-group label { display: block; margin-bottom: 5px; color: #666; font-weight: 500; min-width: 180px; }
        .form-group input, .form-group select { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; box-sizing: border-box; }
        .form-group input:focus, .form-group select:focus { outline: none; border-color: #1890ff; box-shadow: 0 0 0 2px rgba(24,144,255,0.2); }
        .form-actions { margin-top: 20px; text-align: right; grid-column: 1 / -1; }
        
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; }
        .tab { padding: 10px 20px; background: white; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; }
        .tab.active { background: #1890ff; color: white; border-color: #1890ff; }
        
        .highlight { background: #fff566; padding: 2px 4px; border-radius: 2px; font-weight: bold; }
        
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal-content { background: white; margin: 30px auto; padding: 0; border-radius: 8px; width: 90%; max-width: 1200px; max-height: 90vh; overflow: hidden; display: flex; flex-direction: column; }
        .modal-header { background: #1890ff; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
        .modal-title { font-size: 18px; font-weight: bold; cursor: pointer; }
        .modal-title:hover { text-decoration: underline; }
        .modal-close { background: none; border: none; color: white; font-size: 24px; cursor: pointer; padding: 0 10px; }
        .modal-close:hover { opacity: 0.8; }
        .modal-body { padding: 20px; overflow-y: auto; flex: 1; }
        .modal-meta { background: #f5f5f5; padding: 10px 15px; border-radius: 4px; margin-bottom: 15px; font-size: 14px; }
        .modal-meta span { margin-right: 20px; color: #666; }
        .file-content { white-space: pre-wrap; word-wrap: break-word; line-height: 1.8; font-size: 14px; color: #333; background: #fafafa; padding: 20px; border-radius: 4px; border: 1px solid #eee; }
        
        .format-toolbar { margin-bottom: 8px; display: flex; gap: 10px; align-items: center; }
        .format-btn { background: #f0f0f0; border: 1px solid #ddd; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; }
        .format-btn:hover { background: #e0e0e0; }
        .format-btn.active { background: #1890ff; color: white; border-color: #1890ff; }
        
        .formatted-content { font-size: 14px; line-height: 1.8; padding: 20px; background: #fafafa; border-radius: 8px; }
        .formatted-content .section { margin-bottom: 25px; padding: 20px; background: #fff; border-radius: 8px; border-left: 4px solid #1890ff; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .formatted-content .section-title { font-weight: bold; color: #1890ff; margin-bottom: 15px; font-size: 16px; padding-bottom: 8px; border-bottom: 2px solid #e6f7ff; }
        .formatted-content .key-value { display: flex; margin-bottom: 12px; padding: 8px 0; border-bottom: 1px dashed #eee; }
        .formatted-content .key { min-width: 150px; font-weight: 500; color: #666; }
        .formatted-content .value { flex: 1; color: #333; line-height: 1.6; }
        .formatted-content .list-item { padding: 10px 0 10px 25px; position: relative; margin-bottom: 5px; }
        .formatted-content .list-item:before { content: "•"; position: absolute; left: 5px; color: #1890ff; font-size: 18px; line-height: 1; }
        .formatted-content .code-block { background: #f5f5f5; padding: 20px; border-radius: 8px; font-family: Consolas, Monaco, monospace; font-size: 13px; overflow-x: auto; margin: 15px 0; border: 1px solid #e8e8e8; }
        .formatted-content .highlight-line { background: #fffbe6; padding: 2px 5px; border-radius: 2px; }
        .formatted-content .error-text { color: #f5222d; padding: 8px 12px; background: #fff2f0; border-radius: 4px; margin: 8px 0; }
        .formatted-content .success-text { color: #52c41a; padding: 8px 12px; background: #f6ffed; border-radius: 4px; margin: 8px 0; }
        .formatted-content .warning-text { color: #faad14; padding: 8px 12px; background: #fffbe6; border-radius: 4px; margin: 8px 0; }
        .formatted-content .info-text { color: #1890ff; padding: 8px 12px; background: #e6f7ff; border-radius: 4px; margin: 8px 0; }
        .formatted-content > div:not(.section):not(.code-block):not(.key-value):not(.list-item):not(.error-text):not(.success-text):not(.warning-text):not(.info-text) { margin-bottom: 10px; padding: 8px 0; }
        
        .loading { text-align: center; padding: 20px; color: #666; }
        
        .api-docs { background: white; padding: 20px; border-radius: 8px; }
        .api-endpoint { background: #f9f9f9; padding: 10px; margin: 10px 0; border-radius: 4px; border-left: 3px solid #1890ff; }
        .method { display: inline-block; padding: 2px 8px; background: #52c41a; color: white; border-radius: 3px; font-size: 12px; margin-right: 10px; }
        .method.post { background: #1890ff; }
        
        .search-info { background: #e6f7ff; padding: 10px 15px; border-radius: 4px; margin-bottom: 15px; font-size: 14px; color: #1890ff; }
        
        .kg-controls { margin-bottom: 20px; }
        .kg-stats { display: flex; gap: 20px; margin-bottom: 15px; }
        .kg-actions { display: flex; gap: 10px; flex-wrap: wrap; }
        .kg-search { margin-bottom: 20px; }
        .kg-container { display: flex; gap: 20px; height: 600px; }
        .kg-sidebar { width: 300px; background: white; border-radius: 8px; padding: 15px; overflow-y: auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .kg-sidebar h3 { margin: 0 0 15px 0; color: #333; border-bottom: 2px solid #1890ff; padding-bottom: 10px; }
        .kg-graph { flex: 1; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); position: relative; }
        #kg-network { width: 100%; height: 100%; }
        .kg-zoom-controls { position: absolute; right: 20px; top: 20px; display: flex; flex-direction: column; gap: 10px; z-index: 1000; }
        .kg-zoom-btn { width: 50px; height: 50px; border: none; border-radius: 8px; background: #1890ff; color: white; font-size: 28px; font-weight: bold; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.15); transition: all 0.3s; display: flex; align-items: center; justify-content: center; }
        .kg-zoom-btn:hover { background: #40a9ff; transform: scale(1.1); }
        .kg-zoom-btn:active { transform: scale(0.95); }
        .entity-item { padding: 10px; margin: 5px 0; background: #f5f5f5; border-radius: 4px; cursor: pointer; transition: all 0.3s; }
        .entity-item:hover { background: #e6f7ff; transform: translateX(5px); }
        .entity-item.active { background: #1890ff; color: white; }
        .entity-type { font-size: 12px; color: #666; margin-top: 5px; }
        .entity-item.active .entity-type { color: #e6f7ff; }
        .entity-item.show-all { background: #1890ff; color: white; font-weight: bold; }
        .entity-item.show-all:hover { background: #40a9ff; }
        
        .entity-modal { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 2000; }
        .entity-modal-content { background: white; border-radius: 8px; width: 90%; max-width: 600px; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
        .entity-modal-header { padding: 20px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; background: #f5f5f5; border-radius: 8px 8px 0 0; }
        .entity-modal-header h3 { margin: 0; color: #333; }
        .close-btn { background: none; border: none; font-size: 24px; color: #999; cursor: pointer; padding: 0 10px; }
        .close-btn:hover { color: #1890ff; }
        .entity-modal-body { padding: 20px; }
        .entity-info { margin-bottom: 20px; }
        .entity-info p { margin: 8px 0; color: #666; }
        .entity-properties h4 { margin: 15px 0 10px 0; color: #333; border-bottom: 1px solid #eee; padding-bottom: 5px; }
        .entity-properties p { margin: 8px 0; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 知识库查询系统</h1>
        
        <div class="stats" id="stats">
            <div class="stat-card">
                <div class="stat-number" id="total-docs">-</div>
                <div class="stat-label">文档总数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="total-types">-</div>
                <div class="stat-label">问题类型</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="today-queries">0</div>
                <div class="stat-label">今日查询</div>
            </div>
        </div>
        
        <div class="tabs">
            <div class="tab" onclick="switchTab('content', this)">内容查找</div>
            <div class="tab active" onclick="switchTab('search', this)">智能搜索</div>
            <div class="tab" onclick="switchTab('qa', this)">智能问答</div>
            <div class="tab" onclick="switchTab('regex', this)">正则匹配</div>
            <div class="tab" onclick="switchTab('knowledge', this)">知识图谱</div>
            <div class="tab" onclick="switchTab('system', this)">系统信息</div>
            <div class="tab" onclick="switchTab('api', this)">API 文档</div>
            <div class="tab" onclick="switchTab('help', this)">帮助信息</div>
        </div>
        
        <div id="search-panel">
            <div class="search-box">
                <input type="text" class="search-input" id="search-input" placeholder="输入关键词进行语义搜索..." onkeypress="if(event.keyCode==13)search()">
                <button class="search-btn" onclick="search()">搜索</button>
            </div>
            <div class="results" id="search-results"></div>
        </div>
        
        <div id="content-panel" style="display:none">
            <div class="search-box">
                <input type="text" class="search-input" id="content-input" placeholder="输入关键词精确查找内容（多个关键词用空格分隔）..." onkeypress="if(event.keyCode==13)searchContent()">
                <button class="search-btn" onclick="searchContent()">查找</button>
            </div>
            <div class="results" id="content-results"></div>
        </div>
        
        <div id="qa-panel" style="display:none">
            <div class="search-box">
                <textarea class="search-input" id="qa-input" placeholder="输入您的问题（支持多行输入）..." rows="4"></textarea>
                <button class="search-btn" onclick="askQuestion()">提问</button>
            </div>
            <div class="results" id="qa-results"></div>
        </div>
        
        <div id="regex-panel" style="display:none">
            <div class="search-box">
                <h2>🎯 正则匹配搜索</h2>
                
                <!-- 方式 1：快速模板 -->
                <div style="margin-bottom: 20px;">
                    <h3 style="margin-bottom: 10px;">⭐ 新手推荐 - 快速模板</h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px;">
                        <button class="action-btn" onclick="useRegexTemplate('1[3-9]\\d{9}', '手机号')" style="padding: 15px; text-align: left;">
                            📱 手机号<br><small style="font-size: 12px; color: #666;">18612345678</small>
                        </button>
                        <button class="action-btn" onclick="useRegexTemplate('OHQ\\d{10}', '订单号')" style="padding: 15px; text-align: left;">
                            🔢 订单号<br><small style="font-size: 12px; color: #666;">OHQ202401001</small>
                        </button>
                        <button class="action-btn" onclick="useRegexTemplate('错误 | 报错 | 失败 | 异常|Exception|Error', '错误信息')" style="padding: 15px; text-align: left;">
                            ⚠️ 错误信息<br><small style="font-size: 12px; color: #666;">报错、失败等</small>
                        </button>
                        <button class="action-btn" onclick="useRegexTemplate('\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}', '日期')" style="padding: 15px; text-align: left;">
                            📅 日期<br><small style="font-size: 12px; color: #666;">2024-01-15</small>
                        </button>
                        <button class="action-btn" onclick="useRegexTemplate('\\d{3,4}[-]?\\d{7,8}', '电话号码')" style="padding: 15px; text-align: left;">
                            📞 电话号码<br><small style="font-size: 12px; color: #666;">010-12345678</small>
                        </button>
                        <button class="action-btn" onclick="useRegexTemplate('\\d+', '数字')" style="padding: 15px; text-align: left;">
                            🔢 数字<br><small style="font-size: 12px; color: #666;">任意数字</small>
                        </button>
                    </div>
                </div>
                
                <!-- 方式 2：自然语言 -->
                <div style="margin-bottom: 20px;">
                    <h3 style="margin-bottom: 10px;">💡 智能推荐 - 自然语言搜索</h3>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <input type="text" class="search-input" id="regex-natural-input" 
                               placeholder="用自然语言描述，如：我想搜索包含手机号的文档" 
                               style="flex: 1;" 
                               onkeypress="if(event.keyCode==13) naturalLanguageSearch()">
                        <button class="search-btn" onclick="naturalLanguageSearch()">智能搜索</button>
                    </div>
                    <div style="margin-top: 8px; font-size: 13px; color: #666;">
                        示例："包含手机号的文档" | "同时包含套餐和变更的内容" | "包含错误或失败的文档"
                    </div>
                </div>
                
                <!-- 方式 3：自定义正则 -->
                <div style="margin-bottom: 20px;">
                    <h3 style="margin-bottom: 10px;">🔧 高级用户 - 自定义正则表达式</h3>
                    <input type="text" class="search-input" id="regex-pattern" 
                           placeholder="输入正则表达式，如：1[3-9]\d{9}" 
                           oninput="validateRegexPreview()" onkeypress="if(event.keyCode==13) regexSearch()">
                    <div style="margin-top: 10px; display: flex; gap: 10px; align-items: center;">
                        <label><input type="checkbox" id="regex-flag-i" checked> 忽略大小写</label>
                        <label><input type="checkbox" id="regex-flag-m"> 多行匹配</label>
                        <label><input type="checkbox" id="regex-flag-s"> 点号匹配所有</label>
                    </div>
                </div>
                
                <!-- 实时预览 -->
                <div id="regex-preview" style="margin-bottom: 15px; padding: 12px; background: #f6ffed; border: 1px solid #b7eb8f; border-radius: 4px; display: none;">
                    <div style="color: #52c41a; font-weight: bold; margin-bottom: 8px;">✅ 正则表达式有效</div>
                    <div id="regex-examples" style="font-size: 13px;"></div>
                </div>
                <div id="regex-error" style="margin-bottom: 15px; padding: 12px; background: #fff2f0; border: 1px solid #ffccc7; border-radius: 4px; display: none;">
                    <div style="color: #f5222d; font-weight: bold;">❌ 正则表达式无效</div>
                    <div id="regex-error-msg" style="font-size: 13px; margin-top: 5px;"></div>
                </div>
                
                <!-- 搜索字段选择 -->
                <div style="margin-bottom: 15px;">
                    <label style="font-weight: bold; margin-right: 10px;">搜索字段：</label>
                    <label><input type="checkbox" name="regex-field" value="content" checked> 内容</label>
                    <label><input type="checkbox" name="regex-field" value="solution" checked> 解决方案</label>
                    <label><input type="checkbox" name="regex-field" value="file_name"> 文件名</label>
                    <label><input type="checkbox" name="regex-field" value="problem_type"> 问题类型</label>
                    <label><input type="checkbox" name="regex-field" value="problem_id"> 问题 ID</label>
                </div>
                
                <button class="search-btn" onclick="regexSearch()" style="width: 200px; padding: 12px; font-size: 16px;">开始搜索</button>
                
                <!-- 常用模板参考 -->
                <div style="margin-top: 20px; padding: 15px; background: #f0f0f0; border-radius: 4px;">
                    <strong style="color: #1890ff;">📖 常用正则模板：</strong>
                    <ul style="margin: 10px 0; padding-left: 20px; font-size: 13px;">
                        <li><code>\d{11}</code> - 11 位数字（手机号）</li>
                        <li><code>OHQ\d{10}</code> - 订单号（OHQ 开头 +10 位数字）</li>
                        <li><code>\d{4}-\d{2}-\d{2}</code> - 日期格式（如：2024-01-15）</li>
                        <li><code>套餐.*变更</code> - 包含"套餐"和"变更"的内容</li>
                        <li><code>错误 | 失败 | 异常</code> - 包含任一关键词</li>
                        <li><code>1[3-9]\d{9}</code> - 中国移动手机号</li>
                    </ul>
                    <div style="font-size: 13px; color: #666;">
                        <strong>符号说明：</strong>
                        <code>\d</code> = 数字，<code>.</code> = 任意字符，<code>*</code> = 0 次或多次，<code>+</code> = 1 次或多次，<code>?</code> = 0 次或 1 次，<code>|</code> = 或
                    </div>
                </div>
            </div>
            <div class="results" id="regex-results"></div>
        </div>
        
        <div id="system-panel" style="display:none">
            <div class="search-box">
                <h2>系统信息</h2>
                <div class="system-info">
                    <div class="info-section">
                        <h3>问题分类</h3>
                        <div id="categories-list" class="info-content">加载中...</div>
                    </div>
                    <div class="info-section">
                        <h3>统计信息</h3>
                        <div id="stats-info" class="info-content">加载中...</div>
                    </div>
                    <div class="info-section">
                        <h3>配置信息</h3>
                        <div id="config-info" class="info-content">加载中...</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div id="api-panel" style="display:none">
            <div class="api-docs">
                <h2>API 接口文档</h2>
                
                <h3>搜索接口</h3>
                <div class="api-endpoint">
                    <span class="method">GET</span> /api/search?query=关键词&top_k=10
                </div>
                
                <h3>内容查找接口</h3>
                <div class="api-endpoint">
                    <span class="method">GET</span> /api/find_content?keywords=关键词 1,关键词 2
                </div>
                
                <h3>正则匹配接口</h3>
                <div class="api-endpoint">
                    <span class="method">GET</span> /api/regex_search?pattern=正则表达式&search_fields=content,solution&flags=i
                    <br><small>使用正则表达式搜索文档内容</small>
                    <br><small>参数：pattern=正则模式，search_fields=搜索字段（逗号分隔），flags=正则标志（i,m,s）</small>
                    <br><small>示例：/api/regex_search?pattern=1[3-9]\\d{9} 搜索所有手机号</small>
                </div>
                
                <h3>文件查看接口</h3>
                <div class="api-endpoint">
                    <span class="method">GET</span> /api/view_file?file_path=文件路径&keywords=关键词
                    <br><small>返回文件完整内容，关键词高亮标记</small>
                </div>
                
                <h3>打开文件接口</h3>
                <div class="api-endpoint">
                    <span class="method">GET</span> /api/open_file?file_path=文件路径
                    <br><small>使用系统默认工具打开文件</small>
                </div>
                
                <h3>智能问答接口</h3>
                <div class="api-endpoint">
                    <span class="method post">POST</span> /api/qa
                    <br><small>Body: {"question": "问题内容"}</small>
                </div>
                
                <h3>统计信息接口</h3>
                <div class="api-endpoint">
                    <span class="method">GET</span> /api/stats
                </div>
                
                <h3>问题分类接口</h3>
                <div class="api-endpoint">
                    <span class="method">GET</span> /api/categories
                </div>
                
                <h3>配置接口</h3>
                <div class="api-endpoint">
                    <span class="method">GET</span> /api/config
                    <br><small>获取当前配置</small>
                </div>
                <div class="api-endpoint">
                    <span class="method post">POST</span> /api/config
                    <br><small>保存配置 (Body: JSON配置对象)</small>
                </div>
                <div class="api-endpoint">
                    <span class="method post">POST</span> /api/restart
                    <br><small>重启服务器</small>
                </div>
                
                <h3>知识库管理接口</h3>
                <div class="api-endpoint">
                    <span class="method post">POST</span> /api/init
                    <br><small>全量重建知识库（清空所有数据）</small>
                </div>
                <div class="api-endpoint">
                    <span class="method post">POST</span> /api/rebuild
                    <br><small>增量更新知识库（只处理变更文件）</small>
                </div>
                
                <h3>推荐接口</h3>
                <div class="api-endpoint">
                    <span class="method">GET</span> /api/recommend?file_path=文件路径
                </div>
                
                <h3>摘要接口</h3>
                <div class="api-endpoint">
                    <span class="method">GET</span> /api/summary?file_path=文件路径
                </div>
            </div>
        </div>
        
        <div id="knowledge-panel" style="display:none">
            <div class="search-box">
                <h2>知识图谱</h2>
                <div class="kg-controls">
                    <div class="kg-stats">
                        <div class="stat-card">
                            <div class="stat-number" id="kg-entity-count">0</div>
                            <div class="stat-label">实体数量</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number" id="kg-relation-count">0</div>
                            <div class="stat-label">关系数量</div>
                        </div>
                    </div>
                    <div class="kg-actions">
                        <button class="action-btn" onclick="loadKnowledgeGraph()">加载图谱</button>
                        <button class="action-btn" onclick="extractFromText()">从文本抽取</button>
                        <button class="action-btn" onclick="batchExtract()">批量抽取</button>
                        <button class="action-btn" onclick="clearKnowledgeGraph()" style="background:#ff4d4f">清空图谱</button>
                    </div>
                </div>
                
                <div class="kg-search">
                    <input type="text" id="kg-search-input" placeholder="搜索实体..." class="search-input">
                    <button class="search-btn" onclick="searchEntities()">搜索</button>
                </div>
                
                <div class="kg-container">
                    <div class="kg-sidebar">
                        <h3>实体列表</h3>
                        <div id="kg-entity-list"></div>
                    </div>
                    <div class="kg-graph">
                        <div id="kg-network"></div>
                        <div class="kg-zoom-controls">
                            <button class="kg-zoom-btn" onclick="zoomIn()" title="放大">+</button>
                            <button class="kg-zoom-btn" onclick="zoomOut()" title="缩小">−</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div id="help-panel" style="display:none">
            <div class="search-box">
                <h2>帮助信息</h2>
                <div class="system-info">
                    <div class="info-section">
                        <h3>查询方式</h3>
                        <div class="info-content">
                            <ul>
                                <li>直接输入问题，如: 开户报错如何处理</li>
                                <li>按类型查询，如: type:开户报错 用户办理失败</li>
                            </ul>
                        </div>
                    </div>
                    <div class="info-section">
                        <h3>命令说明</h3>
                        <div class="info-content">
                            <ul>
                                <li>help - 显示本帮助信息</li>
                                <li>categories - 显示问题分类列表</li>
                                <li>stats - 显示知识库统计信息</li>
                                <li>config - 配置智谱大模型API Key</li>
                                <li>rebuild - 重建知识库索引</li>
                                <li>quit/exit - 退出系统</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal" id="file-modal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title" id="modal-title">文件内容</div>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="modal-meta" id="modal-meta"></div>
                <div class="file-content" id="modal-content"></div>
            </div>
        </div>
    </div>
    
    <script>
        let queryCount = 0;
        let searchKeywords = [];
        let contentKeywords = [];
        let qaKeywords = [];
        let currentFilePath = '';
        let defaultModelProvider = 'zhipu';
        let highlightKeywords = [];  // 用于存储后端返回的分词关键词
        
        // 配置信息（从config.py读取）
        const ZHIPU_API_KEY = '***';  // 已配置
        const ZHIPU_MODEL = 'glm-4';
        const REDIS_HOST = '127.0.0.1';
        const REDIS_PORT = '6380';
        
        function switchTab(tab, element) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            if (element) {
                element.classList.add('active');
            }
            document.getElementById('search-panel').style.display = tab === 'search' ? 'block' : 'none';
            document.getElementById('content-panel').style.display = tab === 'content' ? 'block' : 'none';
            document.getElementById('qa-panel').style.display = tab === 'qa' ? 'block' : 'none';
            document.getElementById('regex-panel').style.display = tab === 'regex' ? 'block' : 'none';
            document.getElementById('knowledge-panel').style.display = tab === 'knowledge' ? 'block' : 'none';
            document.getElementById('system-panel').style.display = tab === 'system' ? 'block' : 'none';
            document.getElementById('api-panel').style.display = tab === 'api' ? 'block' : 'none';
            document.getElementById('help-panel').style.display = tab === 'help' ? 'block' : 'none';
            
            // 切换到智能问答时，设置默认模型
            if (tab === 'qa') {
                const qaModelSelector = document.querySelector(`input[name="model-provider"][value="${defaultModelProvider}"]`);
                if (qaModelSelector) {
                    qaModelSelector.checked = true;
                }
            }
            
            // 加载系统信息
            if (tab === 'system') {
                loadSystemInfo();
            }
            
            // 加载知识图谱统计
            if (tab === 'knowledge') {
                loadKGStats();
            }
        }
        
        function loadSystemInfo() {
            // 加载问题分类
            fetch('/api/categories')
                .then(r => r.json())
                .then(data => {
                    if (data.categories && data.categories.length > 0) {
                        let html = '<ul>';
                        data.categories.forEach((cat, index) => {
                            html += `<li>${index + 1}. ${escapeHtml(cat)}</li>`;
                        });
                        html += '</ul>';
                        document.getElementById('categories-list').innerHTML = html;
                    } else {
                        document.getElementById('categories-list').innerHTML = '<p>暂无分类数据</p>';
                    }
                })
                .catch(err => {
                    document.getElementById('categories-list').innerHTML = `<p style="color:red">加载失败: ${err}</p>`;
                });
            
            // 加载统计信息
            fetch('/api/stats')
                .then(r => r.json())
                .then(data => {
                    let html = `
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                            <div class="stat-card" style="padding: 15px;">
                                <div class="stat-number" style="font-size: 28px;">${data.total_documents || 0}</div>
                                <div class="stat-label">文档总数</div>
                            </div>
                            <div class="stat-card" style="padding: 15px;">
                                <div class="stat-number" style="font-size: 28px;">${Object.keys(data.type_distribution || {}).length}</div>
                                <div class="stat-label">分类数量</div>
                            </div>
                        </div>
                    `;
                    
                    // 添加自动更新状态
                    if (data.auto_update) {
                        const autoUpdate = data.auto_update;
                        const status = autoUpdate.watching ? 
                            `<span style="color:green; font-weight: bold;">运行中</span>` : 
                            `<span style="color:red; font-weight: bold;">已停止</span>`;
                        
                        html += `
                            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-top: 15px;">
                                <div class="stat-card" style="padding: 15px;">
                                    <div class="stat-number" style="font-size: 20px;">${status}</div>
                                    <div class="stat-label">自动监控</div>
                                </div>
                                <div class="stat-card" style="padding: 15px;">
                                    <div class="stat-number" style="font-size: 20px;">${autoUpdate.watcher ? autoUpdate.watcher.file_count : 0}</div>
                                    <div class="stat-label">监控文件数</div>
                                </div>
                            </div>
                        `;
                    }
                    
                    document.getElementById('stats-info').innerHTML = html;
                })
                .catch(err => {
                    document.getElementById('stats-info').innerHTML = `<p style="color:red">加载失败: ${err}</p>`;
                });
            
            // 加载配置信息
            loadConfigInfo();
        }
        
        function loadConfigInfo() {
            fetch('/api/config')
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('config-info').innerHTML = `<p style="color:red">加载失败: ${data.error}</p>`;
                        return;
                    }
                    
                    const zhipu = data.zhipu || {};
                    const dataConfig = data.data || {};
                    const search = data.search || {};
                    const redis = data.redis || {};
                    const localModel = data.local_model || {};
                    const defaultProvider = data.default_provider || 'zhipu';
                    
                    // 更新全局默认模型提供商
                    defaultModelProvider = defaultProvider;
                    
                    document.getElementById('config-info').innerHTML = `
                        <div class="config-form">
                            <h4>Redis配置</h4>
                            <div class="form-group">
                                <label>主机地址:</label>
                                <input type="text" id="redis-host" value="${escapeHtml(redis.host || '127.0.0.1')}" placeholder="Redis主机地址">
                            </div>
                            <div class="form-group">
                                <label>端口:</label>
                                <input type="number" id="redis-port" value="${redis.port || 6379}" min="1" max="65535" placeholder="Redis端口">
                            </div>
                            <div class="form-group">
                                <label>密码:</label>
                                <input type="password" id="redis-password" value="${escapeHtml(redis.password || '')}" placeholder="Redis密码（可选）">
                            </div>
                            <div class="form-group">
                                <label>数据库:</label>
                                <input type="number" id="redis-db" value="${redis.db || 0}" min="0" max="15" placeholder="Redis数据库编号">
                            </div>
                            
                            <h4>智谱AI配置</h4>
                            <div class="form-group">
                                <label>API Key:</label>
                                <input type="password" id="zhipu-api-key" value="${zhipu.api_key || ''}" placeholder="请输入API Key">
                            </div>
                            <div class="form-group">
                                <label>模型:</label>
                                <select id="zhipu-model">
                                    <option value="glm-4" ${zhipu.model === 'glm-4' ? 'selected' : ''}>glm-4</option>
                                    <option value="glm-3-turbo" ${zhipu.model === 'glm-3-turbo' ? 'selected' : ''}>glm-3-turbo</option>
                                    <option value="glm-4-flash" ${zhipu.model === 'glm-4-flash' ? 'selected' : ''}>glm-4-flash</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>温度 (0-2):</label>
                                <input type="number" id="zhipu-temperature" value="${zhipu.temperature || 0.7}" min="0" max="2" step="0.1">
                            </div>
                            
                            <h4>本地模型配置</h4>
                            <div class="form-group">
                                <label>API地址:</label>
                                <input type="text" id="local-model-api-base" value="${escapeHtml(localModel.api_base || 'http://192.168.1.189:11434/api/chat')}" placeholder="Ollama API地址">
                            </div>
                            <div class="form-group">
                                <label>模型名称:</label>
                                <input type="text" id="local-model-name" value="${escapeHtml(localModel.model || 'deepseek-r1:1.5b')}" placeholder="模型名称">
                            </div>
                            <div class="form-group">
                                <label>温度 (0-2):</label>
                                <input type="number" id="local-model-temperature" value="${localModel.temperature || 0.7}" min="0" max="2" step="0.1">
                            </div>
                            
                            <h4>默认模型</h4>
                            <div class="form-group">
                                <label>选择默认模型:</label>
                                <select id="default-provider">
                                    <option value="zhipu" ${defaultProvider === 'zhipu' ? 'selected' : ''}>智谱 AI</option>
                                    <option value="local" ${defaultProvider === 'local' ? 'selected' : ''}>本地模型</option>
                                </select>
                            </div>
                            
                            <h4>向量模型配置</h4>
                            <div class="form-group">
                                <label>向量模型提供商:</label>
                                <select id="vector-model-provider">
                                    <option value="local" ${dataConfig.vector_model_provider === 'local' ? 'selected' : ''}>本地模型 (text2vec)</option>
                                    <option value="zhipu" ${dataConfig.vector_model_provider === 'zhipu' ? 'selected' : ''}>智谱 AI (embedding-2)</option>
                                </select>
                                <p style="font-size: 12px; color: #666; margin-top: 5px;">
                                    选择用于文本向量化的模型。本地模型速度快，智谱 AI 精度高但需要网络
                                </p>
                            </div>
                            
                            <h4>数据配置</h4>
                            <div class="form-group">
                                <label>数据目录:</label>
                                <input type="text" id="data-dir" value="${escapeHtml(dataConfig.data_dir || '')}" placeholder="数据目录路径">
                            </div>
                            <div class="form-group">
                                <label>本地模型路径:</label>
                                <input type="text" id="local-model-path" value="${escapeHtml(dataConfig.local_model_path || '')}" placeholder="本地模型路径">
                            </div>
                            <div class="form-group">
                                <label>向量维度:</label>
                                <input type="number" id="vector-dimension" value="${dataConfig.vector_dimension || 768}" min="128" max="2048" step="128">
                            </div>
                            
                            <h4>搜索配置</h4>
                            <div class="form-group">
                                <label>相似度阈值 (0-1):</label>
                                <input type="number" id="similarity-threshold" value="${search.similarity_threshold || 0.7}" min="0" max="1" step="0.1">
                            </div>
                            <div class="form-group">
                                <label>返回结果数:</label>
                                <input type="number" id="top-k-results" value="${search.top_k_results || 5}" min="1" max="50" step="1">
                            </div>
                            
                            <div class="form-actions">
                                <button class="search-btn" onclick="saveConfig()">保存配置</button>
                            </div>
                            
                            <div class="form-actions" style="margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                                <h4 style="margin-bottom: 15px; font-size: 16px; color: #333;">知识库管理</h4>
                                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                                    <button class="search-btn" onclick="initKnowledgeBase()" style="background: #ff4d4f; min-width: 100px;">全量重建</button>
                                    <button class="search-btn" onclick="rebuildKnowledgeBase()" style="background: #faad14; min-width: 100px;">增量更新</button>
                                </div>
                                <p style="margin-top: 10px; font-size: 12px; color: #999;">
                                    <strong>全量重建：</strong>清空所有数据并重新导入所有文件<br>
                                    <strong>增量更新：</strong>只处理新增或修改的文件
                                </p>
                            </div>
                        </div>
                    `;
                    
                    // 更新智能问答面板的模型选择器
                    const qaModelSelector = document.querySelector(`input[name="model-provider"][value="${defaultProvider}"]`);
                    if (qaModelSelector) {
                        qaModelSelector.checked = true;
                    }
                })
                .catch(err => {
                    document.getElementById('config-info').innerHTML = `<p style="color:red">加载失败: ${err}</p>`;
                });
        }
        
        function saveConfig() {
            const config = {
                redis: {
                    host: document.getElementById('redis-host').value,
                    port: parseInt(document.getElementById('redis-port').value),
                    password: document.getElementById('redis-password').value,
                    db: parseInt(document.getElementById('redis-db').value)
                },
                zhipu: {
                    api_key: document.getElementById('zhipu-api-key').value,
                    model: document.getElementById('zhipu-model').value,
                    temperature: parseFloat(document.getElementById('zhipu-temperature').value)
                },
                local_model: {
                    api_base: document.getElementById('local-model-api-base').value,
                    model: document.getElementById('local-model-name').value,
                    temperature: parseFloat(document.getElementById('local-model-temperature').value)
                },
                default_provider: document.getElementById('default-provider').value,
                data: {
                    data_dir: document.getElementById('data-dir').value,
                    local_model_path: document.getElementById('local-model-path').value,
                    vector_dimension: parseInt(document.getElementById('vector-dimension').value),
                    vector_model_provider: document.getElementById('vector-model-provider').value
                },
                search: {
                    similarity_threshold: parseFloat(document.getElementById('similarity-threshold').value),
                    top_k_results: parseInt(document.getElementById('top-k-results').value)
                }
            };
            
            fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(config)
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('配置保存成功！Redis配置已热生效，其他配置需要重启服务器。');
                } else {
                    alert(`保存失败: ${data.error || '未知错误'}`);
                }
            })
            .catch(err => {
                alert(`保存失败: ${err}`);
            });
        }
        
        function restartServer() {
            fetch('/api/restart', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('服务器正在重启，请稍后刷新页面...');
                    setTimeout(() => {
                        location.reload();
                    }, 3000);
                } else {
                    alert(`重启失败: ${data.error || '未知错误'}`);
                }
            })
            .catch(err => {
                alert(`重启失败: ${err}`);
            });
        }
        
        function initKnowledgeBase() {
            if (confirm('确认要清空所有数据并全量重建吗？此操作不可逆！')) {
                fetch('/api/init', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        alert('全量重建已在后台开始执行，请稍后查看统计信息确认结果。');
                    } else {
                        alert(`全量重建失败: ${data.error || '未知错误'}`);
                    }
                })
                .catch(err => {
                    alert(`全量重建失败: ${err}`);
                });
            }
        }
        
        function rebuildKnowledgeBase() {
            if (confirm('确认要进行增量更新吗？只会处理新增或修改的文件。')) {
                fetch('/api/rebuild', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        alert('增量更新已在后台开始执行，请稍后查看统计信息确认结果。');
                    } else {
                        alert(`增量更新失败: ${data.error || '未知错误'}`);
                    }
                })
                .catch(err => {
                    alert(`增量更新失败: ${err}`);
                });
            }
        }
        
        function loadStats() {
            fetch('/api/stats')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('total-docs').textContent = data.total_documents || 0;
                    document.getElementById('total-types').textContent = Object.keys(data.type_distribution || {}).length;
                });
        }
        
        function viewAllDocuments() {
            fetch('/api/documents')
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        alert('加载失败: ' + data.error);
                        return;
                    }
                    
                    const documents = data.documents || [];
                    const total = data.total || 0;
                    
                    let html = `<div class="search-info">共 ${total} 个文档</div>`;
                    
                    if (documents.length === 0) {
                        html += '<p style="color:red">暂无文档</p>';
                    } else {
                        documents.forEach((doc, index) => {
                            const fileName = doc.file_name || '未知';
                            const filePath = doc.file_path || '';
                            const problemType = doc.problem_type || '未知';
                            const problemId = doc.problem_id || '';
                            
                            html += `
                                <div class="result-item">
                                    <div class="result-title" onclick="viewFile('${encodeURIComponent(filePath)}', '${encodeURIComponent(fileName)}', '${problemType}', '${problemId}')" title="点击查看详情">${index + 1}. ${fileName}</div>
                                    <div class="result-meta">
                                        <span>类型: ${problemType}</span>
                                        <span>ID: ${problemId}</span>
                                        <span>长度: ${doc.content_length || 0} 字符</span>
                                    </div>
                                </div>
                            `;
                        });
                    }
                    
                    document.getElementById('search-results').innerHTML = html;
                    document.getElementById('search-input').value = '';
                })
                .catch(err => {
                    alert('加载失败: ' + err);
                });
        }
        
        function search() {
            const query = document.getElementById('search-input').value;
            if (!query) return;
            
            searchKeywords = query.split(/\s+/).filter(k => k.length > 0);
            
            document.getElementById('search-results').innerHTML = '<div class="loading">搜索中...</div>';
            queryCount++;
            document.getElementById('today-queries').textContent = queryCount;
            
            fetch(`/api/search?query=${encodeURIComponent(query)}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('search-results').innerHTML = `<p style="color:red">错误: ${data.error}</p>`;
                        return;
                    }
                    
                    const results = data.results || data || [];
                    highlightKeywords = data.keywords || searchKeywords;
                    
                    let html = `<div class="search-info">找到 ${results.length} 条结果，点击"查看全部"可查看完整内容</div>`;
                    results.forEach((item, index) => {
                        const content = item.content || '';
                        const preview = content.length > 200 ? content.substring(0, 200) + '...' : content;
                        const filePath = item.file_path || item.source || '';
                        const fileName = item.file_name || (filePath ? filePath.split(/[\\/]/).pop() : '未知');
                        
                        html += `
                            <div class="result-item">
                                <div class="result-title" onclick="openFile('${encodeURIComponent(filePath)}')" title="点击打开文件">${index + 1}. ${fileName}</div>
                                <div class="result-meta">
                                    <span>类型: ${item.problem_type || '未知'}</span>
                                    <span>ID: ${item.problem_id || '未知'}</span>
                                    <span>相似度: ${(item.similarity || 0).toFixed(4)}</span>
                                </div>
                                <div class="result-content">${highlightAndEscape(preview, highlightKeywords)}</div>
                                <div class="result-actions">
                                    <button class="btn-view" onclick="viewFile('${encodeURIComponent(filePath)}', '${encodeURIComponent(fileName)}', '${item.problem_type || ''}', '${item.problem_id || ''}', highlightKeywords)">查看全部</button>
                                </div>
                            </div>
                        `;
                    });
                    document.getElementById('search-results').innerHTML = html;
                })
                .catch(err => {
                    document.getElementById('search-results').innerHTML = `<p style="color:red">请求失败: ${err}</p>`;
                });
        }
        
        function searchContent() {
            const keywords = document.getElementById('content-input').value;
            if (!keywords) return;
            
            contentKeywords = keywords.split(/\s+/).filter(k => k.length > 0);
            
            document.getElementById('content-results').innerHTML = '<div class="loading">查找中...</div>';
            queryCount++;
            document.getElementById('today-queries').textContent = queryCount;
            
            fetch(`/api/find_content?keywords=${encodeURIComponent(keywords)}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('content-results').innerHTML = `<p style="color:red">错误: ${data.error}</p>`;
                        return;
                    }
                    
                    let html = `<div class="search-info">找到 ${data.length} 条包含所有关键词的结果</div>`;
                    data.forEach((item, index) => {
                        const content = item.content || '';
                        const preview = content.length > 200 ? content.substring(0, 200) + '...' : content;
                        const filePath = item.file_path || item.source || '';
                        const fileName = item.file_name || (filePath ? filePath.split(/[\\/]/).pop() : '未知');
                        
                        html += `
                            <div class="result-item">
                                <div class="result-title" onclick="openFile('${encodeURIComponent(filePath)}')" title="点击打开文件">${index + 1}. ${fileName}</div>
                                <div class="result-meta">
                                    <span>类型: ${item.problem_type || '未知'}</span>
                                    <span>ID: ${item.problem_id || '未知'}</span>
                                </div>
                                <div class="result-content">${highlightAndEscapeExact(preview, contentKeywords)}</div>
                                <div class="result-actions">
                                    <button class="btn-view" onclick="viewFile('${encodeURIComponent(filePath)}', '${encodeURIComponent(fileName)}', '${item.problem_type || ''}', '${item.problem_id || ''}', contentKeywords, true)">查看全部</button>
                                </div>
                            </div>
                        `;
                    });
                    document.getElementById('content-results').innerHTML = html;
                })
                .catch(err => {
                    document.getElementById('content-results').innerHTML = `<p style="color:red">请求失败: ${err}</p>`;
                });
        }
        
        function viewFileWithRegex(filePath, fileName, problemType, problemId, pattern) {
            const decodedPath = decodeURIComponent(filePath);
            const decodedName = decodeURIComponent(fileName);
            const decodedPattern = decodeURIComponent(pattern);
            
            currentFilePath = decodedPath;
            
            document.getElementById('modal-title').textContent = decodedName;
            document.getElementById('modal-title').title = '点击打开文件：' + decodedPath;
            document.getElementById('modal-title').onclick = function() { openFile(encodeURIComponent(filePath)); };
            document.getElementById('modal-meta').innerHTML = `
                <span>类型: ${problemType}</span>
                <span>ID: ${problemId}</span>
                <span>路径: ${decodedPath}</span>
                <button class="btn-open" onclick="openFile('${encodeURIComponent(filePath)}')">打开文件</button>
                <button class="btn-open" onclick="downloadFile('${encodeURIComponent(filePath)}')">下载文件</button>
            `;
            document.getElementById('modal-content').innerHTML = '<div class="loading">加载中...</div>';
            document.getElementById('file-modal').style.display = 'block';
            
            // 传递正则 pattern 参数
            fetch(`/api/view_file?file_path=${filePath}&file_name=${fileName}&pattern=${encodeURIComponent(pattern)}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('modal-content').innerHTML = `<p style="color:red">${data.error}</p>`;
                        return;
                    }
                    
                    const content = data.content || '无内容';
                    
                    // 存储原始内容供切换使用
                    window.rawContent = content;
                    window.regexPattern = decodedPattern;
                    window.currentFilePath = decodedPath;
                    window.aiFormattedContent = null; // 清除之前的AI格式化内容
                    
                    // 显示格式工具栏和内容
                    const toolbar = `
                        <div class="format-toolbar">
                            <span>显示格式:</span>
                            <button class="format-btn active" onclick="setFormat('raw')">原始文本</button>
                            <button class="format-btn" onclick="setFormat('smart')">智能格式</button>
                            <button class="format-btn" onclick="setFormat('section')">分段显示</button>
                            <button class="format-btn" onclick="setFormat('ai')">AI格式</button>
                            <button class="format-btn" onclick="setFormat('ai')">AI格式</button>
                        </div>
                    `;
                    
                    // 使用正则高亮
                    const highlightedContent = highlightRegexContent(content, decodedPattern);
                    
                    // 智能格式化 - 使用已有的 formatSmartContent 函数，传递 pattern 参数
                    const smartFormatted = formatSmartContent(content, [], false, decodedPattern);
                    
                    // 分段格式化 - 使用已有的 formatSectionContent 函数，传递 pattern 参数
                    const sectionFormatted = formatSectionContent(content, [], false, decodedPattern);
                    
                    // 默认显示智能格式
                    window.formattedContent = {
                        raw: `<pre>${escapeHtml(content)}</pre>`,
                        smart: smartFormatted,
                        section: sectionFormatted
                    };
                    
                    // 创建 content-display 容器
                    document.getElementById('modal-content').innerHTML = toolbar + 
                        `<div id="content-display" class="formatted-content">${smartFormatted}</div>`;
                    document.getElementById('modal-content').dataset.rawContent = content;
                })
                .catch(err => {
                    document.getElementById('modal-content').innerHTML = `<p style="color:red">加载失败：${err}</p>`;
                });
        }
        
        function viewFile(filePath, fileName, problemType, problemId, keywords, exactMatch = false) {
            const decodedPath = decodeURIComponent(filePath);
            const decodedName = decodeURIComponent(fileName);
            
            currentFilePath = decodedPath;
            
            document.getElementById('modal-title').textContent = decodedName;
            document.getElementById('modal-title').title = '点击打开文件: ' + decodedPath;
            document.getElementById('modal-title').onclick = function() { openFile(encodeURIComponent(filePath)); };
            document.getElementById('modal-meta').innerHTML = `
                <span>类型: ${problemType}</span>
                <span>ID: ${problemId}</span>
                <span>路径: ${decodedPath}</span>
                <button class="btn-open" onclick="openFile('${encodeURIComponent(filePath)}')">打开文件</button>
                <button class="btn-open" onclick="downloadFile('${encodeURIComponent(filePath)}')">下载文件</button>
            `;
            document.getElementById('modal-content').innerHTML = '<div class="loading">加载中...</div>';
            document.getElementById('file-modal').style.display = 'block';
            
            const keywordsParam = keywords ? keywords.join(',') : '';
            fetch(`/api/view_file?file_path=${filePath}&file_name=${fileName}&keywords=${encodeURIComponent(keywordsParam)}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('modal-content').innerHTML = `<p style="color:red">${data.error}</p>`;
                        return;
                    }
                    
                    const content = data.content || '无内容';
                    const apiKeywords = data.keywords || [];
                    const apiPattern = data.pattern || '';
                    
                    // 存储原始内容供切换使用
                    window.rawContent = content;
                    window.currentFilePath = decodedPath;
                    window.aiFormattedContent = null; // 清除之前的AI格式化内容
                    
                    // 显示格式工具栏和内容
                    const toolbar = `
                        <div class="format-toolbar">
                            <span>显示格式:</span>
                            <button class="format-btn active" onclick="setFormat('raw')">原始文本</button>
                            <button class="format-btn" onclick="setFormat('smart')">智能格式</button>
                            <button class="format-btn" onclick="setFormat('section')">分段显示</button>
                            <button class="format-btn" onclick="setFormat('ai')">AI格式</button>
                        </div>
                    `;
                    
                    // 如果有 pattern，使用正则高亮；否则使用关键词高亮
                    if (apiPattern) {
                        window.regexPattern = apiPattern;
                        const highlightedContent = highlightRegexContent(content, apiPattern);
                        const smartFormatted = formatSmartContent(content, [], false, apiPattern);
                        const sectionFormatted = formatSectionContent(content, [], false, apiPattern);
                        
                        window.formattedContent = {
                            raw: `<pre>${escapeHtml(content)}</pre>`,
                            smart: smartFormatted,
                            section: sectionFormatted
                        };
                        
                        document.getElementById('modal-content').innerHTML = toolbar + 
                            `<div id="content-display" class="formatted-content">${smartFormatted}</div>`;
                    } else {
                        window.contentKeywords = keywords && keywords.length > 0 ? keywords : apiKeywords;
                        window.exactMatch = exactMatch;
                        
                        const highlightFunc = exactMatch ? highlightAndEscapeExact : highlightAndEscape;
                        const highlightedContent = highlightFunc(content, window.contentKeywords);
                        document.getElementById('modal-content').innerHTML = toolbar + 
                            `<div id="content-display" class="file-content">${highlightedContent}</div>`;
                    }
                })
                .catch(err => {
                    document.getElementById('modal-content').innerHTML = `<p style="color:red">加载失败: ${err}</p>`;
                });
        }
        
        function setFormat(format) {
            const buttons = document.querySelectorAll('.format-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            const display = document.getElementById('content-display');
            const content = window.rawContent || '';
            const keywords = window.contentKeywords || [];
            const pattern = window.regexPattern || '';
            
            if (format === 'raw') {
                display.className = 'file-content';
                // 如果有 pattern，使用正则高亮；否则使用关键词高亮
                if (pattern) {
                    display.innerHTML = highlightRegexContent(content, pattern);
                } else {
                    const highlightFunc = window.exactMatch ? highlightAndEscapeExact : highlightAndEscape;
                    display.innerHTML = highlightFunc(content, keywords);
                }
            } else if (format === 'smart') {
                display.className = 'formatted-content';
                display.innerHTML = formatSmartContent(content, keywords, window.exactMatch, pattern);
            } else if (format === 'section') {
                display.className = 'formatted-content';
                display.innerHTML = formatSectionContent(content, keywords, window.exactMatch, pattern);
            } else if (format === 'ai') {
                display.className = 'formatted-content';
                // 检查是否已经有AI格式化的内容
                if (window.aiFormattedContent) {
                    display.innerHTML = window.aiFormattedContent;
                    return;
                }
                
                // 显示加载提示
                display.innerHTML = '<div class="loading">AI格式化中...</div>';
                
                // 调用AI格式化
                fetch('/api/ai_format', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        content: content,
                        keywords: keywords,
                        pattern: pattern,
                        exact_match: window.exactMatch
                    })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        let formattedContent = data.formatted_content;
                        
                        // 检查高亮标记是否被保留
                        if (pattern && !formattedContent.includes('<span class="highlight">')) {
                            // 正则高亮
                            formattedContent = highlightRegexContent(formattedContent, pattern);
                        } else if (keywords.length > 0 && !formattedContent.includes('<span class="highlight">')) {
                            // 关键词高亮
                            const highlightFunc = window.exactMatch ? highlightAndEscapeExact : highlightAndEscape;
                            formattedContent = highlightFunc(formattedContent, keywords);
                        }
                        
                        // 移除空的高亮标签
                        formattedContent = formattedContent.replace(/<span class="highlight">\s*<\/span>/g, '');
                        
                        // 转义 HTML 标签（保留高亮标签）
                        formattedContent = formattedContent.replace(/&lt;(?!span class="highlight")/g, '<').replace(/&gt;(?!\/span)/g, '>').replace(/&amp;/g, '&');
                        
                        window.aiFormattedContent = formattedContent;
                        display.innerHTML = formattedContent;
                    } else {
                        display.innerHTML = `<p style="color:red">AI格式化失败: ${data.error}</p>`;
                    }
                })
                .catch(err => {
                    display.innerHTML = `<p style="color:red">AI格式化失败: ${err}</p>`;
                });
            }
        }
        
        function formatSmartContent(content, keywords, exactMatch = false, pattern = '') {
            // 智能格式化
            let highlightFunc;
            if (pattern) {
                // 使用正则高亮
                highlightFunc = (text, kw) => highlightRegexContent(text, pattern);
            } else {
                highlightFunc = exactMatch ? highlightAndEscapeExact : highlightAndEscape;
            }
            let lines = content.split('\\n');
            let result = '';
            let inCodeBlock = false;
            let codeContent = '';
            
            for (let i = 0; i < lines.length; i++) {
                let line = lines[i];
                let trimmed = line.trim();
                
                // 检测代码块
                if (trimmed.startsWith('```') || trimmed.startsWith('---') || trimmed.startsWith('===')) {
                    if (inCodeBlock) {
                        const highlightedCode = highlightFunc(codeContent, keywords);
                        result += `<div class="code-block">${highlightedCode}</div>`;
                        codeContent = '';
                        inCodeBlock = false;
                    } else {
                        inCodeBlock = true;
                    }
                    continue;
                }
                
                if (inCodeBlock) {
                    codeContent += line + '\\n';
                    continue;
                }
                
                // 空行
                if (!trimmed) {
                    result += '<br>';
                    continue;
                }
                
                // 标题行 (以#开头或全大写或以数字.开头)
                if (trimmed.startsWith('#') || /^[一二三四五六七八九十]+[、.]/.test(trimmed) || /^[0-9]+[.、]/.test(trimmed)) {
                    const highlightedTitle = highlightFunc(trimmed, keywords);
                    result += `<div class="section-title">${highlightedTitle}</div>`;
                    continue;
                }
                
                // 键值对 (包含:或：)
                if (trimmed.includes('：') || trimmed.includes(':')) {
                    let parts = trimmed.split(/[：:]/);
                    if (parts.length >= 2 && parts[0].length < 30) {
                        const highlightedKey = highlightFunc(parts[0], keywords);
                        const highlightedValue = highlightFunc(parts.slice(1).join('：'), keywords);
                        result += `<div class="key-value"><span class="key">${highlightedKey}：</span><span class="value">${highlightedValue}</span></div>`;
                        continue;
                    }
                }
                
                // 列表项 (以-或*或数字.开头)
                if (/^[-*•]\s/.test(trimmed) || /^\d+[.)]\s/.test(trimmed)) {
                    const highlightedItem = highlightFunc(trimmed, keywords);
                    result += `<div class="list-item">${highlightedItem}</div>`;
                    continue;
                }
                
                // 错误/成功/警告关键词
                if (/错误|失败|异常|error|fail|exception/i.test(trimmed)) {
                    const highlightedError = highlightFunc(trimmed, keywords);
                    result += `<div class="error-text">${highlightedError}</div>`;
                    continue;
                }
                if (/成功|完成|success|ok/i.test(trimmed)) {
                    const highlightedSuccess = highlightFunc(trimmed, keywords);
                    result += `<div class="success-text">${highlightedSuccess}</div>`;
                    continue;
                }
                if (/警告|注意|warning|warn/i.test(trimmed)) {
                    const highlightedWarning = highlightFunc(trimmed, keywords);
                    result += `<div class="warning-text">${highlightedWarning}</div>`;
                    continue;
                }
                
                // 普通行
                const highlightedLine = highlightFunc(trimmed, keywords);
                result += `<div>${highlightedLine}</div>`;
            }
            
            if (inCodeBlock && codeContent) {
                const highlightedCode = highlightFunc(codeContent, keywords);
                result += `<div class="code-block">${highlightedCode}</div>`;
            }
            
            return result;
        }
        
        function formatSectionContent(content, keywords, exactMatch = false, pattern = '') {
            // 按段落分段显示
            let highlightFunc;
            if (pattern) {
                // 使用正则高亮
                highlightFunc = (text, kw) => highlightRegexContent(text, pattern);
            } else {
                highlightFunc = exactMatch ? highlightAndEscapeExact : highlightAndEscape;
            }
            let sections = content.split(/\\n\\s*\\n/);
            let result = '';
            let sectionNum = 1;
            
            for (let section of sections) {
                if (!section.trim()) continue;
                
                // 获取段落的第一行作为标题
                let lines = section.trim().split('\\n');
                let title = lines[0].trim();
                
                // 如果第一行太长，使用默认标题
                if (title.length > 50) {
                    title = '段落 ' + sectionNum;
                }
                
                const highlightedTitle = highlightFunc(title, keywords);
                const highlightedBody = highlightFunc(section.trim(), keywords).replace(/\\n/g, '<br>');
                
                result += `<div class="section">
                    <div class="section-title">${sectionNum}. ${highlightedTitle}</div>
                    <div class="section-body">${highlightedBody}</div>
                </div>`;
                
                sectionNum++;
            }
            
            return result;
        }
        
        function closeModal() {
            document.getElementById('file-modal').style.display = 'none';
        }
        
        function openFile(filePath) {
            if (!filePath) {
                alert('文件路径为空');
                return;
            }
            
            // 解码一次看看实际路径
            var decodedPath = decodeURIComponent(filePath);
            console.log('编码路径: ' + filePath);
            console.log('解码路径: ' + decodedPath);
            
            fetch(`/api/open_file?file_path=${filePath}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        alert('打开文件失败: ' + data.error);
                    }
                })
                .catch(err => {
                    alert('请求失败: ' + err);
                });
        }
        
        function downloadFile(filePath) {
            if (!filePath) {
                alert('文件路径为空');
                return;
            }
            
            // 使用数据流下载
            const link = document.createElement('a');
            link.href = `/api/download_file?file_path=${filePath}`;
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // ============== 正则匹配搜索功能 ==============
        
        // 使用模板
        function useRegexTemplate(pattern, name) {
            document.getElementById('regex-pattern').value = pattern;
            validateRegexPreview();
            // 自动滚动到搜索框
            document.getElementById('regex-pattern').focus();
        }
        
        // 验证正则表达式并预览
        function validateRegexPreview() {
            const pattern = document.getElementById('regex-pattern').value;
            const previewDiv = document.getElementById('regex-preview');
            const errorDiv = document.getElementById('regex-error');
            const examplesDiv = document.getElementById('regex-examples');
            
            if (!pattern) {
                previewDiv.style.display = 'none';
                errorDiv.style.display = 'none';
                return;
            }
            
            try {
                new RegExp(pattern);
                // 正则有效
                errorDiv.style.display = 'none';
                
                // 生成示例
                const examples = generateRegexExamples(pattern);
                if (examples.length > 0) {
                    let html = '<div style="margin-top: 5px;"><strong>匹配示例：</strong></div><ul style="margin: 5px 0; padding-left: 20px;">';
                    examples.forEach(ex => {
                        html += `<li style="color: #52c41a;">✓ ${escapeHtml(ex)}</li>`;
                    });
                    html += '</ul>';
                    examplesDiv.innerHTML = html;
                } else {
                    examplesDiv.innerHTML = '';
                }
                
                previewDiv.style.display = 'block';
            } catch (e) {
                // 正则无效
                previewDiv.style.display = 'none';
                errorDiv.style.display = 'block';
                document.getElementById('regex-error-msg').textContent = e.message;
            }
        }
        
        // 生成正则示例
        function generateRegexExamples(pattern) {
            const examplesMap = {
                '1[3-9]\\d{9}': ['18692310000', '13912345678', '19812345678'],
                'OHQ\\d{10}': ['OHQ202401001', 'OHQ202402002', 'OHQ202403003'],
                '\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}': ['2024-01-15', '2023/12/31', '2024-6-1'],
                '错误 | 报错 | 失败 | 异常|Exception|Error': ['错误', '失败', '系统报错', '操作异常'],
                '\\d{3,4}[-]?\\d{7,8}': ['010-12345678', '021-87654321', '12345678'],
                '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}': ['test@example.com', 'user@domain.cn'],
                '\\d+': ['123', '4567', '89012'],
                '¥?\\d+[,.]?\\d*': ['100', '¥1,234.56', '99.99'],
            };
            
            return examplesMap[pattern] || [];
        }
        
        // 自然语言搜索
        function naturalLanguageSearch() {
            const text = document.getElementById('regex-natural-input').value.trim();
            if (!text) {
                alert('请输入搜索内容');
                return;
            }
            
            queryCount++;
            document.getElementById('today-queries').textContent = queryCount;
            
            document.getElementById('regex-results').innerHTML = '<div class="loading">智能搜索中...</div>';
            
            const params = new URLSearchParams({
                pattern: text,
                natural_language: 'true',
                search_fields: getSelectedRegexFields().join(','),
                flags: getRegexFlags()
            });
            
            fetch(`/api/regex_search?${params}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('regex-results').innerHTML = `<p style="color:red">错误：${escapeHtml(data.error)}</p>`;
                        return;
                    }
                    
                    displayRegexResults(data);
                })
                .catch(err => {
                    document.getElementById('regex-results').innerHTML = `<p style="color:red">请求失败：${err}</p>`;
                });
        }
        
        // 正则搜索
        function regexSearch() {
            const pattern = document.getElementById('regex-pattern').value.trim();
            if (!pattern) {
                alert('请输入正则表达式或选择模板');
                return;
            }
            
            // 验证正则表达式
            try {
                new RegExp(pattern);
            } catch (e) {
                alert('正则表达式无效：' + e.message);
                return;
            }
            
            queryCount++;
            document.getElementById('today-queries').textContent = queryCount;
            
            document.getElementById('regex-results').innerHTML = '<div class="loading">搜索中...</div>';
            
            const params = new URLSearchParams({
                pattern: pattern,
                natural_language: 'false',
                search_fields: getSelectedRegexFields().join(','),
                flags: getRegexFlags()
            });
            
            fetch(`/api/regex_search?${params}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('regex-results').innerHTML = `<p style="color:red">错误：${escapeHtml(data.error)}</p>`;
                        return;
                    }
                    
                    displayRegexResults(data);
                })
                .catch(err => {
                    document.getElementById('regex-results').innerHTML = `<p style="color:red">请求失败：${err}</p>`;
                });
        }
        
        // 获取选中的搜索字段
        function getSelectedRegexFields() {
            const checkboxes = document.querySelectorAll('input[name="regex-field"]:checked');
            return Array.from(checkboxes).map(cb => cb.value);
        }
        
        // 获取正则标志
        function getRegexFlags() {
            const flags = [];
            if (document.getElementById('regex-flag-i').checked) flags.push('i');
            if (document.getElementById('regex-flag-m').checked) flags.push('m');
            if (document.getElementById('regex-flag-s').checked) flags.push('s');
            return flags.join(',');
        }
        
        // 显示正则搜索结果
        function displayRegexResults(data) {
            let html = `<div class="search-info">
                            找到 ${data.total} 条匹配结果
                            （正则模式：${escapeHtml(data.pattern)}）
                        </div>`;
            
            if (data.total === 0) {
                html += '<p style="color:red">未找到匹配的文档</p>';
            } else {
                data.results.forEach((item, index) => {
                    const content = item.content || '';
                    const preview = content.length > 200 
                        ? content.substring(0, 200) + '...' 
                        : content;
                    const filePath = item.file_path || item.source || '';
                    const fileName = item.file_name || 
                                    (filePath ? filePath.split(/[\\/]/).pop() : '未知');
                    
                    // 高亮显示匹配的内容
                    const highlightedContent = highlightRegexContent(preview, data.pattern);
                    
                    // 简单转义单引号和反斜杠
                    const safeFilePath = filePath.replace(/'/g, "\\'").replace(/\\\\/g, "\\\\\\\\");
                    const safeFileName = fileName.replace(/'/g, "\\'").replace(/\\\\/g, "\\\\\\\\");
                    const safePattern = data.pattern.replace(/'/g, "\\'").replace(/\\\\/g, "\\\\\\\\");
                    
                    html += `
                        <div class="result-item">
                            <div class="result-title">${index + 1}. ${escapeHtml(fileName)}</div>
                            <div class="result-meta">
                                <span>类型：${escapeHtml(item.problem_type || '未知')}</span>
                                <span>ID: ${escapeHtml(item.problem_id || '未知')}</span>
                                ${item.matched_field ? `<span>匹配字段：${escapeHtml(item.matched_field)}</span>` : ''}
                            </div>
                            <div class="result-content">${highlightedContent}</div>
                            <div class="result-actions">
                                <button class="btn-view" onclick="viewFileWithRegex('${safeFilePath}', '${safeFileName}', '${item.problem_type || ''}', '${item.problem_id || ''}', '${safePattern}')">
                                    查看全部
                                </button>
                            </div>
                        </div>
                    `;
                });
            }
            
            document.getElementById('regex-results').innerHTML = html;
        }
        
        // 高亮正则匹配的内容 - 用于正则查询
        function highlightRegexContent(text, pattern) {
            try {
                // 先转义 HTML 特殊字符
                const escapedText = escapeHtml(text);
                
                // 直接使用正则表达式匹配并高亮所有匹配的内容
                try {
                    const regex = new RegExp(pattern, 'gi');
                    return escapedText.replace(regex, "<span class='highlight'>$&</span>");
                } catch (e) {
                    console.warn('正则表达式无法直接应用:', e);
                    // 如果正则无效，返回转义后的文本
                    return escapedText;
                }
                
            } catch (e) {
                console.error('高亮错误:', e);
                return escapeHtml(text);
            }
        }
        
        function highlightText(text, keywords) {
            if (!keywords || keywords.length === 0) return text;
            
            let result = text;
            keywords.forEach(keyword => {
                if (keyword && keyword.trim()) {
                    const trimmedKeyword = keyword.trim();
                    const escaped = escapeRegex(trimmedKeyword);
                    const regex = new RegExp(`(${escaped})`, 'gi');
                    result = result.replace(regex, '<span class="highlight">$1</span>');
                }
            });
            
            return result;
        }
        
        function highlightAndEscape(text, keywords) {
            if (!keywords || keywords.length === 0) return escapeHtml(text);
            
            // 如果只有一个长关键词，尝试拆分
            let finalKeywords = [];
            keywords.forEach(keyword => {
                if (keyword && keyword.trim()) {
                    if (keyword.length > 2) {
                        // 尝试拆分长关键词
                        const parts = splitKeyword(keyword);
                        finalKeywords = finalKeywords.concat(parts);
                    } else {
                        finalKeywords.push(keyword);
                    }
                }
            });
            
            let result = text;
            finalKeywords.forEach(keyword => {
                if (keyword && keyword.trim()) {
                    const trimmedKeyword = keyword.trim();
                    const escaped = escapeRegex(trimmedKeyword);
                    const regex = new RegExp(`(${escaped})`, 'gi');
                    result = result.replace(regex, '___HIGHLIGHT_START___$1___HIGHLIGHT_END___');
                }
            });
            
            result = escapeHtml(result);
            result = result.replace(/___HIGHLIGHT_START___/g, '<span class="highlight">');
            result = result.replace(/___HIGHLIGHT_END___/g, '</span>');
            
            return result;
        }
        
        function highlightAndEscapeExact(text, keywords) {
            // 精准匹配高亮，不进行分词
            if (!keywords || keywords.length === 0) return escapeHtml(text);
            
            let result = text;
            keywords.forEach(keyword => {
                if (keyword && keyword.trim()) {
                    const trimmedKeyword = keyword.trim();
                    const escaped = escapeRegex(trimmedKeyword);
                    const regex = new RegExp(`(${escaped})`, 'gi');
                    result = result.replace(regex, '___HIGHLIGHT_START___$1___HIGHLIGHT_END___');
                }
            });
            
            result = escapeHtml(result);
            result = result.replace(/___HIGHLIGHT_START___/g, '<span class="highlight">');
            result = result.replace(/___HIGHLIGHT_END___/g, '</span>');
            
            return result;
        }
        
        function splitKeyword(keyword) {
            // 简单的中文分词：按常见词汇拆分
            const commonWords = ['公众', '宽带', '用户', '号码', '类型', '服务', '产品', '套餐', '业务', '订单', '施工', '竣工', '开户', '变更', '新增', '删除', '资料', '信息', '操作', '系统', '数据', '省份', '集中', '生产', '测试', '判断', '下发', '需要', '完成', '成功', '失败', '错误', '异常', '问题', '解决', '方法', '步骤', '流程', '配置', '设置', '查询', '修改', '更新', '添加', '移除', '安装', '卸载', '启动', '停止', '重启', '登录', '退出', '注册', '认证', '授权', '权限', '角色', '用户', '账号', '密码', '手机', '电话', '邮箱', '地址', '名称', '编号', '代码', '状态', '结果', '原因', '描述', '备注', '说明', '提示', '警告', '注意', '重要', '紧急', '优先', '级别', '分类', '标签', '属性', '参数', '选项', '功能', '模块', '组件', '接口', '服务', '请求', '响应', '数据', '文件', '目录', '路径', '服务器', '客户端', '浏览器', '网络', '连接', '断开', '超时', '重试', '失败', '成功', '完成', '进行', '开始', '结束', '创建', '删除', '修改', '查询', '保存', '取消', '确认', '返回', '跳转', '刷新', '加载', '显示', '隐藏', '展开', '折叠', '排序', '筛选', '搜索', '过滤', '分组', '统计', '分析', '报表', '图表', '导出', '导入', '打印', '下载', '上传', '发送', '接收', '转发', '回复', '评论', '点赞', '收藏', '分享', '关注', '订阅', '通知', '消息', '提醒', '公告', '新闻', '文章', '帖子', '评论', '回复', '点赞', '收藏', '分享', '关注', '订阅', '通知', '消息', '提醒', '公告', '新闻', '文章', '帖子'];
            
            let result = [];
            let remaining = keyword;
            
            // 先尝试匹配常见词
            commonWords.forEach(word => {
                if (remaining.includes(word)) {
                    result.push(word);
                    remaining = remaining.replace(new RegExp(word, 'g'), '');
                }
            });
            
            // 如果还有剩余字符，按2个字符一组拆分
            if (remaining.length > 0) {
                for (let i = 0; i < remaining.length; i += 2) {
                    const part = remaining.substring(i, i + 2);
                    if (part.trim() && part.length > 1) {
                        result.push(part);
                    }
                }
            }
            
            return result.length > 0 ? result : [keyword];
        }
        
        function escapeRegex(string) {
            var chars = ['.', '*', '+', '?', '^', '$', '{', '}', '(', ')', '|', '[', ']', '\\\\'];
            var result = string;
            for (var i = 0; i < chars.length; i++) {
                result = result.split(chars[i]).join('\\\\' + chars[i]);
            }
            return result;
        }
        
        // 智能问答快捷键支持
        document.addEventListener('DOMContentLoaded', function() {
            const qaInput = document.getElementById('qa-input');
            if (qaInput) {
                qaInput.addEventListener('keydown', function(e) {
                    // Ctrl+Enter 或 Cmd+Enter 提交
                    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                        e.preventDefault();
                        askQuestion();
                    }
                });
            }
        });
        
        function askQuestion() {
            const question = document.getElementById('qa-input').value;
            if (!question) return;
            
            // 设置当前关键词为问题内容（用于高亮显示）
            qaKeywords = question.split(/\s+/).filter(k => k.length > 0);
            
            document.getElementById('qa-results').innerHTML = '<div class="loading">思考中...</div>';
            queryCount++;
            document.getElementById('today-queries').textContent = queryCount;
            
            fetch('/api/qa', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    question: question
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    document.getElementById('qa-results').innerHTML = `<p style="color:red">错误: ${data.error}</p>`;
                    return;
                }
                
                let html = '';
                
                html += `
                    <div class="result-item">
                        <div class="result-title">AI回答</div>
                        <div class="result-content" style="white-space: pre-wrap;">${escapeHtml(data.answer)}</div>
                    </div>
                `;
                
                if (data.reference_docs && data.reference_docs.length > 0) {
                    html += '<div class="result-title" style="margin-top:20px; padding: 15px 0;">参考来源</div>';
                    data.reference_docs.forEach((item, index) => {
                        const filePath = item.source || '';
                        const fileName = item.file_name || (filePath ? filePath.split(/[\\/]/).pop() : '未知');
                        const similarity = item.similarity || 0;
                        html += `
                            <div class="result-item">
                                <div class="result-title" onclick="openFile('${encodeURIComponent(filePath)}')" title="点击打开文件">${index + 1}. ${fileName}</div>
                                <div class="result-meta">
                                    <span>类型: ${item.problem_type || '未知'}</span>
                                    <span>ID: ${item.problem_id || '未知'}</span>
                                    <span>相似度: ${(similarity * 100).toFixed(1)}%</span>
                                </div>
                                <div class="result-content">${highlightAndEscape(item.content || '无内容', qaKeywords)}</div>
                                <div class="result-actions">
                                    <button class="btn-view" onclick="viewFile('${encodeURIComponent(filePath)}', '${encodeURIComponent(fileName)}', '${item.problem_type || ''}', '${item.problem_id || ''}', qaKeywords)">查看全部</button>
                                    <button class="btn-view" onclick="downloadFile('${encodeURIComponent(filePath)}')">下载</button>
                                </div>
                            </div>
                        `;
                    });
                }
                
                document.getElementById('qa-results').innerHTML = html;
            })
            .catch(err => {
                document.getElementById('qa-results').innerHTML = `<p style="color:red">请求失败: ${err}</p>`;
            });
        }
        
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeModal();
            }
        });
        
        document.getElementById('file-modal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });
        
        // ==================== 知识图谱相关函数 ====================
        
        let kgNetwork = null;
        
        function loadKGStats() {
            fetch('/api/kg/stats')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('kg-entity-count').textContent = data.entity_count || 0;
                    document.getElementById('kg-relation-count').textContent = data.relation_count || 0;
                })
                .catch(err => console.error('加载知识图谱统计失败:', err));
        }
        
        function loadKnowledgeGraph() {
            fetch('/api/kg/graph')
                .then(r => r.json())
                .then(data => {
                    displayKnowledgeGraph(data);
                    loadEntityList(data.nodes);
                })
                .catch(err => {
                    console.error('加载知识图谱失败:', err);
                    alert(`加载知识图谱失败: ${err}`);
                });
        }
        
        function displayKnowledgeGraph(data) {
            const container = document.getElementById('kg-network');
            
            const nodes = new vis.DataSet(data.nodes.map(node => ({
                id: node.id,
                label: node.label,
                group: node.group,
                title: node.title,
                font: { size: 14, face: 'Microsoft YaHei' },
                shadow: true
            })));
            
            const edges = new vis.DataSet(data.edges.map(edge => ({
                id: edge.id,
                from: edge.from,
                to: edge.to,
                label: edge.label,
                title: edge.title,
                arrows: 'to',
                font: { size: 12, face: 'Microsoft YaHei', align: 'middle' },
                smooth: { type: 'curvedCW', roundness: 0.2 }
            })));
            
            const graphData = { nodes, edges };
            
            const options = {
                nodes: {
                    shape: 'dot',
                    size: 20,
                    borderWidth: 2,
                    shadow: true,
                    color: {
                        background: '#e6f7ff',
                        border: '#1890ff',
                        highlight: {
                            background: '#1890ff',
                            border: '#0050b3'
                        }
                    }
                },
                edges: {
                    width: 2,
                    shadow: true,
                    color: { color: '#999', highlight: '#1890ff' }
                },
                physics: {
                    enabled: true,
                    barnesHut: {
                        gravitationalConstant: -3000,
                        centralGravity: 0.3,
                        springLength: 100
                    }
                },
                interaction: {
                    hover: true,
                    tooltipDelay: 200,
                    zoomView: true,
                    zoomSpeed: 0.2
                }
            };
            
            if (kgNetwork) {
                kgNetwork.destroy();
            }
            
            kgNetwork = new vis.Network(container, graphData, options);
            
            kgNetwork.on('click', function(params) {
                if (params.nodes.length > 0) {
                    const nodeId = params.nodes[0];
                    showEntityDetails(nodeId, null);
                }
            });
        }
        
        function zoomIn() {
            if (kgNetwork) {
                const scale = kgNetwork.getScale();
                kgNetwork.moveTo({ scale: scale * 1.3 });
            }
        }
        
        function zoomOut() {
            if (kgNetwork) {
                const scale = kgNetwork.getScale();
                kgNetwork.moveTo({ scale: scale / 1.3 });
            }
        }
        
        function showAllEntities() {
            // 显示全部实体图谱
            loadKnowledgeGraph();
            
            // 清除选中状态
            document.querySelectorAll('.entity-item').forEach(item => {
                item.classList.remove('active');
            });
        }
        
        function showEntityDetails(entityId, event) {
            fetch(`/api/kg/entity/${entityId}`)
                .then(r => r.json())
                .then(data => {
                    const entity = data.entity;
                    const relations = data.relations;
                    
                    document.querySelectorAll('.entity-item').forEach(item => {
                        item.classList.remove('active');
                    });
                    
                    if (event) {
                        event.target.closest('.entity-item')?.classList.add('active');
                    }
                    
                    // 更新图谱显示
                    fetch(`/api/kg/graph?entity_id=${entityId}&depth=2`)
                        .then(r => r.json())
                        .then(graphData => {
                            displayKnowledgeGraph(graphData);
                        });
                })
                .catch(err => console.error('获取实体详情失败:', err));
        }
        
        function showEntityModal(entity) {
            // 创建弹窗
            const modal = document.createElement('div');
            modal.className = 'entity-modal';
            modal.innerHTML = `
                <div class="entity-modal-content">
                    <div class="entity-modal-header">
                        <h3>${entity.name}</h3>
                        <button class="close-btn" onclick="closeEntityModal()">×</button>
                    </div>
                    <div class="entity-modal-body">
                        <div class="entity-info">
                            <p><strong>类型:</strong> ${entity.type}</p>
                            <p><strong>创建时间:</strong> ${new Date(entity.created_at).toLocaleString()}</p>
                            <p><strong>ID:</strong> ${entity.id}</p>
                        </div>
                        <div class="entity-properties">
                            <h4>属性:</h4>
                            ${Object.keys(entity.properties).length > 0 ? 
                                Object.entries(entity.properties).map(([key, value]) => 
                                    `<p><strong>${key}:</strong> ${value}</p>`).join('') : 
                                '<p>无属性</p>'}
                        </div>
                    </div>
                </div>
            `;
            
            // 添加到页面
            document.body.appendChild(modal);
            
            // 点击弹窗外部关闭
            modal.onclick = function(e) {
                if (e.target === modal) {
                    closeEntityModal();
                }
            };
        }
        
        function closeEntityModal() {
            const modal = document.querySelector('.entity-modal');
            if (modal) {
                document.body.removeChild(modal);
            }
        }
        
        function loadEntityList(nodes) {
            const listContainer = document.getElementById('kg-entity-list');
            let html = '';
            
            // 添加显示全部按钮
            html += `<div class="entity-item show-all" onclick="showAllEntities()">
                <div>显示全部实体</div>
                <div class="entity-type">共 ${nodes.length} 个实体</div>
            </div>`;
            
            nodes.forEach(node => {
                html += `<div class="entity-item" onclick="showEntityDetails('${node.id}', event)">
                    <div>${node.label}</div>
                    <div class="entity-type">${node.group}</div>
                </div>`;
            });
            
            listContainer.innerHTML = html || '<p style="color:#999">暂无实体</p>';
        }
        
        function searchEntities() {
            const keyword = document.getElementById('kg-search-input').value.trim();
            if (!keyword) {
                alert('请输入搜索关键词');
                return;
            }
            
            fetch(`/api/kg/entities?keyword=${encodeURIComponent(keyword)}`)
                .then(r => r.json())
                .then(data => {
                    loadEntityList(data.entities.map(e => ({
                        id: e.id,
                        label: e.name,
                        group: e.type
                    })));
                })
                .catch(err => {
                    console.error('搜索实体失败:', err);
                    alert(`搜索实体失败: ${err}`);
                });
        }
        
        function extractFromText() {
            const text = prompt('请输入要抽取知识的文本：');
            if (!text) return;
            
            if (!confirm('确定要从该文本中抽取知识吗？这将调用 LLM 进行分析。')) return;
            
            fetch('/api/kg/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert(`抽取成功！\\n实体数：${data.entities_count}\\n关系数：${data.relations_count}`);
                    loadKGStats();
                    loadKnowledgeGraph();
                } else {
                    alert(`抽取失败：${data.error}`);
                }
            })
            .catch(err => {
                console.error('知识抽取失败:', err);
                alert(`知识抽取失败: ${err}`);
            });
        }
        
        function batchExtract() {
            const limit = prompt('请输入要处理的文档数量（建议不超过10）：', '5');
            if (!limit) return;
            
            if (!confirm(`确定要从 ${limit} 个文档中批量抽取知识吗？\\n这可能需要较长时间。`)) return;
            
            alert('批量抽取已开始，请稍候...');
            
            fetch('/api/kg/batch_extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ limit: parseInt(limit) })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert(`批量抽取完成！\\n` +
                          `处理文档：${data.processed_documents}/${data.total_documents}\\n` +
                          `实体数：${data.saved_entities}\\n` +
                          `关系数：${data.saved_relations}`);
                    loadKGStats();
                    loadKnowledgeGraph();
                } else {
                    alert(`批量抽取失败：${data.error}`);
                }
            })
            .catch(err => {
                console.error('批量抽取失败:', err);
                alert(`批量抽取失败: ${err}`);
            });
        }
        
        function clearKnowledgeGraph() {
            if (!confirm('确定要清空知识图谱吗？此操作不可逆！')) return;
            if (!confirm('再次确认：真的要清空所有实体和关系吗？')) return;
            
            fetch('/api/kg/clear', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        alert('知识图谱已清空');
                        loadKGStats();
                        if (kgNetwork) {
                            kgNetwork.destroy();
                            kgNetwork = null;
                        }
                        document.getElementById('kg-entity-list').innerHTML = '<p style="color:#999">暂无实体</p>';
                    } else {
                        alert('清空失败');
                    }
                })
                .catch(err => {
                    console.error('清空知识图谱失败:', err);
                    alert(`清空知识图谱失败: ${err}`);
                });
        }
        
        loadStats();
    </script>
</body>
</html>
    '''
    return render_template_string(html)


@app.route('/api/search')
def api_search():
    """搜索接口"""
    query = request.args.get('query', '')
    top_k = int(request.args.get('top_k', 10))
    
    if not query:
        return jsonify({'error': '缺少query参数'}), 400
    
    try:
        # 确保模型加载完成
        if hasattr(kb, 'vector_store') and hasattr(kb.vector_store, 'embedding_model'):
            em = kb.vector_store.embedding_model
            if hasattr(em, 'model_loaded') and not em.model_loaded:
                import time
                for i in range(30):
                    if em.model_loaded:
                        break
                    time.sleep(0.5)
        
        if hasattr(kb, 'vector_store') and hasattr(kb.vector_store, 'search'):
            results = kb.vector_store.search(query, top_k=top_k)
        else:
            query_result = kb.query(query, top_k=top_k)
            results = query_result.get('results', [])
        
        for r in results:
            if 'embedding' in r:
                del r['embedding']
            if 'file_path' not in r and 'source' in r:
                r['file_path'] = r['source']
        
        # 使用jieba进行中文分词，用于前端高亮
        try:
            import jieba
            keywords = list(jieba.cut(query))
            # 过滤掉空字符串和标点符号
            keywords = [k for k in keywords if k.strip() and len(k) > 1]
        except:
            # 如果jieba不可用，使用原始查询词
            keywords = [query]
        
        return jsonify({
            'results': results,
            'keywords': keywords
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/view_file')
def api_view_file():
    """查看文件完整内容"""
    file_path = request.args.get('file_path', '')
    keywords_str = request.args.get('keywords', '')
    file_name = request.args.get('file_name', '')
    pattern = request.args.get('pattern', '')  # 正则表达式 pattern
    
    if not file_path and not file_name and not keywords_str and not pattern:
        return jsonify({'error': '缺少文件参数'}), 400
    
    try:
        from urllib.parse import unquote
        file_path = unquote(file_path) if file_path else ''
        file_name = unquote(file_name) if file_name else ''
        pattern = unquote(pattern) if pattern else ''
        
        results = []
        
        # 方法1: 直接从文件名索引搜索
        if file_name:
            import redis
            from config import REDIS_CONFIG
            r = redis.Redis(**REDIS_CONFIG)
            idx_key = 'workorder:filename_idx'
            
            fn_lower = file_name.lower()
            idx_data = r.hget(idx_key, fn_lower)
            if idx_data:
                import json
                keys = json.loads(idx_data)
                if keys:
                    doc = r.execute_command('JSON.GET', keys[0], '$')
                    doc_data = json.loads(doc)[0]
                    results = [doc_data]
        
        # 方法2: 通过find_document_by_filename搜索
        if not results and file_path:
            results = kb.find_document_by_filename(file_path)
        
        if not results and file_name:
            results = kb.find_document_by_filename(file_name)
        
        # 方法3: 从keywords中提取文件名搜索
        if not results and keywords_str:
            keywords_list = [k.strip() for k in keywords_str.split(',') if k.strip()]
            for kw in keywords_list:
                if len(kw) > 5:
                    results = kb.find_document_by_filename(kw)
                    if results:
                        break
        
        # 方法 4: 直接搜索 Redis 中的所有文档（改进版）
        if not results and (file_name or file_path):
            import redis
            from config import REDIS_CONFIG
            r = redis.Redis(**REDIS_CONFIG)
            
            # 提取搜索关键词
            search_name = os.path.basename(file_name or file_path).lower()
            search_path = (file_path or file_name).lower().replace('\\', '/')
            
            # 移除多余空格进行模糊匹配
            search_name_no_space = search_name.replace(' ', '')
            search_path_no_space = search_path.replace(' ', '')
            
            # 提取纯文件名（不含扩展名）用于更宽松的匹配
            search_name_base = os.path.splitext(search_name)[0]
            
            all_keys = r.keys('workorder:*')
            doc_keys = [k for k in all_keys if b'filename_idx' not in k and b'type_idx' not in k and b'fp:' not in k and not k.endswith(b'stats_cache')]
            
            # 优先精确匹配文件名
            for key in doc_keys:
                try:
                    doc = r.execute_command('JSON.GET', key, '$')
                    if not doc:
                        continue
                    doc_data = json.loads(doc)[0]
                    fn = doc_data.get('file_name', '').lower()
                    fp = doc_data.get('file_path', '') or doc_data.get('source', '')
                    fp_lower = fp.lower().replace('\\', '/') if fp else ''
                    
                    # 移除空格后的版本
                    fn_no_space = fn.replace(' ', '')
                    fp_no_space = fp_lower.replace(' ', '') if fp_lower else ''
                    
                    # 提取纯文件名（不含扩展名）
                    fn_base = os.path.splitext(fn)[0]
                    
                    # 精确匹配文件名
                    if fn == search_name:
                        results = [doc_data]
                        break
                    
                    # 匹配文件路径
                    if fp_lower == search_path:
                        results = [doc_data]
                        break
                    
                    # 模糊匹配（移除空格后匹配）
                    if fn_no_space == search_name_no_space:
                        results = [doc_data]
                        break
                    
                    # 模糊匹配路径
                    if fp_no_space and fp_no_space == search_path_no_space:
                        results = [doc_data]
                        break
                    
                    # 路径包含匹配（处理路径层级差异）
                    if search_path and fp_lower and (search_path in fp_lower or fp_lower in search_path):
                        results = [doc_data]
                        break
                    
                    # 文件名包含匹配（处理文件名差异）
                    if search_name in fn or fn in search_name:
                        results = [doc_data]
                        break
                    
                    # 纯文件名匹配（不含扩展名）
                    if fn_base and search_name_base and (fn_base == search_name_base or search_name_base in fn_base or fn_base in search_name_base):
                        results = [doc_data]
                        break
                        
                except Exception as e:
                    continue
        
        if not results:
            return jsonify({'error': '文件未找到', 'file_path': file_path, 'file_name': file_name}), 404
        
        doc = results[0]
        content = doc.get('content', '')
        
        keywords = [k.strip() for k in keywords_str.split(',') if k.strip()] if keywords_str else []
        
        actual_file_path = doc.get('file_path', '') or doc.get('source', '') or file_path or file_name
        
        return jsonify({
            'file_path': actual_file_path,
            'file_name': doc.get('file_name', os.path.basename(actual_file_path) if actual_file_path else '未知'),
            'problem_type': doc.get('problem_type', ''),
            'problem_id': doc.get('problem_id', ''),
            'content': content,
            'keywords': keywords,
            'pattern': pattern,  # 返回正则 pattern
            'content_length': len(content)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/find_file')
def api_find_file():
    """文件查找接口"""
    filename = request.args.get('filename', '')
    
    if not filename:
        return jsonify({'error': '缺少filename参数'}), 400
    
    try:
        results = kb.find_document_by_filename(filename)
        
        for r in results:
            if 'embedding' in r:
                del r['embedding']
            if 'file_path' not in r and 'source' in r:
                r['file_path'] = r['source']
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/find_content')
def api_find_content():
    """内容查找接口"""
    keywords_str = request.args.get('keywords', '')
    
    if not keywords_str:
        return jsonify({'error': '缺少 keywords 参数'}), 400
    
    # 优先使用逗号分割
    if ',' in keywords_str:
        keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
    else:
        # 没有逗号，使用空格分割
        keywords = keywords_str.split()
    
    # 如果仍然没有关键词，尝试中文分词
    if not keywords and keywords_str:
        try:
            import jieba
            # 使用 jieba 进行中文分词
            keywords = [k.strip() for k in jieba.cut(keywords_str) if k.strip() and len(k.strip()) > 1]
        except:
            # 如果 jieba 不可用，使用原始字符串
            keywords = [keywords_str]
    
    logging.info(f"内容查找 - 原始关键词：{keywords_str}, 分词后：{keywords}")
    
    try:
        results = kb.find_by_content(keywords)
        
        logging.info(f"内容查找 - 找到 {len(results)} 条结果")
        
        for r in results:
            if 'embedding' in r:
                del r['embedding']
            if 'file_path' not in r and 'source' in r:
                r['file_path'] = r['source']
        
        return jsonify(results)
    except Exception as e:
        logging.error(f"内容查找失败：{str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/qa', methods=['POST'])
def api_qa():
    """智能问答接口 - 支持本地模型和智谱模型"""
    data = request.get_json()
    question = data.get('question', '')
    
    if not question:
        return jsonify({'error': '缺少question参数'}), 400
    
    try:
        from config import LOCAL_MODEL_CONFIG, ZHIPU_CONFIG, DEFAULT_MODEL_PROVIDER
        
        # 先进行向量搜索，获取相关文档
        vector_result = kb.query(question, top_k=5)
        
        # 根据默认配置选择模型提供商
        model_provider = DEFAULT_MODEL_PROVIDER
        
        # 根据模型提供商调用不同的API
        if model_provider == 'local':
            return call_local_model(question, vector_result)
        else:
            return call_zhipu_model(question, vector_result)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def call_local_model(question, vector_result):
    """调用本地Ollama模型"""
    try:
        import requests
        from config import LOCAL_MODEL_CONFIG
        
        api_url = LOCAL_MODEL_CONFIG['api_base']
        model_name = LOCAL_MODEL_CONFIG['model']
        temperature = LOCAL_MODEL_CONFIG['temperature']
        
        # 构建上下文
        context = _build_context(vector_result.get('results', []))
        
        prompt = f"""你是一个专业的业务问题分析专家。请根据以下知识库内容，深入分析用户问题并提供完整的解决方案。

用户问题：{question}

相关知识库内容：
{context}

请按以下格式详细回答：

## 1. 问题类型
[根据知识库内容，判断问题所属的具体分类，如：开户报错、套餐变更、移机改号、销户问题、合约问题、费用问题、服务状态、终端问题、跨域业务、实名认证等]

## 2. 问题描述
[详细描述用户遇到的问题，包括问题的具体表现、影响范围等]

## 3. 问题原因分析
[深入分析问题产生的根本原因，可能包括：
- 系统层面的原因
- 业务流程的原因
- 数据配置的原因
- 用户操作的原因
- 其他可能的原因]

## 4. 解决方案
[提供详细、可操作的解决步骤，包括：
### 4.1 立即处理措施
[能够快速解决问题的临时措施]

### 4.2 根本解决方案
[彻底解决问题的完整步骤，按序号列出]
1. 第一步：...
2. 第二步：...
3. 第三步：...
...

### 4.3 验证方法
[如何验证问题是否已经解决]

## 5. 预防措施
[如何避免类似问题再次发生]

## 6. 注意事项
[处理过程中需要特别注意的事项，包括：
- 操作风险
- 数据备份要求
- 权限要求
- 时间窗口要求
- 其他重要提示]

## 7. 相关案例参考
[简要总结知识库中相关案例的关键信息，包括案例编号、相似度和来源文件]

请确保回答内容详实、专业、可操作性强，帮助客服人员快速理解和解决问题。"""
        
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 2000
            }
        }
        
        response = requests.post(api_url, json=payload, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            message = result.get('message', {})
            content = message.get('content', '')
            
            # 过滤掉思考内容（deepseek-r1模型会返回
            if '<think>' in content and '</think>' in content:
                import re
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            # 提取参考文档信息（参照智谱AI的实现）
            reference_docs = []
            for i, result in enumerate(vector_result.get('results', [])[:5], 1):
                reference_docs.append({
                    'index': i,
                    'file_name': result.get('file_name', '未知'),
                    'source': result.get('source', '未知'),
                    'similarity': result.get('similarity', 0),
                    'content': result.get('content', '')[:100] + '...' if result.get('content') else '无',
                    'problem_type': result.get('problem_type', '未知'),
                    'problem_id': result.get('problem_id', '未知')
                })
            
            return jsonify({
                'answer': content,
                'reference_docs': reference_docs
            })
        else:
            return jsonify({'error': f'本地模型调用失败: {response.status_code} - {response.text}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'本地模型调用异常: {str(e)}'}), 500


def call_zhipu_model(question, vector_result):
    """调用智谱AI模型"""
    try:
        from config import ZHIPU_CONFIG
        from zhipu_llm import ZhipuLLM
        
        # 构建上下文
        context = _build_context(vector_result.get('results', []))
        
        prompt = f"""你是一个专业的业务问题分析专家。请根据以下知识库内容，深入分析用户问题并提供完整的解决方案。

用户问题：{question}

相关知识库内容：
{context}

请按以下格式详细回答：

## 1. 问题类型
[根据知识库内容，判断问题所属的具体分类，如：开户报错、套餐变更、移机改号、销户问题、合约问题、费用问题、服务状态、终端问题、跨域业务、实名认证等]

## 2. 问题描述
[详细描述用户遇到的问题，包括问题的具体表现、影响范围等]

## 3. 问题原因分析
[深入分析问题产生的根本原因，可能包括：
- 系统层面的原因
- 业务流程的原因
- 数据配置的原因
- 用户操作的原因
- 其他可能的原因]

## 4. 解决方案
[提供详细、可操作的解决步骤，包括：
### 4.1 立即处理措施
[能够快速解决问题的临时措施]

### 4.2 根本解决方案
[彻底解决问题的完整步骤，按序号列出]
1. 第一步：...
2. 第二步：...
3. 第三步：...
...

### 4.3 验证方法
[如何验证问题是否已经解决]

## 5. 预防措施
[如何避免类似问题再次发生]

## 6. 注意事项
[处理过程中需要特别注意的事项，包括：
- 操作风险
- 数据备份要求
- 权限要求
- 时间窗口要求
- 其他重要提示]

## 7. 相关案例参考
[简要总结知识库中相关案例的关键信息，包括案例编号、相似度和来源文件]

请确保回答内容详实、专业、可操作性强，帮助客服人员快速理解和解决问题。"""
        
        llm = ZhipuLLM(ZHIPU_CONFIG)
        messages = [{"role": "user", "content": prompt}]
        answer = llm.chat(messages, temperature=ZHIPU_CONFIG['temperature'])
        
        # 提取参考文档信息（参照智谱AI的实现）
        reference_docs = []
        for i, result in enumerate(vector_result.get('results', [])[:5], 1):
            reference_docs.append({
                'index': i,
                'file_name': result.get('file_name', '未知'),
                'source': result.get('source', '未知'),
                'similarity': result.get('similarity', 0),
                'content': result.get('content', '')[:100] + '...' if result.get('content') else '无',
                'problem_type': result.get('problem_type', '未知'),
                'problem_id': result.get('problem_id', '未知')
            })
        
        return jsonify({
            'answer': answer,
            'reference_docs': reference_docs
        })
        
    except Exception as e:
        return jsonify({'error': f'智谱模型调用异常: {str(e)}'}), 500


def _build_context(search_results, max_length=8000):
    """构建上下文"""
    context_parts = []
    total_length = 0
    
    for i, result in enumerate(search_results[:5], 1):
        content = result.get('content', '')
        source = result.get('source', '未知')
        similarity = result.get('similarity', 0)
        
        part = f"\n【案例{i}】(相似度: {similarity:.2%}, 来源: {source})\n{content}\n"
        
        if total_length + len(part) > max_length:
            break
        
        context_parts.append(part)
        total_length += len(part)
    
    return ''.join(context_parts)


@app.route('/api/categories')
def api_categories():
    """问题分类接口"""
    try:
        categories = kb.get_categories()
        return jsonify({'categories': categories})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def api_get_config():
    """获取配置接口"""
    try:
        from config import (
            ZHIPU_CONFIG, DATA_DIR, LOCAL_MODEL_PATH,
            VECTOR_DIMENSION, SIMILARITY_THRESHOLD, TOP_K_RESULTS,
            REDIS_CONFIG, LOCAL_MODEL_CONFIG, DEFAULT_MODEL_PROVIDER,
            VECTOR_MODEL_PROVIDER
        )
        
        config_data = {
            'redis': {
                'host': REDIS_CONFIG.get('host', '127.0.0.1'),
                'password': REDIS_CONFIG.get('password', ''),
                'port': REDIS_CONFIG.get('port', 6379),
                'db': REDIS_CONFIG.get('db', 0)
            },
            'zhipu': {
                'api_key': ZHIPU_CONFIG.get('api_key', ''),
                'model': ZHIPU_CONFIG.get('model', 'glm-4'),
                'temperature': ZHIPU_CONFIG.get('temperature', 0.7)
            },
            'local_model': {
                'api_base': LOCAL_MODEL_CONFIG.get('api_base', 'http://192.168.1.189:11434/api/chat'),
                'model': LOCAL_MODEL_CONFIG.get('model', 'deepseek-r1:1.5b'),
                'temperature': LOCAL_MODEL_CONFIG.get('temperature', 0.7)
            },
            'default_provider': DEFAULT_MODEL_PROVIDER,
            'data': {
                'data_dir': DATA_DIR,
                'local_model_path': LOCAL_MODEL_PATH,
                'vector_dimension': VECTOR_DIMENSION,
                'vector_model_provider': VECTOR_MODEL_PROVIDER
            },
            'search': {
                'similarity_threshold': SIMILARITY_THRESHOLD,
                'top_k_results': TOP_K_RESULTS
            }
        }
        
        return jsonify(config_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['POST'])
def api_save_config():
    """保存配置接口"""
    try:
        from config import update_config
        
        data = request.get_json()
        redis_needs_reconnect = False
        
        # 保存Redis配置
        if 'redis' in data:
            redis_config = data['redis']
            if 'host' in redis_config:
                update_config('redis', 'host', redis_config['host'])
            if 'password' in redis_config:
                update_config('redis', 'password', redis_config['password'])
            if 'port' in redis_config:
                update_config('redis', 'port', str(redis_config['port']))
            if 'db' in redis_config:
                update_config('redis', 'db', str(redis_config['db']))
            
            redis_needs_reconnect = True
        
        # 保存智谱配置
        if 'zhipu' in data:
            zhipu = data['zhipu']
            if 'api_key' in zhipu:
                update_config('zhipu', 'api_key', zhipu['api_key'])
            if 'model' in zhipu:
                update_config('zhipu', 'model', zhipu['model'])
            if 'temperature' in zhipu:
                update_config('zhipu', 'temperature', str(zhipu['temperature']))
        
        # 保存本地模型配置
        if 'local_model' in data:
            local_model = data['local_model']
            if 'api_base' in local_model:
                update_config('local_model', 'api_base', local_model['api_base'])
            if 'model' in local_model:
                update_config('local_model', 'model', local_model['model'])
            if 'temperature' in local_model:
                update_config('local_model', 'temperature', str(local_model['temperature']))
        
        # 保存默认模型提供商
        if 'default_provider' in data:
            update_config('model', 'default_provider', data['default_provider'])
        
        # 保存数据配置
        if 'data' in data:
            data_config = data['data']
            if 'data_dir' in data_config:
                update_config('data', 'data_dir', data_config['data_dir'])
            if 'local_model_path' in data_config:
                update_config('model', 'local_model_path', data_config['local_model_path'])
            if 'vector_dimension' in data_config:
                update_config('model', 'vector_dimension', str(data_config['vector_dimension']))
            if 'vector_model_provider' in data_config:
                update_config('model', 'vector_model_provider', data_config['vector_model_provider'])
        
        # 保存搜索配置
        if 'search' in data:
            search = data['search']
            if 'similarity_threshold' in search:
                update_config('search', 'similarity_threshold', str(search['similarity_threshold']))
            if 'top_k_results' in search:
                update_config('search', 'top_k_results', str(search['top_k_results']))
        
        # 如果修改了Redis配置，重新连接Redis
        if redis_needs_reconnect and kb and kb.vector_store:
            try:
                kb.vector_store.reconnect_redis()
                print("Redis连接已更新")
            except Exception as e:
                print(f"Redis重连失败: {e}")
        
        return jsonify({'success': True, 'message': '配置保存成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/restart', methods=['POST'])
def api_restart():
    """重启服务器接口"""
    try:
        import sys
        import os
        
        def restart_server():
            print("正在重启服务器...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        
        import threading
        restart_thread = threading.Thread(target=restart_server)
        restart_thread.daemon = True
        restart_thread.start()
        
        return jsonify({'success': True, 'message': '服务器正在重启...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/init', methods=['POST'])
def api_init():
    """全量重建知识库接口"""
    try:
        import threading
        
        def init_worker():
            try:
                print("\n开始全量重建...")
                print("  - 清空现有数据...")
                kb.clear_all()
                
                print("  - 重建索引...")
                kb.create_index(force_recreate=True)
                
                print("  - 全量导入数据...")
                success = kb.initialize()
                
                if success:
                    stats = kb.get_statistics()
                    print(f"\n全量重建完成，当前知识库共 {stats['total_documents']} 条记录")
                else:
                    print("\n全量重建失败")
            except Exception as e:
                print(f"\n初始化过程出错: {str(e)}")
        
        init_thread = threading.Thread(target=init_worker)
        init_thread.daemon = True
        init_thread.start()
        
        return jsonify({'success': True, 'message': '全量重建已在后台开始执行'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rebuild', methods=['POST'])
def api_rebuild():
    """增量更新知识库接口"""
    try:
        import threading
        
        def rebuild_worker():
            try:
                print("\n开始增量更新...")
                if kb.initialize():
                    stats = kb.get_statistics()
                    print(f"\n增量更新完成，当前知识库共 {stats['total_documents']} 条记录")
                else:
                    print("\n增量更新失败")
            except Exception as e:
                print(f"\n增量更新出错: {str(e)}")
        
        rebuild_thread = threading.Thread(target=rebuild_worker)
        rebuild_thread.daemon = True
        rebuild_thread.start()
        
        return jsonify({'success': True, 'message': '增量更新已在后台开始执行'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def api_stats():
    """统计信息接口"""
    try:
        stats = kb.get_statistics()
        
        # 添加自动更新状态
        if auto_updater:
            stats['auto_update'] = auto_updater.get_status()
        else:
            stats['auto_update'] = {'watching': False, 'message': '自动更新未启动'}
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/documents')
def api_documents():
    """获取所有文档列表接口"""
    try:
        import redis
        from config import REDIS_CONFIG, KEY_PREFIX
        r = redis.Redis(**REDIS_CONFIG)
        
        # 获取所有文档键
        all_keys = list(r.scan_iter(match=f"{KEY_PREFIX}*", count=1000))
        
        # 过滤掉索引键和缓存键
        doc_keys = [k for k in all_keys if not k.endswith(b'filename_idx') and not k.endswith(b'type_idx') and not k.startswith(b'workorder_fp:') and not k.endswith(b'stats_cache')]
        
        if not doc_keys:
            return jsonify({'total': 0, 'documents': []})
        
        # 批量获取文档数据
        pipe = r.pipeline()
        for key in doc_keys:
            pipe.json().get(key, '$')
        
        docs_data = pipe.execute()
        
        # 处理文档数据
        documents = []
        for doc in docs_data:
            if isinstance(doc, list) and doc:
                d = doc[0]
                documents.append({
                    'file_name': d.get('file_name', ''),
                    'file_path': d.get('file_path', '') or d.get('source', ''),
                    'problem_id': d.get('problem_id', ''),
                    'problem_type': d.get('problem_type', ''),
                    'content_length': len(d.get('content', '')),
                    'created_time': d.get('created_time', 0)
                })
        
        # 按文件名排序
        documents.sort(key=lambda x: x['file_name'])
        
        return jsonify({
            'total': len(documents),
            'documents': documents
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recommend')
def api_recommend():
    """推荐接口"""
    file_path = request.args.get('file_path', '')
    
    if not file_path:
        return jsonify({'error': '缺少file_path参数'}), 400
    
    try:
        from smart_features import SmartRecommender
        
        recommender = SmartRecommender(kb, llm)
        result = recommender.recommend_related(file_path)
        
        for key in result:
            for r in result[key]:
                if 'embedding' in r:
                    del r['embedding']
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/summary')
def api_summary():
    """摘要接口"""
    file_path = request.args.get('file_path', '')
    
    if not file_path:
        return jsonify({'error': '缺少file_path参数'}), 400
    
    try:
        from smart_features import AutoSummarizer
        
        summarizer = AutoSummarizer(kb, llm)
        result = summarizer.summarize_file(file_path)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export', methods=['POST'])
def api_export():
    """导出接口"""
    data = request.get_json()
    format = data.get('format', 'json')
    results = data.get('results', [])
    
    if not results:
        return jsonify({'error': '缺少results参数'}), 400
    
    try:
        from enhanced_features import ResultExporter
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"export_{timestamp}.{format}"
        
        if format == 'csv':
            ResultExporter.to_csv(results, filename)
        elif format == 'excel':
            ResultExporter.to_excel(results, filename)
        elif format == 'json':
            ResultExporter.to_json(results, filename)
        else:
            return jsonify({'error': f'不支持的格式: {format}'}), 400
        
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/types')
def api_types():
    """获取所有问题类型"""
    try:
        stats = kb.get_statistics()
        types = list(stats.get('type_distribution', {}).keys())
        return jsonify(types)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/open_file')
def api_open_file():
    """使用系统默认工具打开文件"""
    file_path = request.args.get('file_path', '')
    
    import logging
    logging.warning(f"[open_file] 原始接收路径: {file_path}")
    
    if not file_path:
        return jsonify({'error': '缺少file_path参数'}), 400
    
    try:
        from urllib.parse import unquote
        import platform
        import subprocess
        
        file_path = unquote(file_path)
        
        logging.warning(f"[open_file] 解码后路径: {file_path}")
        logging.warning(f"[open_file] 文件存在: {os.path.exists(file_path)}")
        
        if not os.path.exists(file_path):
            return jsonify({'error': f'文件不存在: {file_path}'}), 404
        
        success = False
        error_msg = ""
        
        if platform.system() == 'Windows':
            # 获取文件扩展名
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # txt文件使用notepad打开并置于前台
            if ext == '.txt':
                try:
                    import ctypes
                    import time
                    user32 = ctypes.windll.user32
                    
                    # 先尝试查找已打开的窗口
                    file_name = os.path.basename(file_path)
                    hwnd = user32.FindWindowW(None, file_name + " - 记事本")
                    if hwnd == 0:
                        hwnd = user32.FindWindowW(None, file_name + " - Notepad")
                    
                    if hwnd:
                        # 窗口已存在，激活它
                        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        user32.SetForegroundWindow(hwnd)
                        user32.BringWindowToTop(hwnd)
                        logging.warning(f"[open_file] 激活已存在的窗口: {hwnd}")
                        success = True
                    else:
                        # 窗口不存在，启动notepad
                        proc = subprocess.Popen(['notepad.exe', file_path])
                        
                        # 等待窗口创建
                        time.sleep(0.5)
                        
                        # 查找新窗口并置于前台
                        hwnd = user32.FindWindowW(None, file_name + " - 记事本")
                        if hwnd == 0:
                            hwnd = user32.FindWindowW(None, file_name + " - Notepad")
                        
                        if hwnd:
                            user32.SetForegroundWindow(hwnd)
                            user32.BringWindowToTop(hwnd)
                            logging.warning(f"[open_file] 新窗口已置于前台: {hwnd}")
                        
                        success = True
                        logging.warning(f"[open_file] notepad 成功")
                except Exception as e:
                    error_msg += f"notepad失败: {e}; "
                    logging.warning(f"[open_file] notepad 失败: {e}")
            else:
                # 其他文件使用默认程序打开
                try:
                    os.startfile(file_path)
                    success = True
                    logging.warning(f"[open_file] os.startfile 成功")
                except Exception as e1:
                    error_msg += f"os.startfile失败: {e1}; "
                    logging.warning(f"[open_file] os.startfile 失败: {e1}")
        
        elif platform.system() == 'Darwin':
            os.system(f'open "{file_path}"')
            success = True
        else:
            os.system(f'xdg-open "{file_path}"')
            success = True
        
        if success:
            return jsonify({'success': True, 'file_path': file_path})
        else:
            return jsonify({'error': f'打开失败: {error_msg}'}), 500
            
    except Exception as e:
        import logging
        import traceback
        logging.error(f"[open_file] 异常: {e}")
        logging.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/download_file')
def api_download_file():
    """下载文件（使用数据流）"""
    file_path = request.args.get('file_path', '')
    
    if not file_path:
        return jsonify({'error': '缺少file_path参数'}), 400
    
    try:
        from urllib.parse import unquote
        
        file_path = unquote(file_path)
        
        if not os.path.exists(file_path):
            return jsonify({'error': f'文件不存在: {file_path}'}), 404
        
        # 获取文件名
        file_name = os.path.basename(file_path)
        
        # 使用send_file进行数据流下载
        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_name,
            mimetype='application/octet-stream'
        )
            
    except Exception as e:
        import logging
        import traceback
        logging.error(f"[open_file] 异常：{e}")
        logging.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai_format', methods=['POST'])
def api_ai_format():
    """AI格式化文件内容"""
    try:
        data = request.json
        content = data.get('content', '')
        keywords = data.get('keywords', [])
        pattern = data.get('pattern', '')
        exact_match = data.get('exact_match', False)
        
        if not content:
            return jsonify({'error': '内容为空'}), 400
        
        # 调用大模型格式化内容
        formatted_content = ai_format_content(content, keywords, pattern, exact_match)
        
        return jsonify({
            'success': True,
            'formatted_content': formatted_content
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def ai_format_content(content, keywords=[], pattern='', exact_match=False):
    """使用AI格式化内容"""
    try:
        # 动态导入配置，支持热切换
        import importlib
        from config import LOCAL_MODEL_CONFIG, ZHIPU_CONFIG, DEFAULT_MODEL_PROVIDER
        
        # 重新加载配置模块，支持热切换
        import config
        importlib.reload(config)
        
        # 根据最新配置选择模型提供商
        model_provider = config.DEFAULT_MODEL_PROVIDER
        
        # 构建提示词
        prompt = f"请将以下文本进行美化和优化格式，保持原有的语义和信息，同时保留关键词的高亮标记（<span class='highlight'>...</span>）：\n\n{content}"
        
        # 根据模型提供商调用不同的API
        if model_provider == 'local':
            # 调用本地Ollama模型
            import requests
            
            api_url = config.LOCAL_MODEL_CONFIG['api_base']
            model_name = config.LOCAL_MODEL_CONFIG['model']
            temperature = config.LOCAL_MODEL_CONFIG['temperature']
            
            # 构建请求
            data = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature
            }
            
            # 发送请求
            response = requests.post(api_url, json=data, timeout=60)
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            formatted_content = result.get('choices', [{}])[0].get('message', {}).get('content', content)
            
            return formatted_content
        else:
            # 调用智普模型
            global llm
            
            # 如果没有LLM或者配置已更改，重新初始化
            if not llm or hasattr(llm, 'model') and llm.model != config.ZHIPU_CONFIG.get('model', 'glm-4-flash'):
                from zhipu_llm import ZhipuLLM
                llm = ZhipuLLM(config.ZHIPU_CONFIG)
                print("智谱AI已重新初始化")
            
            # 调用LLM
            messages = [{"role": "user", "content": prompt}]
            response = llm.chat(messages)
            
            # 确保高亮标记被保留
            if not response:
                return content
            
            # 返回AI格式化后的内容
            return response
    except Exception as e:
        # 出错时返回原始内容
        return content


# ============== 自然语言到正则的转换 ==============

NATURAL_LANGUAGE_PATTERNS = {
    '手机号': r'1[3-9]\d{9}',
    '电话': r'\d{3,4}[-]?\d{7,8}',
    '订单号': r'OHQ\d{10}',
    '工单号': r'\d{7}',
    '日期': r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
    '时间': r'\d{1,2}:\d{2}:\d{2}',
    '错误': r'错误 | 报错 | 失败 | 异常|Exception|Error',
    '邮箱': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    '网址': r'https?://[^\s]+',
    '身份证': r'\d{17}[\dXx]',
    '数字': r'\d+',
    '金额': r'¥?\d+[,.]?\d*',
}

def parse_natural_language(text: str) -> Optional[Dict]:
    """
    将自然语言转换为正则表达式
    """
    text_lower = text.lower()
    
    # 关键词匹配
    for keyword, pattern in NATURAL_LANGUAGE_PATTERNS.items():
        if keyword in text_lower:
            return {
                'pattern': pattern,
                'description': f'搜索包含{keyword}的内容',
                'examples': generate_regex_examples(pattern),
                'type': 'natural_language'
            }
    
    # 组合搜索检测
    if '同时包含' in text or ('和' in text and '包含' in text):
        keywords = extract_keywords_from_text(text, ['同时包含', '和', '包含', '的', '内容', '文档'])
        if len(keywords) >= 2:
            pattern = '.*'.join(map(re.escape, keywords))
            return {
                'pattern': pattern,
                'description': f'搜索同时包含 {"、".join(keywords)} 的内容',
                'examples': [],
                'type': 'natural_language'
            }
    
    # 包含任一检测
    if ('包含' in text or '或者' in text or '或' in text) and any(k in text for k in ['错误', '失败', '异常', '报错']):
        keywords = extract_keywords_from_text(text, ['包含', '或者', '或', '的', '内容', '文档'])
        if len(keywords) >= 2:
            pattern = '|'.join(map(re.escape, keywords))
            return {
                'pattern': pattern,
                'description': f'搜索包含 {"或".join(keywords)} 的内容',
                'examples': [],
                'type': 'natural_language'
            }
    
    return None


def extract_keywords_from_text(text: str, stop_words: List[str]) -> List[str]:
    """
    从文本中提取关键词
    """
    # 移除停用词
    for word in stop_words:
        text = text.replace(word, ' ')
    
    # 分割并过滤
    keywords = [k.strip() for k in text.split() if len(k.strip()) > 1]
    return keywords


def generate_regex_examples(pattern: str) -> List[str]:
    """
    生成正则表达式的示例匹配
    """
    examples_map = {
        r'1[3-9]\d{9}': ['18692310000', '13912345678', '19812345678'],
        r'OHQ\d{10}': ['OHQ202401001', 'OHQ202402002', 'OHQ202403003'],
        r'\d{4}[-/]\d{1,2}[-/]\d{1,2}': ['2024-01-15', '2023/12/31', '2024-6-1'],
        r'错误 | 报错 | 失败 | 异常|Exception|Error': ['错误', '失败', '系统报错', '操作异常'],
        r'\d{3,4}[-]?\d{7,8}': ['010-12345678', '021-87654321', '12345678'],
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}': ['test@example.com', 'user@domain.cn'],
        r'\d+': ['123', '4567', '89012'],
        r'¥?\d+[,.]?\d*': ['100', '¥1,234.56', '99.99'],
    }
    
    return examples_map.get(pattern, [])


@app.route('/api/regex_search', methods=['GET'])
def api_regex_search():
    """
    正则表达式搜索接口
    
    参数：
    - pattern: 正则表达式模式（必需）
    - search_fields: 搜索字段，可选值：content, solution, file_name, problem_type, problem_id
                     多个字段用逗号分隔，默认为：content,solution
    - flags: 正则标志，可选值：i(忽略大小写), m(多行匹配), s(点号匹配所有)
             多个标志用逗号分隔，默认为：i
    - natural_language: 是否为自然语言输入，true/false
    
    返回：
    - 匹配正则表达式的所有文档
    """
    pattern = request.args.get('pattern', '')
    search_fields_str = request.args.get('search_fields', 'content,solution')
    flags = request.args.get('flags', 'i')
    natural_language = request.args.get('natural_language', 'false').lower() == 'true'
    
    if not pattern:
        return jsonify({'error': '缺少 pattern 参数'}), 400
    
    try:
        # 如果是自然语言输入，尝试转换
        if natural_language:
            parsed = parse_natural_language(pattern)
            if parsed:
                pattern = parsed['pattern']
                logging.info(f"自然语言转换：'{pattern}' -> 正则：{parsed['pattern']}")
            else:
                # 无法转换，使用原始文本作为普通关键词
                pattern = re.escape(pattern)
                logging.info(f"自然语言无法转换，使用转义后的文本：{pattern}")
        
        # 解析搜索字段
        search_fields = [f.strip() for f in search_fields_str.split(',') if f.strip()]
        if not search_fields:
            search_fields = ['content', 'solution']
        
        # 验证字段合法性
        valid_fields = ['content', 'solution', 'file_name', 'problem_type', 'problem_id']
        for field in search_fields:
            if field not in valid_fields:
                return jsonify({'error': f'无效的搜索字段：{field}'}), 400
        
        # 执行搜索
        results = kb.vector_store.find_by_regex(pattern, search_fields, flags)
        
        # 移除 embedding 字段
        for r in results:
            if 'embedding' in r:
                del r['embedding']
            if 'file_path' not in r and 'source' in r:
                r['file_path'] = r['source']
        
        return jsonify({
            'pattern': pattern,
            'search_fields': search_fields,
            'flags': flags,
            'total': len(results),
            'results': results
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"正则搜索失败：{str(e)}")
        return jsonify({'error': str(e)}), 500


# ==================== 知识图谱相关接口 ====================

@app.route('/api/kg/stats')
def api_kg_stats():
    """获取知识图谱统计信息"""
    try:
        from knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        stats = kg.get_stats()
        return jsonify(stats)
    except Exception as e:
        logging.error(f"获取知识图谱统计失败：{str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/kg/entities')
def api_kg_entities():
    """获取实体列表"""
    try:
        from knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        
        entity_type = request.args.get('type', '')
        keyword = request.args.get('keyword', '')
        limit = int(request.args.get('limit', 50))
        
        if keyword:
            entities = kg.search_entities(keyword, limit)
        elif entity_type:
            entities = kg.get_entities_by_type(entity_type)
        else:
            entities = []
            entity_keys = kg.redis_client.keys(f"{kg.entity_prefix}*")
            for entity_key in entity_keys[:limit]:
                entity_data = kg.redis_client.get(entity_key)
                if entity_data:
                    from knowledge_graph import Entity
                    entities.append(Entity.from_dict(json.loads(entity_data)))
        
        return jsonify({
            'total': len(entities),
            'entities': [e.to_dict() for e in entities]
        })
    except Exception as e:
        logging.error(f"获取实体列表失败：{str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/kg/entity/<entity_id>')
def api_kg_entity(entity_id):
    """获取单个实体详情"""
    try:
        from knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        
        entity = kg.get_entity(entity_id)
        if not entity:
            return jsonify({'error': '实体不存在'}), 404
        
        relations = kg.get_relations_by_entity(entity_id)
        
        return jsonify({
            'entity': entity.to_dict(),
            'relations': [r.to_dict() for r in relations]
        })
    except Exception as e:
        logging.error(f"获取实体详情失败：{str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/kg/graph')
def api_kg_graph():
    """获取知识图谱数据"""
    try:
        from knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        
        entity_id = request.args.get('entity_id', '')
        depth = int(request.args.get('depth', 2))
        
        graph_data = kg.get_graph_data(entity_id if entity_id else None, depth)
        
        return jsonify(graph_data)
    except Exception as e:
        logging.error(f"获取知识图谱数据失败：{str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/kg/extract', methods=['POST'])
def api_kg_extract():
    """从文本中抽取知识"""
    try:
        from knowledge_extractor import KnowledgeExtractor
        from knowledge_graph import KnowledgeGraph
        
        data = request.json
        text = data.get('text', '')
        doc_id = data.get('doc_id', '')
        
        if not text:
            return jsonify({'error': '文本不能为空'}), 400
        
        kg = KnowledgeGraph()
        extractor = KnowledgeExtractor(llm_instance=llm, knowledge_graph=kg)
        
        result = extractor.extract_and_save(text, doc_id)
        
        return jsonify(result)
    except Exception as e:
        logging.error(f"知识抽取失败：{str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/kg/batch_extract', methods=['POST'])
def api_kg_batch_extract():
    """批量从文档中抽取知识"""
    try:
        from knowledge_extractor import KnowledgeExtractor
        from knowledge_graph import KnowledgeGraph
        import redis
        from config import REDIS_CONFIG, KEY_PREFIX
        
        data = request.json
        limit = data.get('limit', 10)
        
        documents = []
        
        redis_client = redis.Redis(
            host=REDIS_CONFIG['host'],
            port=REDIS_CONFIG['port'],
            db=REDIS_CONFIG['db'],
            password=REDIS_CONFIG['password'],
            decode_responses=False
        )
        
        doc_keys = list(redis_client.scan_iter(match=f"{KEY_PREFIX}*", count=100))
        
        for doc_key in doc_keys[:limit]:
            try:
                doc_data = redis_client.json().get(doc_key)
                if doc_data:
                    content = doc_data.get('content', '')
                    if isinstance(content, bytes):
                        content = content.decode('utf-8', errors='replace')
                    documents.append({
                        'id': doc_key.decode('utf-8').split(':')[-1] if isinstance(doc_key, bytes) else doc_key.split(':')[-1],
                        'content': content
                    })
            except Exception as e:
                logging.warning(f"读取文档失败 {doc_key}: {e}")
                continue
        
        if not documents:
            return jsonify({'error': '没有可处理的文档'}), 400
        
        kg = KnowledgeGraph()
        extractor = KnowledgeExtractor(llm_instance=llm, knowledge_graph=kg)
        
        result = extractor.batch_extract_from_documents(documents)
        
        return jsonify(result)
    except Exception as e:
        logging.error(f"批量知识抽取失败：{str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/kg/clear', methods=['POST'])
def api_kg_clear():
    """清空知识图谱"""
    try:
        from knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        
        success = kg.clear_all()
        
        return jsonify({'success': success})
    except Exception as e:
        logging.error(f"清空知识图谱失败：{str(e)}")
        return jsonify({'error': str(e)}), 500


def run_server(host='0.0.0.0', port=5000, debug=False):
    """启动服务器"""
    print(f"\n启动Web服务器: http://{host}:{port}")
    print("按 Ctrl+C 停止服务\n")
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    from knowledge_base import KnowledgeBase
    from zhipu_llm import ZhipuLLM
    from config import ZHIPU_CONFIG
    import time
    
    print("初始化知识库...")
    kb = KnowledgeBase(use_llm=True)
    
    # 初始化LLM
    from config import DEFAULT_MODEL_PROVIDER
    
    if DEFAULT_MODEL_PROVIDER == 'local':
        # 使用本地模型
        print("使用本地模型")
    else:
        # 使用智普模型
        if ZHIPU_CONFIG.get('api_key'):
            llm = ZhipuLLM(ZHIPU_CONFIG)
            print("智谱AI已初始化")
    
    # 等待模型加载完成
    print("等待模型加载...")
    if hasattr(kb.vector_store, 'embedding_model') and hasattr(kb.vector_store.embedding_model, 'model_loaded'):
        for i in range(60):
            if kb.vector_store.embedding_model.model_loaded:
                print(f"模型加载完成!")
                break
            time.sleep(1)
            if i % 5 == 0:
                print(f"等待中... {i}秒")
    
    run_server(port=5000, debug=True)
