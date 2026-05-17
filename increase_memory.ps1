# 增加Windows虚拟内存脚本
# 需要以管理员身份运行

Write-Host "当前虚拟内存设置:" -ForegroundColor Yellow
$computerSystem = Get-CimInstance -ClassName Win32_ComputerSystem
$automaticManaged = $computerSystem.AutomaticManagedPagefile
Write-Host "自动管理: $automaticManaged"

$pageFile = Get-CimInstance -ClassName Win32_PageFileUsage
if ($pageFile) {
    Write-Host "当前页面文件位置: $($pageFile.Name)"
    Write-Host "当前大小: $([math]::Round($pageFile.AllocatedBaseSize / 1024, 2)) GB"
}

Write-Host ""
Write-Host "建议:" -ForegroundColor Green
Write-Host "1. 手动设置虚拟内存为物理内存的2-3倍"
Write-Host "2. 例如: 16GB内存建议设置 32000MB - 48000MB"
Write-Host ""
Write-Host "请按照以下步骤操作:" -ForegroundColor Cyan
Write-Host "1. 右键'此电脑' -> '属性'"
Write-Host "2. 点击'高级系统设置'"
Write-Host "3. 在'性能'区域点击'设置'"
Write-Host "4. 切换到'高级'选项卡"
Write-Host "5. 在'虚拟内存'区域点击'更改'"
Write-Host "6. 取消'自动管理所有驱动器的分页文件大小'"
Write-Host "7. 选择D盘，选择'自定义大小'"
Write-Host "8. 初始大小: 32000, 最大值: 48000"
Write-Host "9. 点击'设置'，然后'确定'"
Write-Host "10. 重启电脑"
