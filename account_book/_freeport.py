"""사용 가능한(비어 있는) TCP 포트 번호 하나를 표준출력으로 반환한다.
런처(가계부_실행.bat)가 이미 사용 중인 포트와의 충돌을 피하기 위해 사용한다.
"""
import socket

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
