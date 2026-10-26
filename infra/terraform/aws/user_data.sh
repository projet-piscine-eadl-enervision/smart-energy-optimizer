#!/bin/bash
# Préparation de l'instance de production au premier démarrage (Debian 13).
# Ne s'exécute qu'à la création de l'instance : le modifier ne change pas l'instance en place.
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl git

# Docker et le plugin Compose, depuis le dépôt officiel de Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker

# Agent SSM : le déploiement passe par SSM Run Command, sans SSH
curl -fsSL https://s3.amazonaws.com/ec2-downloads-windows/SSMAgent/latest/debian_amd64/amazon-ssm-agent.deb -o /tmp/amazon-ssm-agent.deb
dpkg -i /tmp/amazon-ssm-agent.deb
systemctl enable --now amazon-ssm-agent

# Dépôt de déploiement et dossier de configuration (production.env et jeton GHCR : à créer à la main, jamais ici)
git clone https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer /opt/enervision
install -d -m 700 /etc/enervision
