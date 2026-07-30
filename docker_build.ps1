[CmdletBinding()]
param(
    [ValidateSet("12.6", "12.8", "13.0")]
    [string]$CudaVersion,

    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"

function Get-CudaRuntime {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        throw "nvidia-smi was not found. Install an NVIDIA driver or pass -CudaVersion."
    }

    $smiOutput = nvidia-smi 2>&1 | Out-String
    $match = [regex]::Match($smiOutput, "CUDA (?:UMD )?Version:\s*(\d+)\.(\d+)")
    if (-not $match.Success) {
        throw "Unable to detect CUDA compatibility from nvidia-smi."
    }

    $major = [int]$match.Groups[1].Value
    $minor = [int]$match.Groups[2].Value

    if ($major -ge 13) {
        return "13.0"
    }
    if ($major -eq 12 -and $minor -ge 8) {
        return "12.8"
    }
    if ($major -eq 12 -and $minor -ge 6) {
        return "12.6"
    }

    throw "CUDA 12.6 or newer is required; the driver reports $major.$minor."
}

if (-not $CudaVersion) {
    $CudaVersion = Get-CudaRuntime
}

$architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
switch ($architecture) {
    "X64" { $targetPlatform = "linux/amd64" }
    "Arm64" { $targetPlatform = "linux/arm64" }
    default { throw "Unsupported architecture: $architecture" }
}

Write-Host "Building with Python $PythonVersion, CUDA $CudaVersion, platform $targetPlatform"

docker build `
    --build-arg "CUDA_VERSION=$CudaVersion" `
    --build-arg "PYTHON_VERSION=$PythonVersion" `
    --build-arg "TARGETPLATFORM=$targetPlatform" `
    --build-arg "WORKFLOW=true" `
    --tag "gpt-sovits-api:local" `
    .

if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed with exit code $LASTEXITCODE."
}
