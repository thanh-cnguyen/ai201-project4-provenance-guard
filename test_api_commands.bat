@echo off
REM Provenance Guard API test commands for Windows Command Prompt
REM Make sure Flask is running first:
REM python app.py

echo.
echo === Test 1: Submit content ===
echo Copy the content_id from the response below.
curl -s -X POST http://localhost:5000/submit -H "Content-Type: application/json" -d "{\"creator_id\":\"user-123\",\"text\":\"The sun dipped below the horizon, painting the sky in quiet shades of amber and violet.\"}"

echo.
echo.
set /p CONTENT_ID=Paste the content_id from Test 1 here: 

echo.
echo Press Enter to continue to Test 2...
pause > nul

echo.
echo === Test 2: View audit log ===
curl -s -X GET http://localhost:5000/log

echo.
echo.
echo Press Enter to continue to Test 3...
pause > nul

echo.
echo === Test 3: Submit valid appeal ===
curl -s -X POST http://localhost:5000/appeal -H "Content-Type: application/json" -d "{\"content_id\":\"%CONTENT_ID%\",\"creator_id\":\"user-123\",\"creator_reasoning\":\"I wrote this myself and can provide drafts or revision history.\"}"

echo.
echo.
echo Press Enter to continue to Test 4...
pause > nul

echo.
echo === Test 4: View audit log after appeal ===
curl -s -X GET http://localhost:5000/log

echo.
echo.
echo Press Enter to continue to Test 5...
pause > nul

echo.
echo === Test 5: Submit duplicate appeal ===
echo Expected result: duplicate appeal error.
curl -s -X POST http://localhost:5000/appeal -H "Content-Type: application/json" -d "{\"content_id\":\"%CONTENT_ID%\",\"creator_id\":\"user-123\",\"creator_reasoning\":\"Submitting the same appeal again.\"}"

echo.
echo.
echo Press Enter to continue to Test 6...
pause > nul

echo.
echo === Test 6: Submit appeal with wrong creator ===
echo Expected result: wrong creator error.
curl -s -X POST http://localhost:5000/appeal -H "Content-Type: application/json" -d "{\"content_id\":\"%CONTENT_ID%\",\"creator_id\":\"wrong-user\",\"creator_reasoning\":\"Trying to appeal someone else's content.\"}"

echo.
echo.
echo Press Enter to continue to Test 7...
pause > nul

echo.
echo === Test 7: Rate limit /submit ===
echo Expected result: first requests should return 200, then 429 after the limit is exceeded.
for /L %%i in (1,1,12) do curl -s -o NUL -w "%%{http_code}\n" -X POST http://localhost:5000/submit -H "Content-Type: application/json" -d "{\"creator_id\":\"rate-test-user\",\"text\":\"This is a test submission for rate limit testing purposes only.\"}"

echo.
echo.
echo Press Enter to continue to Test 8...
pause > nul

echo.
echo === Test 8: Final audit log ===
curl -s -X GET http://localhost:5000/log

echo.
echo Done.
pause