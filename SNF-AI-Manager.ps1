# SNF-AI Manager - PowerShell GUI Version
# No command line needed - just double-click!

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Create main form
$form = New-Object System.Windows.Forms.Form
$form.Text = "SNF-AI Windsurf Manager"
$form.Size = New-Object System.Drawing.Size(600, 500)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

# License file path
$licenseFile = "$env:APPDATA\SNF-AI\license.txt"

# Status label
$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Location = New-Object System.Drawing.Point(20, 20)
$statusLabel.Size = New-Object System.Drawing.Size(560, 30)
$statusLabel.Font = New-Object System.Drawing.Font("Arial", 12, [System.Drawing.FontStyle]::Bold)
$statusLabel.Text = "SNF-AI Status: Checking..."
$form.Controls.Add($statusLabel)

# License group
$licenseGroup = New-Object System.Windows.Forms.GroupBox
$licenseGroup.Location = New-Object System.Drawing.Point(20, 60)
$licenseGroup.Size = New-Object System.Drawing.Size(560, 100)
$licenseGroup.Text = "License Configuration"
$form.Controls.Add($licenseGroup)

$licenseLabel = New-Object System.Windows.Forms.Label
$licenseLabel.Location = New-Object System.Drawing.Point(10, 25)
$licenseLabel.Size = New-Object System.Drawing.Size(100, 20)
$licenseLabel.Text = "License Key:"
$licenseGroup.Controls.Add($licenseLabel)

$licenseTextBox = New-Object System.Windows.Forms.TextBox
$licenseTextBox.Location = New-Object System.Drawing.Point(10, 45)
$licenseTextBox.Size = New-Object System.Drawing.Size(400, 20)
$licenseGroup.Controls.Add($licenseTextBox)

$saveLicenseButton = New-Object System.Windows.Forms.Button
$saveLicenseButton.Location = New-Object System.Drawing.Point(420, 43)
$saveLicenseButton.Size = New-Object System.Drawing.Size(130, 25)
$saveLicenseButton.Text = "Save License"
$saveLicenseButton.Add_Click({
    $license = $licenseTextBox.Text.Trim()
    if ($license) {
        New-Item -ItemType Directory -Force -Path "$env:APPDATA\SNF-AI" | Out-Null
        $license | Out-File -FilePath $licenseFile -Force
        [System.Windows.Forms.MessageBox]::Show("License key saved!", "Success", "OK", "Information")
        Load-License
    } else {
        [System.Windows.Forms.MessageBox]::Show("Please enter a license key", "Error", "OK", "Error")
    }
})
$licenseGroup.Controls.Add($saveLicenseButton)

$buyLicenseButton = New-Object System.Windows.Forms.Button
$buyLicenseButton.Location = New-Object System.Drawing.Point(10, 70)
$buyLicenseButton.Size = New-Object System.Drawing.Size(540, 25)
$buyLicenseButton.Text = "Purchase License ($20/month)"
$buyLicenseButton.Add_Click({
    Start-Process "https://sunny-imagination-production.up.railway.app"
})
$licenseGroup.Controls.Add($buyLicenseButton)

# Control buttons
$controlGroup = New-Object System.Windows.Forms.GroupBox
$controlGroup.Location = New-Object System.Drawing.Point(20, 170)
$controlGroup.Size = New-Object System.Drawing.Size(560, 120)
$controlGroup.Text = "Container Controls"
$form.Controls.Add($controlGroup)

