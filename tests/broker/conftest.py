"""이식한 broker 테스트가 scripts/broker/ 를 import 할 수 있게 경로를 붙인다.

원 프로젝트에서는 테스트가 scripts/ 바로 아래 tests/ 에 있어 상대 경로로 잡혔지만,
이 프로젝트는 tests/broker/ 와 scripts/broker/ 로 갈라져 있어 conftest 가 필요하다.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'broker'))
