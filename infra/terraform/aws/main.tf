locals {
  name = "${var.project}-${var.environment}"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  github_oidc_provider_arn = (
    var.create_github_oidc_provider
    ? aws_iam_openid_connect_provider.github[0].arn
    : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
  )
}

data "aws_caller_identity" "current" {}

# Image Debian 13 officielle : même système que la VM du staging.
data "aws_ami" "debian" {
  most_recent = true
  owners      = ["136693071363"] # Debian

  filter {
    name   = "name"
    values = ["debian-13-amd64-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Accès à l'instance par AWS Systems Manager : ni SSH ni IP publique pour administrer ou déployer.
data "aws_iam_policy_document" "instance_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${local.name}-instance"
  assume_role_policy = data.aws_iam_policy_document.instance_assume.json
}

resource "aws_iam_role_policy_attachment" "instance_ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "instance" {
  name = "${local.name}-instance"
  role = aws_iam_role.instance.name
}

#trivy:ignore:AWS-0104
resource "aws_security_group" "instance" {
  name        = "${local.name}-instance"
  description = "Instance de production EnerVision"
  vpc_id      = var.vpc_id

  # Sortie limitée à HTTP et HTTPS (GHCR, dépôts Debian, agent SSM, API Mock).
  # Les adresses de GHCR et de SSM ne sont pas énumérables, d'où 0.0.0.0/0.
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_vpc_security_group_ingress_rule" "api" {
  for_each = toset(var.api_ingress_cidrs)

  security_group_id = aws_security_group.instance.id
  description       = "API (port 8000)"
  cidr_ipv4         = each.value
  from_port         = 8000
  to_port           = 8000
  ip_protocol       = "tcp"
}

resource "aws_instance" "main" {
  ami                    = data.aws_ami.debian.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.instance.id]
  iam_instance_profile   = aws_iam_instance_profile.instance.name

  # Docker, agent SSM et clone du dépôt : voir user_data.sh (premier démarrage uniquement).
  user_data                   = file("${path.module}/user_data.sh")
  user_data_replace_on_change = false

  metadata_options {
    http_tokens                 = "required" # IMDSv2 uniquement
    http_put_response_hop_limit = 2          # les conteneurs Docker obtiennent les droits du rôle de l'instance
  }

  root_block_device {
    volume_size = var.root_volume_gb
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name = local.name
  }

  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

# Déploiement depuis GitHub Actions sans secret AWS : le workflow échange son jeton OIDC contre ce rôle.
resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "deploy_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Seuls les jobs de l'environnement GitHub `production` (approbation requise) peuvent assumer le rôle.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${var.github_oidc_sub_prefix}:environment:production"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name               = "${local.name}-deploy"
  assume_role_policy = data.aws_iam_policy_document.deploy_assume.json
}

# Le rôle ne peut lancer que des commandes shell sur cette instance, et lire leur résultat.
data "aws_iam_policy_document" "deploy" {
  statement {
    actions = ["ssm:SendCommand"]
    resources = [
      aws_instance.main.arn,
      "arn:aws:ssm:${var.region}::document/AWS-RunShellScript",
    ]
  }

  statement {
    actions   = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "${local.name}-deploy"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
