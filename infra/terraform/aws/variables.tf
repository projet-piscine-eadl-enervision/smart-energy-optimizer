variable "region" {
  description = "Région AWS des ressources (Paris)."
  type        = string
  default     = "eu-west-3"
}

variable "project" {
  description = "Nom du projet, utilisé dans les noms et les tags."
  type        = string
  default     = "enervision"
}

variable "environment" {
  description = "Environnement déployé par ce dossier."
  type        = string
  default     = "production"
}

variable "vpc_id" {
  description = "VPC dans lequel créer le groupe de sécurité (VPC par défaut du compte)."
  type        = string
}

variable "subnet_id" {
  description = "Sous-réseau de l'instance (dans le VPC par défaut du compte)."
  type        = string
}

variable "instance_type" {
  description = "Type d'instance. Elle héberge base, API, ETL et frontend : 8 Go de mémoire."
  type        = string
  default     = "t3.large"
}

variable "root_volume_gb" {
  description = "Taille du disque racine, en Go."
  type        = number
  default     = 64
}

variable "api_ingress_cidrs" {
  description = "CIDR autorisés à joindre l'API (port 8000). Vide par défaut : le site passe par CloudFront et le frontend, l'API n'a pas à être ouverte."
  type        = list(string)
  default     = []
}

variable "create_github_oidc_provider" {
  description = "Créer le fournisseur OIDC de GitHub. Un seul est possible par compte AWS : mettre false s'il existe déjà."
  type        = bool
  default     = true
}

variable "github_oidc_sub_prefix" {
  description = "Préfixe du claim sub OIDC de GitHub. Le dépôt utilise le format immuable (noms suivis des identifiants numériques) : valeur donnée par gh api repos/<org>/<depot>/actions/oidc/customization/sub."
  type        = string
  default     = "repo:projet-piscine-eadl-enervision@344791702/smart-energy-optimizer@1425243299"
}