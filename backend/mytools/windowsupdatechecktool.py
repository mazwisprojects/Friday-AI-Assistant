import subprocess

def run(args=None):
    """Check for pending Windows updates using PowerShell."""
    result = subprocess.run(
        ['powershell', '-Command', 'Get-WindowsUpdate'],
        capture_output=True, text=True, timeout=60
    )
    return {
        'stdout': result.stdout,
        'stderr': result.stderr,
        'returncode': result.returncode
    }

if __name__ == '__main__':
    import json
    args = json.loads(input()) if False else {}
    output = run(args)
    print(json.dumps(output, default=str))
