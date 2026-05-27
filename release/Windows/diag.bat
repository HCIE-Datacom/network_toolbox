@echo off
cd /d "%~dp0"
echo ========================================
echo checking ports...
echo ========================================

echo.
echo [1] UDP 123:
python\python.exe -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('0.0.0.0',123));print('OK - port 123 free');s.close()" 2>&1

echo.
echo [2] TCP 21:
python\python.exe -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('0.0.0.0',21));s.listen(1);print('OK - port 21 free');s.close()" 2>&1

echo.
echo [3] Starting FTP server with pyftpdlib:
python\python.exe -c "from pyftpdlib.authorizers import DummyAuthorizer;from pyftpdlib.handlers import FTPHandler;from pyftpdlib.servers import FTPServer;from threading import Thread;a=DummyAuthorizer();a.add_user('test','123','.',perm='elradfmw');h=FTPHandler;h.authorizer=a;s=FTPServer(('0.0.0.0',21),h);print('OK - pyftpdlib FTP started on port 21');t=Thread(target=s.serve_forever,daemon=True);t.start()" 2>&1

echo.
echo [4] NetTool app running?
tasklist /FI "IMAGENAME eq NetTool.exe" 2>&1 | find "NetTool"
echo.
pause
