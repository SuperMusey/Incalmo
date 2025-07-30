#!/bin/bash
set -e

redis-server --daemonize yes --port 6379 --bind 0.0.0.0

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
until redis-cli ping > /dev/null 2>&1; do
    echo "Redis not ready yet, waiting..."
    sleep 1
done
echo "Redis is ready!"

if [ "$MODE" == "openstack" ]; then
  # Copy the key to the management VM (192.168.1.234)
  scp -i /root/perry_key.pem -o StrictHostKeyChecking=no /root/perry_key.pem root@192.168.1.234:/root/perry_key.pem

  # Copy the agent to the management VM (192.168.1.234)
  scp -i /root/perry_key.pem -o StrictHostKeyChecking=no /agents/sandcat.go root@192.168.1.234:/root/sandcat.go

  # Copy the agent to the attacker VM (192.168.202.100) via the first VM
  ssh -i /root/perry_key.pem -o StrictHostKeyChecking=no root@192.168.1.234 \
    "scp -i /root/perry_key.pem -o StrictHostKeyChecking=no /root/sandcat.go root@192.168.202.100:/tmp/"

  # Start the agent on the attacker VM (192.168.202.100) via the first VM
  ssh -i /root/perry_key.pem -o StrictHostKeyChecking=no root@192.168.1.234 \
    "ssh -i /root/perry_key.pem -o StrictHostKeyChecking=no root@192.168.202.100 'nohup /tmp/sandcat.go -server http://$SERVER_IP:8888 -group red > /tmp/agent.log 2>&1 &'"

fi

if [ "$MODE" == "docker" ]; then
  cd /agents
  ./sandcat.go -server http://$SERVER_IP:8888 -group red &
fi


cd /incalmo
uv run celery -A incalmo.c2server.celery.celery_worker worker --concurrency=1 &
sleep 3
uv run ./incalmo/c2server/c2server.py