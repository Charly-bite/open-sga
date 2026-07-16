import socket

def test_port(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex((ip, port))
    sock.close()
    return result == 0

ip = '192.168.2.187'
print(f"Port 1433 (SQL Server): {test_port(ip, 1433)}")
print(f"Port 1434 (SQL Browser): {test_port(ip, 1434)}")
print(f"Port 445 (SMB): {test_port(ip, 445)}")
print(f"Port 3389 (RDP): {test_port(ip, 3389)}")