$startButton = New-Object System.Windows.Forms.Button
$startButton.Location = New-Object System.Drawing.Point(10, 25)
$startButton.Size = New-Object System.Drawing.Size(170, 40)
$startButton.Text = "Start SNF-AI"
$startButton.BackColor = [System.Drawing.Color]::LightGreen
$startButton.Font = New-Object System.Drawing.Font("Arial", 10, [System.Drawing.FontStyle]::Bold)
$startButton.Add_Click({
    Start-Container
})
$controlGroup.Controls.Add($startButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Location = New-Object System.Drawing.Point(195, 25)
$stopButton.Size = New-Object System.Drawing.Size(170, 40)
$stopButton.Text = "Stop SNF-AI"
$stopButton.BackColor = [System.Drawing.Color]::LightCoral
$stopButton.Font = New-Object System.Drawing.Font("Arial", 10, [System.Drawing.FontStyle]::Bold)
$stopButton.Add_Click({
    Stop-Container
})
$controlGroup.Controls.Add($stopButton)

$updateButton = New-Object System.Windows.Forms.Button
$updateButton.Location = New-Object System.Drawing.Point(380, 25)
$updateButton.Size = New-Object System.Drawing.Size(170, 40)
$updateButton.Text = "Update SNF-AI"
$updateButton.BackColor = [System.Drawing.Color]::LightBlue
$updateButton.Font = New-Object System.Drawing.Font("Arial", 10, [System.Drawing.FontStyle]::Bold)
$updateButton.Add_Click({
    Update-Container
})
$controlGroup.Controls.Add($updateButton)

$openButton = New-Object System.Windows.Forms.Button
$openButton.Location = New-Object System.Drawing.Point(10, 70)
$openButton.Size = New-Object System.Drawing.Size(540, 40)
$openButton.Text = "Open Application in Browser"
$openButton.BackColor = [System.Drawing.Color]::LightYellow
$openButton.Font = New-Object System.Drawing.Font("Arial", 10, [System.Drawing.FontStyle]::Bold)
$openButton.Add_Click({
    Start-Process "http://localhost:3000"
})
$controlGroup.Controls.Add($openButton)

# Log display
$logGroup = New-Object System.Windows.Forms.GroupBox
$logGroup.Location = New-Object System.Drawing.Point(20, 300)
$logGroup.Size = New-Object System.Drawing.Size(560, 150)
$logGroup.Text = "Activity Log"
$form.Controls.Add($logGroup)

$logTextBox = New-Object System.Windows.Forms.TextBox
$logTextBox.Location = New-Object System.Drawing.Point(10, 20)
$logTextBox.Size = New-Object System.Drawing.Size(540, 120)
$logTextBox.Multiline = $true
$logTextBox.ScrollBars = "Vertical"
$logTextBox.ReadOnly = $true
$logGroup.Controls.Add($logTextBox)

# Functions
function Log-Message {
    param($message)
    $timestamp = Get-Date -Format "HH:mm:ss"
    $logTextBox.AppendText("[$timestamp] $message`r`n")
    $logTextBox.ScrollToCaret()
    $form.Refresh()
}

function Load-License {
    if (Test-Path $licenseFile) {
        $license = Get-Content $licenseFile -Raw
        $licenseTextBox.Text = $license.Trim()
        Log-Message "License key loaded"
        return $license.Trim()
    }
    return $null
}

function Check-Status {
    try {
        $result = docker ps -a --filter name=twhyne --format "{{.Status}}" 2>$null
        if ($result -like "*Up*") {
            $statusLabel.Text = "SNF-AI Status: ✓ Running"
            $statusLabel.ForeColor = [System.Drawing.Color]::Green
            $startButton.Enabled = $false
            $stopButton.Enabled = $true
        } elseif ($result) {
            $statusLabel.Text = "SNF-AI Status: ⚠ Stopped"
            $statusLabel.ForeColor = [System.Drawing.Color]::Orange
            $startButton.Enabled = $true
            $stopButton.Enabled = $false
        } else {
            $statusLabel.Text = "SNF-AI Status: ✗ Not Installed"
            $statusLabel.ForeColor = [System.Drawing.Color]::Red
            $startButton.Enabled = $true
            $stopButton.Enabled = $false
        }
    } catch {
        $statusLabel.Text = "SNF-AI Status: ✗ Docker Not Found"
        $statusLabel.ForeColor = [System.Drawing.Color]::Red
        Log-Message "Error: Docker not installed or not running"
    }
}

function Start-Container {
    $license = Load-License
    if (-not $license) {
        [System.Windows.Forms.MessageBox]::Show("Please enter and save your license key first", "License Required", "OK", "Warning")
        return
    }
    
    Log-Message "Starting SNF-AI..."
    
    # Pull latest image
    Log-Message "Downloading latest version..."
    $result = docker pull twhyne/twhyne:licensed 2>&1
    
    # Stop and remove old container
    docker stop twhyne 2>$null
    docker rm twhyne 2>$null
    
    # Start new container
    Log-Message "Starting container..."
    $result = docker run -d `
        --name twhyne `
        -e SNF_LICENSE_KEY="$license" `
        -p 3000:3000 `
        -p 5001:5001 `
        --mount source=snf_models,target=/app/models `
        --mount source=snf_logs,target=/app/logs `
        --mount source=snf_data,target=/app/data `
        --mount source=snf_uploads,target=/app/uploads `
        --mount source=snf_rag,target=/app/rag_storage `
        --mount source=snf_conversations,target=/app/conversations `
        --restart unless-stopped `
        twhyne/twhyne:licensed 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Log-Message "✓ SNF-AI started successfully!"
        
        # Clean up old images
        Log-Message "Cleaning up old images..."
        docker image prune -f 2>$null | Out-Null
        
        [System.Windows.Forms.MessageBox]::Show("SNF-AI is now running!`n`nAccess at: http://localhost:3000", "Success", "OK", "Information")
    } else {
        Log-Message "✗ Failed to start: $result"
        [System.Windows.Forms.MessageBox]::Show("Failed to start SNF-AI. Check the log for details.", "Error", "OK", "Error")
    }
    
    Check-Status
}

