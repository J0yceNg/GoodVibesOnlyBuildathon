# PowerShell script to generate a complex SUMO network
# This creates a 10x8 grid network with varying lane configurations

Write-Host "Generating complex city network..." -ForegroundColor Green

# Generate the complex network
netgenerate `
    --grid `
    --grid.x-number=10 `
    --grid.y-number=8 `
    --grid.length=350 `
    --grid.attach-length=50 `
    --default.lanenumber=4 `
    --default.speed=16.67 `
    --turn-lanes=2 `
    --turn-lanes.length=30 `
    --tls.guess=true `
    --tls.green.time=45 `
    --tls.yellow.time=4 `
    --tls.red.time=3 `
    --junctions.corner-detail=5 `
    --junctions.limit-turn-speed=5.5 `
    --lefthand=false `
    --output-file=complex_city.net.xml

if ($LASTEXITCODE -eq 0) {
    Write-Host "Network generated successfully: complex_city.net.xml" -ForegroundColor Green
    Write-Host ""
    Write-Host "Network Details:" -ForegroundColor Cyan
    Write-Host "  - Grid Size: 10x8 (80 intersections)" -ForegroundColor White
    Write-Host "  - Block Length: 350 meters" -ForegroundColor White
    Write-Host "  - Default Lanes: 4 per direction" -ForegroundColor White
    Write-Host "  - Max Speed: 60 km/h (16.67 m/s)" -ForegroundColor White
    Write-Host "  - Turn Lanes: 2 per intersection" -ForegroundColor White
    Write-Host "  - Traffic Lights: Enabled (90s cycle)" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "Error generating network!" -ForegroundColor Red
    exit 1
}
