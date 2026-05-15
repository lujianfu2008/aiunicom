# 修复 ReferenceError: formatSmartly is not defined

## 问题描述

在使用正则查询的"查看全部"功能时，出现错误：
```
加载失败：ReferenceError: formatSmartly is not defined
```

## 问题原因

在 `viewFileWithRegex` 函数中调用了不存在的函数：
- `formatSmartly()` ❌ - 该函数不存在
- `formatBySections()` ❌ - 该函数不存在

正确的函数名应该是：
- `formatSmartContent()` ✅
- `formatSectionContent()` ✅

## 解决方案

### 1. 修改函数调用

将 `viewFileWithRegex` 中的函数调用修改为使用已存在的函数：

```javascript
// 修改前（错误）
const smartFormatted = formatSmartly(content, highlightedContent);
const sectionFormatted = formatBySections(content, decodedPattern);

// 修改后（正确）
const smartFormatted = formatSmartContent(content, [], false, decodedPattern);
const sectionFormatted = formatSectionContent(content, [], false, decodedPattern);
```

### 2. 增强格式化函数支持正则高亮

修改 `formatSmartContent` 和 `formatSectionContent` 函数，让它们支持 pattern 参数：

**formatSmartContent**:
```javascript
function formatSmartContent(content, keywords, exactMatch = false, pattern = '') {
    // 智能格式化
    let highlightFunc;
    if (pattern) {
        // 使用正则高亮
        highlightFunc = (text, kw) => highlightRegexContent(text, pattern);
    } else {
        highlightFunc = exactMatch ? highlightAndEscapeExact : highlightAndEscape;
    }
    // ... 其余代码
}
```

**formatSectionContent**:
```javascript
function formatSectionContent(content, keywords, exactMatch = false, pattern = '') {
    // 按段落分段显示
    let highlightFunc;
    if (pattern) {
        // 使用正则高亮
        highlightFunc = (text, kw) => highlightRegexContent(text, pattern);
    } else {
        highlightFunc = exactMatch ? highlightAndEscapeExact : highlightAndEscape;
    }
    // ... 其余代码
}
```

### 3. 修改 setFormat 函数

让格式切换时也支持正则高亮：

```javascript
function setFormat(format) {
    const buttons = document.querySelectorAll('.format-btn');
    buttons.forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    
    const display = document.getElementById('content-display');
    const content = window.rawContent || '';
    const keywords = window.contentKeywords || [];
    const pattern = window.regexPattern || '';  // 获取 pattern
    
    // 根据是否有 pattern 选择高亮函数
    const highlightFunc = pattern 
        ? (text, kw) => highlightRegexContent(text, pattern)
        : (window.exactMatch ? highlightAndEscapeExact : highlightAndEscape);
    
    if (format === 'raw') {
        display.innerHTML = highlightFunc(content, keywords);
    } else if (format === 'smart') {
        display.innerHTML = formatSmartContent(content, keywords, window.exactMatch, pattern);
    } else if (format === 'section') {
        display.innerHTML = formatSectionContent(content, keywords, window.exactMatch, pattern);
    }
}
```

## 修改文件

- [`api_server.py`](file:///e:/AIknowledge/aiunicom/api_server.py)
  - 第 1027-1035 行：`viewFileWithRegex` 函数
  - 第 1122-1147 行：`setFormat` 函数
  - 第 1144-1158 行：`formatSmartContent` 函数签名
  - 第 1230-1244 行：`formatSectionContent` 函数签名

## 测试验证

### 测试步骤

1. 启动服务器
2. 在正则匹配搜索中输入 `1[3-9]\d{9}`
3. 点击"开始搜索"
4. 点击任意结果的"查看全部"按钮
5. 确认弹窗正常显示，没有错误

### 预期结果

✅ 弹窗正常打开  
✅ 内容正确显示  
✅ 手机号被高亮  
✅ 可以切换"原始文本"、"智能格式"、"分段显示"  
✅ 各种格式下高亮都正常

## 功能说明

### 三种显示格式

1. **原始文本**：显示文件的原始内容，保留所有格式
2. **智能格式**：自动识别标题、键值对、列表、代码块等，并美化显示
3. **分段显示**：按段落分段，每段一个编号，便于阅读

### 高亮类型

- **正则高亮**：当使用正则查询时，高亮匹配正则的内容
- **关键词高亮**：当使用普通搜索时，高亮关键词

## 版本历史

- **v1.8.2** - 修复 formatSmartly 未定义错误
  - 修改为使用正确的函数名 `formatSmartContent` 和 `formatSectionContent`
  - 增强格式化函数支持正则高亮
  - 修改 `setFormat` 函数支持 pattern 参数

---

**更新时间**: 2026-03-24  
**版本**: v1.8.2
