Write-Host 'Starting Database in Docker...' -ForegroundColor Green; docker-compose up -d postgres; Write-Host '
Starting FastAPI Backend...' -ForegroundColor Green; Start-Process powershell -ArgumentList '-NoExit', '-Command', '& { .\.venv\Scripts\Activate.ps1; cd backend; uvicorn app.main:app --reload }'; Write-Host '
Starting Next.js Frontend...' -ForegroundColor Green; Start-Process powershell -ArgumentList '-NoExit', '-Command', '& { cd frontend; npm run dev }'; Write-Host '
All services started! Frontend is at http://localhost:3000' -ForegroundColor Cyan