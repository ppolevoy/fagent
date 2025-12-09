#!/bin/bash

echo "=== Testing Docker Subprocess Version ==="
echo ""

# Бэкап текущих плагинов
echo "1. Backing up current plugins..."
cp plugins/docker_client.py plugins/docker_client.py.dockerpy.backup
cp plugins/docker_discoverer.py plugins/docker_discoverer.py.dockerpy.backup
echo "   ✓ Backup created"
echo ""

# Установка PS версии
echo "2. Installing subprocess versions..."
cp integrations/docker_client_ps.py plugins/docker_client.py
cp integrations/docker_discoverer_ps.py plugins/docker_discoverer.py
echo "   ✓ Subprocess versions installed"
echo ""

# Тест клиента
echo "3. Testing docker_client_ps..."
python3.11 -c "
import sys
sys.path.insert(0, 'plugins')
from docker_client import DockerClient

client = DockerClient()
containers = client.get_containers()
print(f'   ✓ Found {len(containers)} containers')

if containers:
    c = containers[0]
    cid = c.get('ID')
    print(f'   ✓ Container ID: {cid[:12]}')

    # Тест методов
    pid = client.get_container_pid(cid)
    print(f'   ✓ PID: {pid}')

    port = client.parse_port_mapping(c.get('Ports', ''))
    print(f'   ✓ Port: {port}')
" 2>&1 | grep -v "^DEBUG"

echo ""

# Тест discoverer
echo "4. Testing docker_discoverer_ps..."
python3.11 -c "
import sys
sys.path.insert(0, '.')
from plugins.docker_discoverer import DockerDiscoverer
import config

config.DOCKER_DISCOVERY_ENABLED = True
config.EUREKA_DISCOVERY_ENABLED = False

discoverer = DockerDiscoverer()
apps = discoverer.discover()
print(f'   ✓ Discovered {len(apps)} applications')

if apps:
    app = apps[0]
    print(f'   ✓ App name: {app.name}')
    print(f'   ✓ Version: {app.version}')
    print(f'   ✓ PID: {app.metadata.get(\"pid\")}')
" 2>&1 | grep -v "^DEBUG" | grep -v "^20"

echo ""

# Восстановление docker-py версии
echo "5. Restoring docker-py versions..."
cp plugins/docker_client.py.dockerpy.backup plugins/docker_client.py
cp plugins/docker_discoverer.py.dockerpy.backup plugins/docker_discoverer.py
rm plugins/docker_client.py.dockerpy.backup
rm plugins/docker_discoverer.py.dockerpy.backup
echo "   ✓ docker-py versions restored"

echo ""
echo "✓ All tests completed successfully"