function Stop-Container {
    Log-Message "Stopping SNF-AI..."
    $result = docker stop twhyne 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Log-Message "✓ SNF-AI stopped"
        [System.Windows.Forms.MessageBox]::Show("SNF-AI has been stopped", "Success", "OK", "Information")
    } else {
        Log-Message "✗ Failed to stop: $result"
    }
    
    Check-Status
}

function Update-Container {
    $license = Load-License
    if (-not $license) {
        [System.Windows.Forms.MessageBox]::Show("Please enter and save your license key first", "License Required", "OK", "Warning")
        return
    }
    
    Log-Message "Updating SNF-AI..."
    
    # Pull latest
    Log-Message "Downloading latest version..."
    docker pull twhyne/twhyne:latest 2>&1 | Out-Null
    
    # Stop old
    Log-Message "Stopping current version..."
    docker stop twhyne 2>$null
    docker rm twhyne 2>$null
    
    # Start new
    Log-Message "Starting updated version..."
    docker run -d `
        --name twhyne `
        -e SNF_LICENSE_KEY="$license" `
        -p 3000:3000 `
        -p 5001:5001 `
        --mount source=snf_models,target=/app/models `
        --mount source=snf_logs,target=/app/logs `
        --mount source=snf_data,target=/app/data `
        --mount source=snf_uploads,target=/app/uploads `
        --mount source=snf_rag,target=/app/rag_storage `
        --mount source=snf_conversations,target=/app/conversations `
        --restart unless-stopped `
        twhyne/twhyne:latest 2>&1 | Out-Null
    
    # Clean up
    Log-Message "Cleaning up old versions..."
    docker image prune -f 2>$null | Out-Null
    
    Log-Message "✓ Update complete!"
    [System.Windows.Forms.MessageBox]::Show("SNF-AI has been updated successfully!", "Update Complete", "OK", "Information")
    
    Check-Status
}

# Initialize
Load-License
Check-Status
Log-Message "SNF-AI Manager ready"

# Show form
$form.ShowDialog()
